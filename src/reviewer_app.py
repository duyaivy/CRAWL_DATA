"""Pipeline Step 3: Streamlit human validation app."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    CATEGORIES,
    CLEAN_CSV_PATH,
    REVIEWED_CSV_PATH,
    VALIDATED_CSV_PATH,
    category_clean_csv_path,
    category_reviewed_csv_path,
    category_validated_csv_path,
    ensure_pipeline_dirs,
)
from src.utils import get_original_image_url, now_iso, read_csv_rows, write_csv_rows  # noqa: E402

REVIEWED_COLUMNS: list[str] = [
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
    "human_status",
    "human_reason",
    "reviewed_at",
]

CLEAN_COLUMNS: list[str] = [
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


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--category")
    args, _ = parser.parse_known_args()
    return args


def _paths(category: str | None) -> tuple[str, str, str]:
    if category:
        return (
            category_validated_csv_path(category),
            category_reviewed_csv_path(category),
            category_clean_csv_path(category),
        )
    return VALIDATED_CSV_PATH, REVIEWED_CSV_PATH, CLEAN_CSV_PATH


def _review_key(row: dict, index: int) -> str:
    return row.get("id") or row.get("source_url") or f"row-{index}"


def _load_reviews(reviewed_path: str) -> dict[str, dict]:
    rows = read_csv_rows(reviewed_path)
    return {row.get("id", ""): row for row in rows if row.get("id")}


def _upsert_review(row: dict, reviews: dict[str, dict], status: str, reason: str) -> None:
    row_id = row.get("id", "")
    if not row_id:
        return

    reviews[row_id] = {
        "id": row_id,
        "name": row.get("name", ""),
        "price": row.get("price", ""),
        "brand": row.get("brand", ""),
        "source": row.get("source", ""),
        "source_url": row.get("source_url", ""),
        "original_image_url": get_original_image_url(row),
        "category": row.get("category", ""),
        "final_category": row.get("final_category") or row.get("category", ""),
        "width": row.get("width", ""),
        "height": row.get("height", ""),
        "blur_score": row.get("blur_score", ""),
        "image_hash": row.get("image_hash", ""),
        "auto_status": row.get("auto_status", ""),
        "auto_reason": row.get("auto_reason", ""),
        "human_status": status,
        "human_reason": reason,
        "reviewed_at": now_iso(),
    }


def _export_clean(reviews: dict[str, dict], clean_path: str) -> int:
    clean_rows = [
        {column: row.get(column, "") for column in CLEAN_COLUMNS}
        for row in reviews.values()
        if row.get("human_status") == "approved"
    ]
    write_csv_rows(clean_path, CLEAN_COLUMNS, clean_rows)
    return len(clean_rows)


def main() -> None:
    ensure_pipeline_dirs()
    category = _args().category
    validated_path, reviewed_path, clean_path = _paths(category)

    st.set_page_config(page_title="Fashion Human Validation", layout="wide")
    title_suffix = f" - {category}" if category else ""
    st.title(f"Fashion Human Validation{title_suffix}")

    if not Path(validated_path).exists():
        st.error(f"Missing input file: {validated_path}")
        return

    rows = read_csv_rows(validated_path)
    reviews = _load_reviews(reviewed_path)
    category_options = list(CATEGORIES.keys())

    pending_indices = [
        idx
        for idx, row in enumerate(rows)
        if not reviews.get(row.get("id", ""), {}).get("human_status")
    ]

    st.sidebar.write(f"Input: {validated_path}")
    st.sidebar.write(f"Reviewed: {reviewed_path}")
    st.sidebar.write(f"Clean: {clean_path}")
    st.sidebar.markdown("### Progress")
    st.sidebar.write(f"Total: {len(rows)}")
    st.sidebar.write(f"Reviewed: {len(reviews)}")
    st.sidebar.write(f"Pending: {len(pending_indices)}")
    show_pending_only = st.sidebar.checkbox("Show pending only", value=True)

    current_indices = pending_indices if show_pending_only and pending_indices else list(range(len(rows)))
    if not current_indices:
        st.success("No items to review.")
        return

    page_size = st.sidebar.number_input("Page size", min_value=5, max_value=100, value=25, step=5)
    total_pages = max(1, (len(current_indices) + page_size - 1) // page_size)
    page = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    page_indices = current_indices[(page - 1) * page_size : page * page_size]

    header = st.columns([1.1, 2.4, 1, 1, 1.6, 2, 1])
    for col, label in zip(
        header,
        ("Image", "Name", "Price", "Brand", "Category", "Source URL", "Reject"),
    ):
        col.markdown(f"**{label}**")

    for row_idx in page_indices:
        row = rows[row_idx]
        key = _review_key(row, row_idx)
        row_id = row.get("id", "")
        saved_review = reviews.get(row_id, {})
        cols = st.columns([1.1, 2.4, 1, 1, 1.6, 2, 1])

        image_url = get_original_image_url(row)
        if image_url:
            cols[0].image(image_url, width=96)
        else:
            cols[0].write("")

        cols[1].write(row.get("name", ""))
        cols[2].write(row.get("price", ""))
        cols[3].write(row.get("brand", ""))

        default_category = saved_review.get("final_category") or row.get("final_category") or row.get("category", "")
        options = category_options.copy()
        if default_category and default_category not in options:
            options.append(default_category)
        if not options:
            options = [default_category or "unknown"]
        row["final_category"] = cols[4].selectbox(
            "Final category",
            options=options,
            index=options.index(default_category) if default_category in options else 0,
            key=f"final-{key}",
            label_visibility="collapsed",
        )

        source_url = row.get("source_url", "")
        if source_url:
            cols[5].link_button("Open", source_url)
        else:
            cols[5].write("")
        row["_reject"] = cols[6].checkbox(
            "Reject",
            value=saved_review.get("human_status") == "rejected",
            key=f"reject-{key}",
            label_visibility="collapsed",
        )

        with st.expander(f"Details {row_id}", expanded=False):
            st.write(
                {
                    "source": row.get("source", ""),
                    "source_url": source_url,
                    "original_image_url": image_url,
                    "category": row.get("category", ""),
                    "final_category": row.get("final_category", ""),
                }
            )

    col_a, col_b = st.columns([1, 1])
    if col_a.button("Save Page", type="primary", use_container_width=True):
        for row_idx in page_indices:
            row = rows[row_idx]
            status = "rejected" if row.get("_reject") else "approved"
            _upsert_review(row, reviews, status, "")
        write_csv_rows(reviewed_path, REVIEWED_COLUMNS, list(reviews.values()))
        st.success(f"Saved reviews to {reviewed_path}")

    if col_b.button("Export Clean CSV", use_container_width=True):
        write_csv_rows(reviewed_path, REVIEWED_COLUMNS, list(reviews.values()))
        exported = _export_clean(reviews, clean_path)
        st.success(f"Exported {exported} approved rows to {clean_path}")


if __name__ == "__main__":
    main()
