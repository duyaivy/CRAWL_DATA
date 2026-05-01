"""
src/crawler_lazada.py
Fashion product metadata crawler for Lazada Vietnam using Selenium.

Mục tiêu:
- Crawl metadata sản phẩm từ trang search/tag của Lazada.
- Lưu CSV theo format cũ: id, source, source_url, name, category, price, brand, image_url...
- Không tải ảnh ở bước này, chỉ lấy image_url để validate/upload ở các bước sau.

Cách chạy nhanh:
    python src/crawler_lazada.py

Gợi ý config:
- Nếu có src/config.py thì file này sẽ dùng CATEGORIES, TARGET_PER_CATEGORY, RAW_CSV_PATH, MAX_PAGES_PER_CATEGORY.
- Nếu không có thì dùng fallback bên dưới.
"""

import csv
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

try:
    from src.config import (
        CATEGORIES,
        category_raw_csv_path,
        ensure_pipeline_dirs,
        MAX_PAGES_PER_CATEGORY,
        RAW_CSV_PATH,
        TARGET_PER_CATEGORY,
    )
except ModuleNotFoundError:
    CATEGORIES = {
        "quan_jean": "quần jean",
        # "ao_thun": "áo thun",
        # "ao_so_mi": "áo sơ mi",
        # "ao_khoac": "áo khoác",
        # "quan_tay": "quần tây",
        # "ao_len": "áo len",
        # "vay": "váy",
        # "quan_short": "quần short",
    }
    TARGET_PER_CATEGORY = 1000
    RAW_CSV_PATH = "data/01_raw_products_lazada.csv"
    MAX_PAGES_PER_CATEGORY = 100

    def category_raw_csv_path(category: str) -> str:
        return f"data/raw/{category}_raw.csv"

    def ensure_pipeline_dirs() -> None:
        Path("data/raw").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAZADA_DOMAIN = "https://www.lazada.vn"
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

# Selector theo HTML Lazada bạn gửi
PRODUCT_LIST_CSS = 'div[data-qa-locator="product-item"]'
PRODUCT_NAME_CSS = ".RfADt a"
PRODUCT_PRICE_CSS = ".ooOxS"
PRODUCT_IMAGE_CSS = 'img[type="product"], img[type="thumb"], img'

WAIT_TIMEOUT = 20
MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Driver setup
# ---------------------------------------------------------------------------


def _build_driver() -> webdriver.Chrome:
    options = Options()

    # Test nên để mở browser để xem Lazada có load đúng không.
    # Khi đã ổn có thể bật headless.
    # options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=vi-VN")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(45)
    return driver


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def _load_existing_data(csv_path: str) -> tuple[set[str], set[str], int]:
    """Return (seen_source_urls, seen_image_urls, last_id_int)."""
    seen_source_urls: set[str] = set()
    seen_image_urls: set[str] = set()
    last_id = 0

    path = Path(csv_path)
    if not path.exists():
        return seen_source_urls, seen_image_urls, last_id

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("source_url"):
                seen_source_urls.add(row["source_url"])
            image_url = row.get("original_image_url") or row.get("image_url")
            if image_url:
                seen_image_urls.add(image_url)
            try:
                last_id = max(last_id, int(row.get("id", 0)))
            except ValueError:
                pass

    logger.info(
        "Loaded existing CSV: %d source_urls, %d image_urls, last id=%d",
        len(seen_source_urls),
        len(seen_image_urls),
        last_id,
    )
    return seen_source_urls, seen_image_urls, last_id


def _ensure_csv_header(csv_path: str) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
        return

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        existing_header = next(reader, [])

    if existing_header != OUTPUT_COLUMNS:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = path.with_name(f"{path.stem}_{timestamp}{path.suffix}.bak")
        path.replace(backup_path)
        logger.warning(
            "Existing raw CSV header did not match pipeline format. "
            "Moved old file to %s and created a new CSV.",
            backup_path,
        )
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()


