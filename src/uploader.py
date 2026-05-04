"""Pipeline Step 4: Upload approved image URLs to Cloudinary."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

from src.config import (
    CLEAN_CSV_PATH,
    CLOUDINARY_FOLDER_PREFIX,
    UPLOADED_CSV_PATH,
    category_clean_csv_path,
    category_cloudinary_csv_path,
    category_reviewed_csv_path,
    ensure_pipeline_dirs,
)
from src.utils import get_original_image_url, now_iso, read_csv_rows, write_csv_rows

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

CLOUDINARY_COLUMNS: list[str] = ["filename", "secure_url", "public_id"]

UPDATED_CLEAN_COLUMNS: list[str] = [
    "id",
    "name",
    "price",
    "brand",
    "source",
    "source_url",
    "original_image_url",
    "category",
    "final_category",
    "width",
    "height",
    "blur_score",
    "image_hash",
    "cloudinary_url",
    "cloudinary_public_id",
    "uploaded_at",
    "filename",
]

REVIEWED_TO_CLEAN_COLUMNS: list[str] = [
    "id",
    "name",
    "price",
    "brand",
    "source",
    "source_url",
    "original_image_url",
    "category",
    "final_category",
    "width",
    "height",
    "blur_score",
    "image_hash",
]


def _configure_cloudinary() -> None:
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    api_key = os.getenv("CLOUDINARY_API_KEY", "")
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "")
    if not all((cloud_name, api_key, api_secret)):
        raise RuntimeError(
            "Cloudinary config is incomplete. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env."
        )
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def _filename(row: dict, index: int, start_id: int) -> str:
    existing = row.get("filename", "")
    if existing:
        return existing
    return f"{start_id + index}.jpg"


def _category_folder(category: str) -> str:
    safe_category = (category or "unknown").strip().strip("/")
    safe_prefix = CLOUDINARY_FOLDER_PREFIX.strip().strip("/")
    return "/".join(part for part in (safe_prefix, safe_category) if part)


def _cloudinary_public_id(category: str, filename: str) -> str:
    stem = Path(filename).stem
    folder = _category_folder(category)
    return f"{folder}/{stem}" if folder else stem


def _load_existing_mappings(mapping_path: str) -> dict[str, dict]:
    mappings: dict[str, dict] = {}
    for row in read_csv_rows(mapping_path):
        filename = row.get("filename", "")
        public_id = row.get("public_id", "")
        if filename:
            mappings[f"filename:{filename}"] = row
        if public_id:
            mappings[f"public_id:{public_id}"] = row
    return mappings


def _load_clean_rows(clean_path: str, category: str | None) -> list[dict]:
    rows = read_csv_rows(clean_path)
    if rows:
        return rows

    if not category:
        return []

    reviewed_path = category_reviewed_csv_path(category)
    reviewed_rows = read_csv_rows(reviewed_path)
    approved_rows = [
        {column: row.get(column, "") for column in REVIEWED_TO_CLEAN_COLUMNS}
        for row in reviewed_rows
        if row.get("human_status") == "approved"
    ]
    if approved_rows:
        write_csv_rows(clean_path, REVIEWED_TO_CLEAN_COLUMNS, approved_rows)
        logger.info(
            "Created %s from %d approved rows in %s",
            clean_path,
            len(approved_rows),
            reviewed_path,
        )
    return approved_rows


def _upload_one(
    index: int,
    total: int,
    row: dict,
    category: str | None,
    start_id: int,
    existing_mappings: dict[str, dict],
) -> tuple[int, dict, dict | None]:
    image_url = get_original_image_url(row)
    if not image_url:
        logger.warning("Skipping row %s: missing original_image_url", row.get("id", index))
        return index, row, None

    filename = _filename(row, index, start_id)
    final_category = row.get("final_category") or row.get("category") or category or "unknown"
    folder = _category_folder(final_category)
    public_id_stem = Path(filename).stem
    public_id = _cloudinary_public_id(final_category, filename)

    existing_url = row.get("cloudinary_url", "")
    existing_public_id = row.get("cloudinary_public_id", "")
    if existing_url and existing_public_id and existing_public_id == public_id:
        logger.info(
            "[%d/%d] Skip existing upload: id=%s filename=%s public_id=%s",
            index + 1,
            total,
            row.get("id", ""),
            filename,
            existing_public_id,
        )
        updated = {
            **row,
            "original_image_url": image_url,
            "filename": filename,
        }
        mapping = {
            "filename": filename,
            "secure_url": existing_url,
            "public_id": existing_public_id,
        }
        return index, updated, mapping

    existing_mapping = existing_mappings.get(f"public_id:{public_id}") or existing_mappings.get(
        f"filename:{filename}"
    )
    if existing_mapping and existing_mapping.get("secure_url") and existing_mapping.get("public_id"):
        logger.info(
            "[%d/%d] Skip mapped upload: id=%s filename=%s public_id=%s",
            index + 1,
            total,
            row.get("id", ""),
            filename,
            existing_mapping.get("public_id", ""),
        )
        uploaded_at = row.get("uploaded_at") or now_iso()
        updated = {
            **row,
            "original_image_url": image_url,
            "cloudinary_url": existing_mapping.get("secure_url", ""),
            "cloudinary_public_id": existing_mapping.get("public_id", ""),
            "uploaded_at": uploaded_at,
            "filename": filename,
        }
        mapping = {
            "filename": filename,
            "secure_url": existing_mapping.get("secure_url", ""),
            "public_id": existing_mapping.get("public_id", ""),
        }
        return index, updated, mapping

    if existing_url and existing_public_id:
        logger.info(
            "[%d/%d] Existing upload is outside expected folder, reuploading: id=%s old_public_id=%s expected_public_id=%s",
            index + 1,
            total,
            row.get("id", ""),
            existing_public_id,
            public_id,
        )

    try:
        logger.info(
            "[%d/%d] Uploading: id=%s filename=%s folder=%s public_id=%s image_url=%s",
            index + 1,
            total,
            row.get("id", ""),
            filename,
            folder,
            public_id,
            image_url,
        )
        upload_result = cloudinary.uploader.upload(
            image_url,
            folder=folder or None,
            public_id=public_id_stem,
            overwrite=False,
            resource_type="image",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%d/%d] Upload failed: id=%s filename=%s public_id=%s error=%s",
            index + 1,
            total,
            row.get("id", ""),
            filename,
            public_id,
            exc,
        )
        return index, row, None

    secure_url = upload_result.get("secure_url", "")
    uploaded_at = now_iso()
    uploaded_public_id = upload_result.get("public_id", public_id)
    logger.info(
        "[%d/%d] Uploaded: id=%s filename=%s public_id=%s secure_url=%s",
        index + 1,
        total,
        row.get("id", ""),
        filename,
        uploaded_public_id,
        secure_url,
    )
    updated = {
        **row,
        "original_image_url": image_url,
        "cloudinary_url": secure_url,
        "cloudinary_public_id": uploaded_public_id,
        "uploaded_at": uploaded_at,
        "filename": filename,
    }
    mapping = {
        "filename": filename,
        "secure_url": secure_url,
        "public_id": uploaded_public_id,
    }
    return index, updated, mapping


def run_uploader(
    category: str | None = None,
    clean_csv_path: str | None = None,
    cloudinary_csv_path: str | None = None,
    start_id: int = 10000,
    workers: int = 8,
) -> None:
    load_dotenv()
    _configure_cloudinary()
    ensure_pipeline_dirs()

    clean_path = clean_csv_path or (category_clean_csv_path(category) if category else CLEAN_CSV_PATH)
    mapping_path = cloudinary_csv_path or (
        category_cloudinary_csv_path(category) if category else UPLOADED_CSV_PATH
    )

    rows = _load_clean_rows(clean_path, category)
    if not rows:
        logger.warning(
            "No input rows found at %s. If you already reviewed products, "
            "make sure %s has approved rows.",
            clean_path,
            category_reviewed_csv_path(category) if category else "the reviewed CSV",
        )
        write_csv_rows(mapping_path, CLOUDINARY_COLUMNS, [])
        return

    worker_count = max(1, workers)
    existing_mappings = _load_existing_mappings(mapping_path)
    updated_by_index: dict[int, dict] = {}
    mapping_by_index: dict[int, dict] = {}

    logger.info(
        "Uploading %d rows to Cloudinary with %d workers (%d existing mapping keys)",
        len(rows),
        worker_count,
        len(existing_mappings),
    )
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                _upload_one,
                index,
                len(rows),
                row,
                category,
                start_id,
                existing_mappings,
            )
            for index, row in enumerate(rows)
        ]
        for future in as_completed(futures):
            index, updated, mapping = future.result()
            updated_by_index[index] = updated
            if mapping:
                mapping_by_index[index] = mapping

    updated_rows = [updated_by_index.get(index, row) for index, row in enumerate(rows)]
    mapping_rows = [mapping_by_index[index] for index in sorted(mapping_by_index)]

    write_csv_rows(mapping_path, CLOUDINARY_COLUMNS, mapping_rows)
    write_csv_rows(clean_path, UPDATED_CLEAN_COLUMNS, updated_rows)
    logger.info(
        "Uploaded %d/%d rows -> %s and updated %s",
        len(mapping_rows),
        len(rows),
        mapping_path,
        clean_path,
    )


if __name__ == "__main__":
    run_uploader()
