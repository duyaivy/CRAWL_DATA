"""CLI entrypoint for Pipeline Step 5: build MongoDB-ready CSV data."""

from __future__ import annotations

import argparse

from src.config import DEFAULT_CATEGORY
from src.final_builder import run_final_builder


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final MongoDB-ready category CSV")
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    args = parser.parse_args()
    run_final_builder(category=args.category)


if __name__ == "__main__":
    main()
