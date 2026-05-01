"""Pipeline Step 5: Build MongoDB-ready category CSV files."""

from __future__ import annotations

import logging

from src.config import (
    category_clean_csv_path,
    category_cloudinary_csv_path,
    category_final_csv_path,
    ensure_pipeline_dirs,
)
from src.utils import get_original_image_url, read_csv_rows, write_csv_rows

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

FINAL_COLUMNS: list[str] = [
    "category",
    "name",
    "price",
    "brand",
    "source",
    "sourceUrl",
    "originalImageUrl",
    "cloudinaryUrl",
    "cloudinaryPublicId",
    "createdAt",
]


def _mapping_by_filename(rows: list[dict]) -> dict[str, dict]:
    return {row.get("filename", ""): row for row in rows if row.get("filename")}


def run_final_builder(
    category: str,
    clean_csv_path: str | None = None,
    cloudinary_csv_path: str | None = None,
    final_csv_path: str | None = None,
) -> None:
    ensure_pipeline_dirs()
    clean_path = clean_csv_path or category_clean_csv_path(category)
    mapping_path = cloudinary_csv_path or category_cloudinary_csv_path(category)
    out_path = final_csv_path or category_final_csv_path(category)

    clean_rows = read_csv_rows(clean_path)
    mapping_rows = _mapping_by_filename(read_csv_rows(mapping_path))
    if not clean_rows:
        logger.warning("No input rows found at %s", clean_path)
        write_csv_rows(out_path, FINAL_COLUMNS, [])
        return

    final_rows: list[dict] = []
    for row in clean_rows:
        mapping = mapping_rows.get(row.get("filename", ""), {})
        cloudinary_url = row.get("cloudinary_url") or mapping.get("secure_url", "")
        cloudinary_public_id = row.get("cloudinary_public_id") or mapping.get("public_id", "")
        if not cloudinary_url or not cloudinary_public_id:
            logger.warning("Skipping row %s: missing Cloudinary metadata", row.get("id", ""))
            continue

        final_rows.append(
            {
                "category": row.get("final_category") or row.get("category", ""),
                "name": row.get("name", ""),
                "price": row.get("price", ""),
                "brand": row.get("brand", ""),
                "source": row.get("source", ""),
                "sourceUrl": row.get("source_url", ""),
                "originalImageUrl": get_original_image_url(row),
                "cloudinaryUrl": cloudinary_url,
                "cloudinaryPublicId": cloudinary_public_id,
                "createdAt": row.get("uploaded_at", ""),
            }
        )

    write_csv_rows(out_path, FINAL_COLUMNS, final_rows)
    logger.info("Built %d MongoDB-ready rows -> %s", len(final_rows), out_path)


if __name__ == "__main__":
    run_final_builder("quan_jean")
