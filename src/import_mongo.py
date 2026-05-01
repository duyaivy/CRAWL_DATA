"""CLI entrypoint for Pipeline Step 6: import final CSV data into MongoDB."""

from __future__ import annotations

import argparse

from src.config import DEFAULT_CATEGORY
from src.db_importer import run_db_importer


def main() -> None:
    parser = argparse.ArgumentParser(description="Import final category CSV into MongoDB")
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    args = parser.parse_args()
    run_db_importer(category=args.category)


if __name__ == "__main__":
    main()
