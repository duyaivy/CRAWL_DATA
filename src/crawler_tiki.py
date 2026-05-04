import csv
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

# ==============================
# CONFIG
# ==============================

BASE_URL = "https://tiki.vn/api/v2/products"
QUERY = "ao khoac jacket"
CATEGORY = "ao_khoac"
LIMIT = 40
MAX_PAGES = 50
REQUEST_TIMEOUT = 15
REQUEST_DELAY = 1.5
TIKI_TRACKITY_ID = os.getenv(
    "TIKI_TRACKITY_ID", "70be08b3-8fa5-ca27-69c5-bb2c444a49d2"
)

REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://tiki.vn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

OUTPUT_COLUMNS = [
    "id",
    "name",
    "price",
    "brand",
    "source",
    "source_url",
    "original_image_url",
    "image_url",
    "category",
    "final_category",
    "image_index",
    "crawl_status",
    "crawled_at",
]

CSV_PATH = "data/01_raw_products_tiki.csv"


# ==============================
# CSV HELPERS
# ==============================


def load_existing(csv_path):
    seen_urls = set()
    seen_images = set()
    last_id = 0

    if not Path(csv_path).exists():
        return seen_urls, seen_images, last_id

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("source_url"):
                seen_urls.add(row["source_url"])
            if row.get("image_url"):
                seen_images.add(row["image_url"])
            try:
                last_id = max(last_id, int(row["id"]))
            except (TypeError, ValueError):
                pass

    return seen_urls, seen_images, last_id


def ensure_header(csv_path):
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()


def append_rows(csv_path, rows):
    if not rows:
        return
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writerows(rows)


# ==============================
# CORE CRAWL
# ==============================


def build_params(query, page):
    return {
        "limit": LIMIT,
        "include": "advertisement",
        "is_mweb": 1,
        "aggregations": 2,
        "version": "",
        "_v": "within_promotions",
        "trackity_id": TIKI_TRACKITY_ID,
        "q": query,
        "page": page,
    }


def build_url(query, page):
    return f"{BASE_URL}?{urlencode(build_params(query, page))}"


def _body_preview(response):
    return response.text[:160].replace("\n", " ").replace("\r", " ").strip()


def normalize_tiki_image_url(url):
    if not url:
        return ""
    return url.replace("salt.tikicdn.com/cache/280x280/", "salt.tikicdn.com/")


def fetch_products(session, query, page):
    response = session.get(
        BASE_URL,
        params=build_params(query, page),
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    content_type = response.headers.get("content-type", "")

    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code} from Tiki "
            f"({content_type or 'unknown content-type'}): {_body_preview(response)}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Tiki returned non-JSON response "
            f"({content_type or 'unknown content-type'}): {_body_preview(response)}"
        ) from exc

    data = payload.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected Tiki response shape: data={type(data).__name__}")

    return data


def crawl(
    query: str = QUERY,
    category: str = CATEGORY,
    csv_path: str = CSV_PATH,
    max_pages: int = MAX_PAGES,
    target: int | None = None,
):
    ensure_header(csv_path)

    seen_urls, seen_images, next_id = load_existing(csv_path)
    next_id += 1

    total = 0
    session = requests.Session()

    for page in range(1, max_pages + 1):
        if target is not None and total >= target:
            break

        url = build_url(query, page)
        print(f"-> Crawling page {page}")

        try:
            data = fetch_products(session, query, page)
        except Exception as exc:
            print("ERROR:", exc)
            print(f"URL: {url}")
            continue

        if not data:
            print("No more data, stop")
            break

        rows = []

        for item in data:
            source_url = "https://tiki.vn/" + item.get("url_path", "")
            original_image_url = item.get("thumbnail_url", "")
            image_url = normalize_tiki_image_url(original_image_url)

            if source_url in seen_urls or image_url in seen_images:
                continue

            if target is not None and total >= target:
                break

            seen_urls.add(source_url)
            seen_images.add(image_url)

            row = {
                "id": str(next_id).zfill(6),
                "name": item.get("name", ""),
                "price": item.get("price", ""),
                "brand": item.get("brand_name", ""),
                "source": "tiki",
                "source_url": source_url,
                "original_image_url": original_image_url,
                "image_url": image_url,
                "category": category,
                "final_category": category,
                "image_index": 0,
                "crawl_status": "raw",
                "crawled_at": datetime.utcnow().isoformat(),
            }

            rows.append(row)
            next_id += 1
            total += 1

        append_rows(csv_path, rows)

        print(f"Page {page}: +{len(rows)} items")
        time.sleep(REQUEST_DELAY)

    print(f"\nDONE. Total: {total} products")
    return total


def _category_keywords(category: str, explicit_keywords: list[str] | None) -> list[str]:
    if explicit_keywords:
        return [keyword.strip() for keyword in explicit_keywords if keyword.strip()]

    try:
        from src.config import CATEGORIES
    except ModuleNotFoundError:
        CATEGORIES = {}

    configured = CATEGORIES.get(category, category)
    if isinstance(configured, str):
        return [configured.strip()]
    keywords = [keyword.strip() for keyword in configured if keyword.strip()]
    return keywords or [category.replace("_", " ")]


def run_crawler(
    category: str | None = None,
    target: int | None = None,
    keywords: list[str] | None = None,
    raw_csv_path: str | None = None,
    max_pages: int | None = None,
) -> None:
    try:
        from src.config import (
            CATEGORIES,
            DEFAULT_CATEGORY,
            TARGET_PER_CATEGORY,
            MAX_PAGES_PER_CATEGORY,
            category_raw_csv_path,
            ensure_pipeline_dirs,
        )
    except ModuleNotFoundError:
        CATEGORIES = {}
        DEFAULT_CATEGORY = CATEGORY
        TARGET_PER_CATEGORY = None
        MAX_PAGES_PER_CATEGORY = MAX_PAGES

        def category_raw_csv_path(category_key: str) -> str:
            return CSV_PATH

        def ensure_pipeline_dirs() -> None:
            Path("data/raw").mkdir(parents=True, exist_ok=True)

    ensure_pipeline_dirs()

    selected_categories = [category] if category else list(CATEGORIES.keys()) or [DEFAULT_CATEGORY]

    target_count = TARGET_PER_CATEGORY if target is None else target
    page_limit = MAX_PAGES_PER_CATEGORY if max_pages is None else max_pages
    if page_limit <= 0:
        raise ValueError("--max-pages must be greater than 0")
    if target_count is not None and target_count <= 0:
        raise ValueError("--target must be greater than 0")

    for category_key in selected_categories:
        csv_path = raw_csv_path or category_raw_csv_path(category_key)
        collected = 0

        for query in _category_keywords(category_key, keywords):
            if target_count is not None and collected >= target_count:
                break

            remaining_target = None
            if target_count is not None:
                remaining_target = target_count - collected

            collected += crawl(
                query=query,
                category=category_key,
                csv_path=csv_path,
                max_pages=page_limit,
                target=remaining_target,
            )


if __name__ == "__main__":
    run_crawler()