def _append_rows(csv_path: str, rows: list[dict]) -> None:
    if not rows:
        return
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writerows([{key: row.get(key, "") for key in OUTPUT_COLUMNS} for row in rows])


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _slugify_vi(keyword: str) -> str:
    """
    Lazada tag URL thường có dạng:
        /tag/quần-jean/
    Browser/Selenium xử lý unicode path được, nhưng quote lại cho chắc.
    """
    slug = keyword.strip().lower().replace(" ", "-")
    return quote(slug)


def _build_search_url(keyword: str, page_num: int) -> str:
    """
    Build Lazada tag search URL in the format that currently returns results:
    https://www.lazada.vn/tag/qu%E1%BA%A7n-jean/?spm=...&q=...&catalog_redirect_tag=true
    """
    slug = _slugify_vi(keyword)
    q = quote(keyword)
    url = (
        f"{LAZADA_DOMAIN}/tag/{slug}/"
        f"?spm=a2o4n.homepage.search.d_go"
        f"&q={q}"
        f"&catalog_redirect_tag=true"
    )
    if page_num > 1:
        url = f"{url}&page={page_num}"
    return url


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(LAZADA_DOMAIN, url)
    return url


def _normalize_image_url(url: str) -> str:
    """
    Lazada hay trả ảnh dạng:
        //vn-live-01.slatic.net/...
        https://...jpg_200x200q80.jpg
    Ta chuẩn hóa protocol và bỏ suffix resize nếu muốn lấy ảnh gốc hơn.
    """
    url = _normalize_url(url)
    if not url:
        return ""

    # Bỏ phần resize phổ biến của Lazada: .jpg_200x200q80.jpg -> .jpg
    url = re.sub(
        r"(\.(?:jpg|jpeg|png|webp))_\d+x\d+q\d+\.(?:jpg|jpeg|png|webp)$", r"\1", url
    )
    return url


# ---------------------------------------------------------------------------
# Extract helpers
# ---------------------------------------------------------------------------


def _safe_text(element, by: By, selector: str) -> str:
    try:
        return element.find_element(by, selector).text.strip()
    except NoSuchElementException:
        return ""


def _best_image_url(element) -> str:
    try:
        img = element.find_element(By.CSS_SELECTOR, PRODUCT_IMAGE_CSS)

        # Lazada có thể lazy-load qua nhiều attribute khác nhau
        for attr in ("src", "data-src", "data-ks-lazyload", "srcset"):
            value = img.get_attribute(attr) or ""
            if not value:
                continue

            if attr == "srcset":
                # Lấy candidate cuối trong srcset
                parts = [p.strip().split()[0] for p in value.split(",") if p.strip()]
                if parts:
                    return _normalize_image_url(parts[-1])

            return _normalize_image_url(value)

    except NoSuchElementException:
        return ""

    return ""


def _extract_product_from_card(element) -> dict | None:
    """
    Extract từ DOM card:
    - card: div[data-qa-locator="product-item"]
    - name/link: .RfADt a
    - price: .ooOxS
    - image: img[type="product"]
    """
    try:
        name = ""
        source_url = ""

        try:
            name_link = element.find_element(By.CSS_SELECTOR, PRODUCT_NAME_CSS)
            name = (name_link.get_attribute("title") or name_link.text or "").strip()
            source_url = _normalize_url(name_link.get_attribute("href") or "")
        except NoSuchElementException:
            pass

        if not name:
            # fallback: lấy alt ảnh
            try:
                img = element.find_element(By.CSS_SELECTOR, PRODUCT_IMAGE_CSS)
                name = (img.get_attribute("alt") or "").strip()
            except NoSuchElementException:
                pass

        price = _safe_text(element, By.CSS_SELECTOR, PRODUCT_PRICE_CSS)
        image_url = _best_image_url(element)

        if not name or not image_url:
            logger.warning("Skipping product: missing name or image_url")
            return None

        return {
            "name": name,
            "price": price,
            "image_url": image_url,
            "source_url": source_url,
        }

    except StaleElementReferenceException:
        logger.warning("Stale element encountered, skipping product")
        return None


