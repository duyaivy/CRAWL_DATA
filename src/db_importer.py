"""Pipeline Step 6: Import final MongoDB-ready CSV data."""

from __future__ import annotations

import logging
import os
import argparse

from dotenv import load_dotenv

from src.config import (
    DEFAULT_CATEGORY,
    MONGODB_COLLECTION,
    UPLOADED_CSV_PATH,
    category_final_csv_path,
)
from src.utils import read_csv_rows

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def _build_record(row: dict) -> dict:
    return {
        "category": row.get("category") or row.get("final_category", ""),
        "name": row.get("name", ""),
        "price": row.get("price", ""),
        "brand": row.get("brand", ""),
        "source": row.get("source", ""),
        "sourceUrl": row.get("sourceUrl") or row.get("source_url", ""),
        "originalImageUrl": row.get("originalImageUrl") or row.get("original_image_url", ""),
        "cloudinaryUrl": row.get("cloudinaryUrl") or row.get("cloudinary_url", ""),
        "cloudinaryPublicId": row.get("cloudinaryPublicId") or row.get("cloudinary_public_id", ""),
        "createdAt": row.get("createdAt") or row.get("uploaded_at", ""),
    }


def _import_mongodb(records: list[dict]) -> None:
    from pymongo import MongoClient
    from pymongo import UpdateOne

    mongodb_uri = os.getenv("MONGODB_URI", "")
    mongodb_database = os.getenv("MONGODB_DATABASE", "fashion_dataset")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set")

    client = MongoClient(mongodb_uri)
    db = client[mongodb_database]
    collection = db[MONGODB_COLLECTION]

    collection.create_index("cloudinaryPublicId")
    collection.create_index("sourceUrl")
    operations = []
    skipped = 0
    for record in records:
        cloudinary_public_id = record.get("cloudinaryPublicId", "")
        source_url = record.get("sourceUrl", "")
        original_image_url = record.get("originalImageUrl", "")

        if cloudinary_public_id:
            filter_doc = {"cloudinaryPublicId": cloudinary_public_id}
        elif source_url:
            filter_doc = {"sourceUrl": source_url}
        elif original_image_url:
            filter_doc = {"originalImageUrl": original_image_url}
        else:
            skipped += 1
            continue

        operations.append(UpdateOne(filter_doc, {"$setOnInsert": record}, upsert=True))

    if not operations:
        logger.warning("No importable records found. Skipped %d rows.", skipped)
        return

    result = collection.bulk_write(operations, ordered=False)
    logger.info(
        "MongoDB import done: %d inserted, %d already existed, %d skipped",
        result.upserted_count,
        len(operations) - result.upserted_count,
        skipped,
    )


def run_db_importer(category: str | None = None, final_csv_path: str | None = None) -> None:
    load_dotenv()
    csv_path = final_csv_path or (category_final_csv_path(category) if category else UPLOADED_CSV_PATH)
    rows = read_csv_rows(csv_path)
    if not rows:
        logger.warning("No input rows found at %s", csv_path)
        return

    records = [_build_record(row) for row in rows]

    mongodb_uri = os.getenv("MONGODB_URI", "")
    if mongodb_uri:
        _import_mongodb(records)
        return

    logger.error("No database config found. Set MONGODB_URI.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import final category CSV into MongoDB")
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    args = parser.parse_args()
    run_db_importer(category=args.category)


if __name__ == "__main__":
    main()
