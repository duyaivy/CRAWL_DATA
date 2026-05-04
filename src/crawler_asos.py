import csv
import requests
import time
from datetime import datetime
from pathlib import Path

# ==============================
# CONFIG
# ==============================

BASE_URL = "https://www.asos.com/api/product/search/v2/"
QUERY = "jean"
CATEGORY = "jean"
LIMIT = 72
MAX_PAGES = 50

CSV_PATH = "data/01_raw_products_asos.csv"

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
            except:
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
# NORMALIZE
# ==============================


def normalize_product_url(url):
    if not url:
        return ""
    return "https://www.asos.com/" + url


def select_best_image(product):
    """
    Chọn ảnh phù hợp nhất cho classification:
    1. ưu tiên additionalImageUrls[4] (thứ 5)
    2. nếu không có, dùng additionalImageUrls[2] (thứ 3)
    3. fallback về imageUrl chính
    """
    additional = product.get("additionalImageUrls", [])
    if len(additional) >= 5:
        return "https://" + additional[4] + ".jpg"
    elif len(additional) >= 3:
        return "https://" + additional[2] + ".jpg"
    else:
        img = product.get("imageUrl", "")
        return "https://" + img + ".jpg" if img else ""


def normalize_image_url(url):
    if not url:
        return ""
    suffix = "" if url.endswith(".jpg") else ".jpg"
    if url.startswith("//"):
        return "https:" + url + suffix
    if url.startswith("http://") or url.startswith("https://"):
        return url + suffix
    return "https://" + url + suffix


def select_product_images(product):
    """
    Return up to 2 unique images for one product.
    Priority: additional image #5, additional image #3, fallback #4, then primary.
    """
    additional = product.get("additionalImageUrls", [])
    candidates = []

    for image_index, list_index in ((5, 4), (3, 2), (4, 3)):
        if len(additional) > list_index:
            candidates.append((image_index, normalize_image_url(additional[list_index])))

    candidates.append((0, normalize_image_url(product.get("imageUrl", ""))))

    selected = []
    seen = set()
    for image_index, image_url in candidates:
        if not image_url or image_url in seen:
            continue
        selected.append((image_index, image_url))
        seen.add(image_url)
        if len(selected) == 2:
            break

    return selected


def build_url(query, offset):
    return (
        f"{BASE_URL}"
        f"?offset={offset}"
        f"&q={query}"
        f"&store=ROW"
        f"&lang=en-GB"
        f"&currency=USD"
        f"&limit={LIMIT}"
        f"&country=VN"
    )


# ==============================
# CORE
# ==============================


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

    for page in range(max_pages):
        if target is not None and total >= target:
            break

        offset = page * LIMIT
        url = build_url(query, offset)

        print(f"👉 Page {page+1} (offset={offset})")

        try:
            res = requests.get(url, timeout=10)
            data = res.json().get("products", [])
        except Exception as e:
            print("❌ Error:", e)
            continue

        if not data:
            print("⚠️ No more data")
            break

        rows = []

        for item in data:
            if target is not None and total >= target:
                break

            source_url = normalize_product_url(item.get("url"))
            price = item.get("price", {}).get("current", {}).get("value", "")

            for image_index, image_url in select_product_images(item):
                if image_url in seen_images:
                    continue

                if target is not None and total >= target:
                    break

                seen_urls.add(source_url)
                seen_images.add(image_url)

                row = {
                    "id": str(next_id).zfill(6),
                    "name": item.get("name", ""),
                    "price": price,
                    "brand": item.get("brandName", ""),
                    "source": "asos",
                    "source_url": source_url,
                    "original_image_url": image_url,
                    "image_url": image_url,
                    "category": category,
                    "final_category": category,
                    "image_index": image_index,
                    "crawl_status": "raw",
                    "crawled_at": datetime.utcnow().isoformat(),
                }

                rows.append(row)
                next_id += 1
                total += 1

        append_rows(csv_path, rows)

        print(f"✅ +{len(rows)} items")

        time.sleep(1.2)

    print(f"\n🎉 DONE: {total} products")
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
    if target_count is not None and target_count <= 0:
        raise ValueError("--target must be greater than 0")
    if page_limit <= 0:
        raise ValueError("--max-pages must be greater than 0")

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