def _extract_products_from_json_ld(page_source: str) -> list[dict]:
    """
    Fallback nếu DOM selector thay đổi.
    Lazada thường có script application/ld+json chứa ItemList/Product.
    Nhược điểm: thường không có price.
    """
    products: list[dict] = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )

    for match in pattern.findall(page_source):
        raw_json = match.strip()
        if not raw_json:
            continue

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict) and data.get("@type") == "ItemList":
            for item in data.get("itemListElement", []):
                product = item.get("item", {}) if isinstance(item, dict) else {}
                if not isinstance(product, dict):
                    continue

                name = (product.get("name") or "").strip()
                image_url = _normalize_image_url(product.get("image") or "")
                source_url = _normalize_url(product.get("url") or "")

                if name and image_url:
                    products.append(
                        {
                            "name": name,
                            "price": "",
                            "image_url": image_url,
                            "source_url": source_url,
                        }
                    )

    return products


def _scroll_to_load_products(driver: webdriver.Chrome) -> None:
    """
    Lazada render/lazy-load khi scroll.
    Scroll vài lần để ảnh và card load đủ hơn.
    """
    last_height = 0

    for _ in range(5):
        driver.execute_script(
            "window.scrollBy(0, Math.floor(window.innerHeight * 0.9));"
        )
        time.sleep(random.uniform(0.8, 1.4))

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(random.uniform(0.5, 1.0))


# ---------------------------------------------------------------------------
# Page-level crawl
# ---------------------------------------------------------------------------


def _crawl_page(
    driver: webdriver.Chrome,
    url: str,
    category: str,
    seen_source_urls: set[str],
    seen_image_urls: set[str],
    next_id: int,
) -> tuple[list[dict], int, int]:
    new_rows: list[dict] = []
    duplicates = 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Opening: %s", url)
            driver.get(url)

            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        f'{PRODUCT_LIST_CSS}, script[type="application/ld+json"]',
                    )
                )
            )

            _scroll_to_load_products(driver)
            break

        except TimeoutException:
            logger.warning("Timeout on %s (attempt %d/%d)", url, attempt, MAX_RETRIES)
            if attempt == MAX_RETRIES:
                return new_rows, duplicates, next_id

        except WebDriverException as exc:
            logger.warning(
                "WebDriverException on %s (attempt %d): %s", url, attempt, exc
            )
            if attempt == MAX_RETRIES:
                return new_rows, duplicates, next_id

        time.sleep(random.uniform(2.0, 4.0))

    time.sleep(random.uniform(1.5, 3.0))

    products: list[dict] = []

    try:
        product_elements = driver.find_elements(By.CSS_SELECTOR, PRODUCT_LIST_CSS)
        for el in product_elements:
            product = _extract_product_from_card(el)
            if product:
                products.append(product)
    except WebDriverException as exc:
        logger.warning("Could not extract DOM product elements: %s", exc)

    if not products:
        logger.info("DOM extraction empty, trying JSON-LD fallback")
        products = _extract_products_from_json_ld(driver.page_source)

    now_iso = datetime.utcnow().isoformat()

    for product in products:
        source_url = product.get("source_url", "")
        image_url = product.get("image_url", "")

        if source_url and source_url in seen_source_urls:
            duplicates += 1
            continue

        if image_url and image_url in seen_image_urls:
            duplicates += 1
            continue

        if source_url:
            seen_source_urls.add(source_url)
        if image_url:
            seen_image_urls.add(image_url)

        row = {
            "id": str(next_id).zfill(6),
            "name": product.get("name", ""),
            "price": product.get("price", ""),
            "brand": "Lazada",
            "source": "lazada",
            "source_url": source_url,
            "original_image_url": image_url,
            "image_url": image_url,
            "category": category,
            "final_category": category,
            "image_index": 0,
            "crawl_status": "raw",
            "crawled_at": now_iso,
        }

        new_rows.append(row)
        next_id += 1

    return new_rows, duplicates, next_id


