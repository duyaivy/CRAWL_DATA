"""Configuration and path helpers for the fashion data pipeline."""

from __future__ import annotations

from pathlib import Path

# Category -> keyword list. Keep values as lists so one category can crawl
# several search terms while still writing a single category CSV.
CATEGORIES: dict[str, list[str]] = {
    "quan_jean": ["quan jean"],
}

DEFAULT_CATEGORY: str = "quan_jean"
TARGET_PER_CATEGORY: int = 600
MAX_PAGES_PER_CATEGORY: int = 100

# ---------------------------------------------------------------------------
# Pipeline paths
# ---------------------------------------------------------------------------

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
VALIDATED_DIR = DATA_DIR / "validated"
CLEAN_DIR = DATA_DIR / "clean"
CLOUDINARY_DIR = DATA_DIR / "cloudinary"
FINAL_DIR = DATA_DIR / "final"

# Legacy defaults kept for backwards-compatible main.py calls.
RAW_CSV_PATH: str = "data/01_raw_products.csv"
VALIDATED_CSV_PATH: str = "data/02_validated_products.csv"
REVIEWED_CSV_PATH: str = "data/03_human_reviewed_products.csv"
CLEAN_CSV_PATH: str = "data/04_clean_products.csv"
UPLOADED_CSV_PATH: str = "data/05_uploaded_products.csv"


def category_raw_csv_path(category: str) -> str:
    return str(RAW_DIR / f"{category}_raw.csv")


def category_validated_csv_path(category: str) -> str:
    return str(VALIDATED_DIR / f"{category}_validated.csv")


def category_reviewed_csv_path(category: str) -> str:
    return str(CLEAN_DIR / f"{category}_reviewed.csv")


def category_clean_csv_path(category: str) -> str:
    return str(CLEAN_DIR / f"{category}_clean.csv")


def category_cloudinary_csv_path(category: str) -> str:
    return str(CLOUDINARY_DIR / f"{category}_cloudinary.csv")


def category_final_csv_path(category: str) -> str:
    return str(FINAL_DIR / f"{category}_data.csv")


def ensure_pipeline_dirs() -> None:
    for path in (RAW_DIR, VALIDATED_DIR, CLEAN_DIR, CLOUDINARY_DIR, FINAL_DIR):
        path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Validation settings
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_SEC: int = 15
MIN_WIDTH: int = 300
MIN_HEIGHT: int = 300
BLUR_THRESHOLD: float = 40.0
HASH_DISTANCE_THRESHOLD: int = 5

DOWNLOAD_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Cloudinary
# ---------------------------------------------------------------------------

CLOUDINARY_FOLDER_PREFIX: str = ""

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

MONGODB_COLLECTION: str = "fashion_images"
