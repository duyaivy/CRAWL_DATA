"""CLI entrypoint for Pipeline Step 4: upload clean images to Cloudinary."""

from __future__ import annotations

import argparse

from src.config import DEFAULT_CATEGORY
from src.uploader import run_uploader


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload clean category images to Cloudinary")
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    parser.add_argument("--start-id", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    run_uploader(category=args.category, start_id=args.start_id, workers=args.workers)


if __name__ == "__main__":
    main()
