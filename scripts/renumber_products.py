"""Renumber product CSV rows and optionally attach Cloudinary mappings.

Examples:
    python scripts/renumber_products.py --category sweater_hoodie
    python scripts/renumber_products.py --category sweater_hoodie --attach-cloudinary --in-place
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_PRODUCT_COLUMNS = [
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

CLOUDINARY_COLUMNS = ["filename", "secure_url", "public_id", "original_image_url"]
PRODUCT_CLOUDINARY_COLUMNS = [
    "cloudinary_url",
    "cloudinary_public_id",
    "uploaded_at",
    "filename",
]


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return [], []
        return list(reader.fieldnames), list(reader)


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in rows])


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".bak_{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def numbered_id(index: int, start: int, width: int) -> str:
    return str(start + index).zfill(width)


def output_path_for(input_path: Path, suffix: str) -> Path:
    return input_path.with_name(f"{input_path.stem}{suffix}{input_path.suffix}")


def merge_fieldnames(fieldnames: list[str], extra_columns: list[str]) -> list[str]:
    merged = list(fieldnames or DEFAULT_PRODUCT_COLUMNS)
    for column in extra_columns:
        if column not in merged:
            merged.append(column)
    return merged


def renumber_products(
    product_csv: Path,
    output_csv: Path,
    start_id: int,
    id_width: int,
    cloudinary_csv: Path | None = None,
    cloudinary_output_csv: Path | None = None,
    strict_cloudinary_count: bool = False,
) -> tuple[int, int, Path | None]:
    product_fields, product_rows = read_csv_rows(product_csv)
    if "id" not in product_fields:
        product_fields = ["id", *product_fields]

    for index, row in enumerate(product_rows):
        row["id"] = numbered_id(index, start_id, id_width)

    attached_count = 0
    mapping_output_path = None
    if cloudinary_csv:
        mapping_fields, mapping_rows = read_csv_rows(cloudinary_csv)
        missing_mapping_fields = [
            column for column in ("filename", "secure_url", "public_id") if column not in mapping_fields
        ]
        if missing_mapping_fields:
            raise ValueError(
                f"{cloudinary_csv} is missing columns: {', '.join(missing_mapping_fields)}"
            )

        if strict_cloudinary_count and len(mapping_rows) != len(product_rows):
            raise ValueError(
                "Cloudinary row count does not match product row count: "
                f"{len(mapping_rows)} != {len(product_rows)}"
            )

        attached_count = min(len(product_rows), len(mapping_rows))
        product_fields = merge_fieldnames(product_fields, PRODUCT_CLOUDINARY_COLUMNS)

        normalized_mapping_rows = []
        for index, mapping in enumerate(mapping_rows):
            if index < len(product_rows):
                product = product_rows[index]
                product["filename"] = mapping.get("filename", "")
                product["cloudinary_url"] = mapping.get("secure_url", "")
                product["cloudinary_public_id"] = mapping.get("public_id", "")
                product.setdefault("uploaded_at", "")
                original_image_url = product.get("original_image_url", "")
            else:
                original_image_url = mapping.get("original_image_url", "")

            normalized_mapping_rows.append(
                {
                    "filename": mapping.get("filename", ""),
                    "secure_url": mapping.get("secure_url", ""),
                    "public_id": mapping.get("public_id", ""),
                    "original_image_url": original_image_url,
                }
            )

        mapping_output_path = cloudinary_output_csv or output_path_for(
            cloudinary_csv, "_renumbered"
        )
        write_csv_rows(mapping_output_path, CLOUDINARY_COLUMNS, normalized_mapping_rows)

    write_csv_rows(output_csv, product_fields, product_rows)
    return len(product_rows), attached_count, mapping_output_path


def category_clean_path(category: str) -> Path:
    return Path("data") / "clean" / f"{category}_clean.csv"


def category_cloudinary_path(category: str) -> Path:
    preferred = Path("cloudinary_links") / f"{category}.csv"
    if preferred.exists():
        return preferred
    return Path("data") / "cloudinary" / f"{category}_cloudinary.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Renumber product CSV ids and optionally attach Cloudinary links by row order."
    )
    parser.add_argument("--category", default="sweater_hoodie")
    parser.add_argument("--product-csv", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--id-width", type=int, default=6)
    parser.add_argument("--attach-cloudinary", action="store_true")
    parser.add_argument("--cloudinary-csv", type=Path)
    parser.add_argument("--cloudinary-output-csv", type=Path)
    parser.add_argument("--strict-cloudinary-count", action="store_true")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the product CSV after creating a .bak timestamp backup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    product_csv = args.product_csv or category_clean_path(args.category)
    output_csv = product_csv if args.in_place else (
        args.output_csv or output_path_for(product_csv, "_renumbered")
    )

    cloudinary_csv = None
    if args.attach_cloudinary:
        cloudinary_csv = args.cloudinary_csv or category_cloudinary_path(args.category)

    product_backup = backup_file(product_csv) if args.in_place else None
    cloudinary_backup = None
    if args.in_place and cloudinary_csv and args.cloudinary_output_csv is None:
        cloudinary_backup = backup_file(cloudinary_csv)

    cloudinary_output_csv = args.cloudinary_output_csv
    if args.in_place and cloudinary_csv and cloudinary_output_csv is None:
        cloudinary_output_csv = cloudinary_csv

    total, attached_count, mapping_output_path = renumber_products(
        product_csv=product_csv,
        output_csv=output_csv,
        start_id=args.start_id,
        id_width=args.id_width,
        cloudinary_csv=cloudinary_csv,
        cloudinary_output_csv=cloudinary_output_csv,
        strict_cloudinary_count=args.strict_cloudinary_count,
    )

    print(f"Renumbered {total} product rows -> {output_csv}")
    if product_backup:
        print(f"Product backup: {product_backup}")
    if cloudinary_csv:
        print(f"Attached {attached_count} Cloudinary rows by row order")
        print(f"Cloudinary output: {mapping_output_path}")
    if cloudinary_backup:
        print(f"Cloudinary backup: {cloudinary_backup}")


if __name__ == "__main__":
    main()