# ---------------------------------------------------------------------------
# Category-level crawl
# ---------------------------------------------------------------------------


def _crawl_category(
    driver: webdriver.Chrome,
    category_key: str,
    keyword: str,
    seen_source_urls: set[str],
    seen_image_urls: set[str],
    next_id: int,
    csv_path: str,
    target: int,
    max_pages: int,
) -> tuple[int, int, int, int]:
    collected = 0
    skipped_dup = 0
    consecutive_empty_pages = 0

    pbar = tqdm(
        total=target,
        desc=f"{category_key}",
        unit="item",
        dynamic_ncols=True,
    )

    try:
        for page_num in range(1, max_pages + 1):
            if collected >= target:
                break

            url = _build_search_url(keyword, page_num)
            pbar.set_postfix_str(f"page={page_num} | collected={collected}")

            new_rows, dup, next_id = _crawl_page(
                driver=driver,
                url=url,
                category=category_key,
                seen_source_urls=seen_source_urls,
                seen_image_urls=seen_image_urls,
                next_id=next_id,
            )

            if not new_rows and dup == 0:
                consecutive_empty_pages += 1
                logger.info(
                    "[%s] No products found on page %d. Empty streak=%d",
                    category_key,
                    page_num,
                    consecutive_empty_pages,
                )
                if consecutive_empty_pages >= MAX_RETRIES:
                    break
                continue

            consecutive_empty_pages = 0

            remaining = target - collected
            if len(new_rows) > remaining:
                new_rows = new_rows[:remaining]

            _append_rows(csv_path, new_rows)

            collected += len(new_rows)
            skipped_dup += dup
            pbar.update(len(new_rows))

            # Nghỉ nhẹ để tránh spam request
            time.sleep(random.uniform(2.0, 5.0))

    finally:
        pbar.close()

    return collected, skipped_dup, consecutive_empty_pages, next_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _category_keywords(category: str, explicit_keywords: list[str] | None) -> list[str]:
    if explicit_keywords:
        return [keyword.strip() for keyword in explicit_keywords if keyword.strip()]

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
    ensure_pipeline_dirs()
    selected_categories = [category] if category else list(CATEGORIES.keys())
    target_count = TARGET_PER_CATEGORY if target is None else target
    page_limit = MAX_PAGES_PER_CATEGORY if max_pages is None else max_pages
    if target_count <= 0:
        raise ValueError("--target must be greater than 0")
    if page_limit <= 0:
        raise ValueError("--max-pages must be greater than 0")

    driver = _build_driver()
    logger.info("Chrome WebDriver started.")

    try:
        for category_key in selected_categories:
            csv_path = raw_csv_path or category_raw_csv_path(category_key)
            _ensure_csv_header(csv_path)
            seen_source_urls, seen_image_urls, last_id = _load_existing_data(csv_path)
            next_id = last_id + 1
            collected = 0
            skipped = 0
            failed = 0

            for keyword in _category_keywords(category_key, keywords):
                if collected >= target_count:
                    break

                logger.info("[%s] Starting crawl for keyword '%s'", category_key, keyword)

                remaining_target = target_count - collected
                got, skipped_dup, empty_streak, next_id = _crawl_category(
                    driver=driver,
                    category_key=category_key,
                    keyword=keyword,
                    seen_source_urls=seen_source_urls,
                    seen_image_urls=seen_image_urls,
                    next_id=next_id,
                    csv_path=csv_path,
                    target=remaining_target,
                    max_pages=page_limit,
                )
                collected += got
                skipped += skipped_dup
                failed = max(failed, empty_streak)

            logger.info(
                "[%s] Done: %d collected, %d skipped duplicate, %d empty/failed streak -> %s",
                category_key,
                collected,
                skipped,
                failed,
                csv_path,
            )

    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt received. Exiting safely.")

    finally:
        try:
            driver.quit()
            logger.info("Chrome WebDriver closed.")
        except WebDriverException as exc:
            logger.warning("Error closing WebDriver: %s", exc)


if __name__ == "__main__":
    run_crawler()
