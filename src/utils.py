"""
Shared helpers for the fashion data pipeline.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image

from src.config import DOWNLOAD_USER_AGENT, REQUEST_TIMEOUT_SEC


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def ensure_csv_header(csv_path: str, fieldnames: Iterable[str]) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(fieldnames))
            writer.writeheader()


def read_csv_rows(csv_path: str) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_csv_rows(csv_path: str, fieldnames: Iterable[str], rows: list[dict]) -> None:
    if not rows:
        return
    ensure_csv_header(csv_path, fieldnames)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writerows([{key: row.get(key, "") for key in fieldnames} for row in rows])


def write_csv_rows(csv_path: str, fieldnames: Iterable[str], rows: list[dict]) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fieldnames)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row.get(key, "") for key in fields} for row in rows])


def normalize_category(value: str) -> str:
    return (value or "").strip().lower()


def get_original_image_url(row: dict) -> str:
    return (row.get("original_image_url") or row.get("image_url") or "").strip()


def download_image_to_memory(url: str) -> bytes:
    headers = {"User-Agent": DOWNLOAD_USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.content


def open_image_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def sleep_jitter(min_sec: float, max_sec: float) -> None:
    time.sleep(min_sec + (max_sec - min_sec) * 0.5)
