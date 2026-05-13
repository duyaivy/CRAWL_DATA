"""Sync Cloudinary image folders into local dataset CSV files.

This script uses Cloudinary Admin API metadata only. It does not HEAD/check
each delivery URL, so it is much faster than validating every secure_url.

Examples:
    python scripts/sync_dataset_csv.py
    python scripts/sync_dataset_csv.py --category ao_khoac
    python scripts/sync_dataset_csv.py --categories ao_khoac quan_short
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import cloudinary
import cloudinary.api
from dotenv import load_dotenv


CSV_COLUMNS = ["filename", "secure_url", "public_id"]
DEFAULT_OUTPUT_DIR = Path("cloudinary_links") / "total"


def configure_cloudinary() -> None:
    load_dotenv()

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    api_key = os.getenv("CLOUDINARY_API_KEY", "")
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "")
    if not all((cloud_name, api_key, api_secret)):
        raise RuntimeError(
            "Missing Cloudinary config. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def read_existing_rows(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        return {}

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {
            row.get("public_id", ""): row
            for row in reader
            if row.get("public_id")
        }


def write_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in CSV_COLUMNS} for row in rows])


def cloudinary_folder(category: str, folder_prefix: str = "") -> str:
    return "/".join(
        part.strip("/")
        for part in (folder_prefix, category)
        if part and part.strip("/")
    )


def filename_from_resource(resource: dict[str, object], existing_row: dict[str, str] | None) -> str:
    if existing_row and existing_row.get("filename"):
        return existing_row["filename"]

    public_id = str(resource.get("public_id", ""))
    stem = Path(public_id).name
    fmt = str(resource.get("format") or "").strip()
    return f"{stem}.{fmt}" if fmt else stem


def list_folder_resources(folder: str) -> list[dict[str, object]]:
    resources: list[dict[str, object]] = []
    next_cursor: str | None = None
    prefix = f"{folder.strip('/')}/" if folder else ""

    while True:
        response = cloudinary.api.resources(
            resource_type="image",
            type="upload",
            prefix=prefix,
            max_results=500,
            next_cursor=next_cursor,
        )
        resources.extend(response.get("resources", []))
        next_cursor = response.get("next_cursor")
        if not next_cursor:
            break

    return resources


def sync_category(category: str, output_dir: Path, folder_prefix: str = "") -> int:
    csv_path = output_dir / f"{category}.csv"
    existing_by_public_id = read_existing_rows(csv_path)
    folder = cloudinary_folder(category, folder_prefix)
    resources = list_folder_resources(folder)

    rows = []
    for resource in sorted(resources, key=lambda item: str(item.get("public_id", ""))):
        public_id = str(resource.get("public_id", ""))
        if not public_id:
            continue

        existing_row = existing_by_public_id.get(public_id)
        rows.append(
            {
                "filename": filename_from_resource(resource, existing_row),
                "secure_url": str(resource.get("secure_url", "")),
                "public_id": public_id,
            }
        )

    write_rows(csv_path, rows)
    print(f"Synced {len(rows)} images from Cloudinary folder '{folder}' -> {csv_path}")
    return len(rows)


def categories_from_output_dir(output_dir: Path) -> list[str]:
    return sorted(path.stem for path in output_dir.glob("*.csv") if path.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync Cloudinary folders into cloudinary_links/total CSV files."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory containing/writing category CSV files.",
    )
    parser.add_argument(
        "--category",
        help="Sync one category folder, e.g. ao_khoac.",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="Sync selected category folders, e.g. ao_khoac quan_short.",
    )
    parser.add_argument(
        "--folder-prefix",
        default="",
        help="Optional Cloudinary parent folder before category names.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_cloudinary()

    if args.category and args.categories:
        raise SystemExit("Use either --category or --categories, not both.")

    if args.category:
        categories = [args.category]
    elif args.categories:
        categories = args.categories
    else:
        categories = categories_from_output_dir(args.output_dir)

    if not categories:
        raise SystemExit(
            f"No categories found. Add CSV files to {args.output_dir} or pass --category."
        )

    total = 0
    for category in categories:
        total += sync_category(category, args.output_dir, args.folder_prefix)

    print(f"Done. Synced {len(categories)} categories, {total} images total.")


if __name__ == "__main__":
    main()
