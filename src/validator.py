"""Pipeline Step 2: Auto-validate product records and image URLs."""

from __future__ import annotations

import logging
from typing import Iterable

import cv2
import imagehash
import numpy as np
from PIL import UnidentifiedImageError

from src.config import (
    BLUR_THRESHOLD,
    HASH_DISTANCE_THRESHOLD,
    MIN_HEIGHT,
    MIN_WIDTH,
    RAW_CSV_PATH,
    VALIDATED_CSV_PATH,
    category_raw_csv_path,
    category_validated_csv_path,
    ensure_pipeline_dirs,
)
from src.utils import (
    download_image_to_memory,
    get_original_image_url,
    now_iso,
    open_image_from_bytes,
    read_csv_rows,
    write_csv_rows,
)

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - optional
    tqdm = None

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

VALIDATED_COLUMNS: list[str] = [
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
    "auto_status",
    "auto_reason",
    "crawled_at",
    "validated_at",
]

REQUIRED_FIELDS = ("name", "source", "source_url", "category")


def _iter_rows(rows: list[dict]) -> Iterable[dict]:
    if tqdm:
        return tqdm(rows, desc="validate", unit="item")
    return rows


def _blur_score(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _reject(reason_counts: dict[str, int], reason: str, row: dict) -> None:
    reason_counts[reason] = reason_counts.get(reason, 0) + 1
    logger.debug("Rejected %s: %s", row.get("id") or row.get("source_url"), reason)


def run_validator(
    category: str | None = None,
    raw_csv_path: str | None = None,
    validated_csv_path: str | None = None,
) -> None:
    ensure_pipeline_dirs()
    raw_path = raw_csv_path or (category_raw_csv_path(category) if category else RAW_CSV_PATH)
    out_path = validated_csv_path or (
        category_validated_csv_path(category) if category else VALIDATED_CSV_PATH
    )

    rows = read_csv_rows(raw_path)
    if not rows:
        logger.warning("No input rows found at %s", raw_path)
        write_csv_rows(out_path, VALIDATED_COLUMNS, [])
        return

    seen_source_urls: set[str] = set()
    seen_image_urls: set[str] = set()
    seen_hashes: list[imagehash.ImageHash] = []
    validated_at = now_iso()
    accepted: list[dict] = []
    reject_counts: dict[str, int] = {}

    for row in _iter_rows(rows):
        image_url = get_original_image_url(row)
        missing = [field for field in REQUIRED_FIELDS if not row.get(field)]
        if missing:
            _reject(reject_counts, f"missing_{missing[0]}", row)
            continue
        if not image_url:
            _reject(reject_counts, "missing_image_url", row)
            continue
        if row.get("source_url") in seen_source_urls or image_url in seen_image_urls:
            _reject(reject_counts, "duplicate_url", row)
            continue

        try:
            data = download_image_to_memory(image_url)
            img = open_image_from_bytes(data).convert("RGB")
        except (UnidentifiedImageError, OSError):
            _reject(reject_counts, "invalid_image_format", row)
            continue
        except Exception as exc:  # noqa: BLE001
            _reject(reject_counts, "download_failed", row)
            logger.debug("Image validate error for %s: %s", image_url, exc)
            continue

        width, height = img.size
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            _reject(reject_counts, "too_small", row)
            continue

        image_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        blur_score = _blur_score(image_bgr)
        if blur_score < BLUR_THRESHOLD:
            _reject(reject_counts, "too_blurry", row)
            continue

        img_hash = imagehash.phash(img)
        if any(img_hash - prev_hash <= HASH_DISTANCE_THRESHOLD for prev_hash in seen_hashes):
            _reject(reject_counts, "duplicate_image", row)
            continue

        seen_source_urls.add(row.get("source_url", ""))
        seen_image_urls.add(image_url)
        seen_hashes.append(img_hash)

        accepted.append(
            {
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "price": row.get("price", ""),
                "brand": row.get("brand", ""),
                "source": row.get("source", ""),
                "source_url": row.get("source_url", ""),
                "original_image_url": image_url,
                "category": row.get("category", category or ""),
                "final_category": row.get("final_category") or row.get("category", category or ""),
                "width": width,
                "height": height,
                "blur_score": f"{blur_score:.2f}",
                "image_hash": str(img_hash),
                "auto_status": "pass",
                "auto_reason": "",
                "crawled_at": row.get("crawled_at", ""),
                "validated_at": validated_at,
            }
        )

    write_csv_rows(out_path, VALIDATED_COLUMNS, accepted)
    logger.info(
        "Validated %d rows -> %s accepted, %s rejected -> %s",
        len(rows),
        len(accepted),
        sum(reject_counts.values()),
        out_path,
    )
    if reject_counts:
        logger.info("Reject counts: %s", reject_counts)


if __name__ == "__main__":
    run_validator()
