import argparse
import re
import subprocess
import sys

from src.config import DEFAULT_CATEGORY
from src.crawler import run_crawler
from src.db_importer import run_db_importer
from src.final_builder import run_final_builder
from src.uploader import run_uploader
from src.validator import run_validator


def _normalize_skip_page_args(argv: list[str]) -> list[str]:
    normalized: list[str] = []
    for arg in argv:
        match = re.fullmatch(r"--skip-(\d+)", arg)
        if match:
            normalized.extend(["--skip-pages", match.group(1)])
        else:
            normalized.append(arg)
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Fashion image data pipeline")
    parser.add_argument(
        "step",
        choices=["crawl", "validate", "human-validate", "upload", "build-final", "import-db", "all"],
        help="Pipeline step to run",
    )
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    parser.add_argument("--target", type=int)
    parser.add_argument("--keyword", dest="keywords", action="append")
    parser.add_argument("--raw-csv-path")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument(
        "--skip-pages",
        type=int,
        default=0,
        help="For Lazada crawl: skip the first N search result pages before crawling.",
    )
    parser.add_argument(
        "--auto-pass-all",
        action="store_true",
        help="For validate/all: mark every raw row as passed without downloading or checking images.",
    )

    args = parser.parse_args(_normalize_skip_page_args(sys.argv[1:]))

    if args.step == "crawl":
        run_crawler(
            category=args.category,
            target=args.target,
            keywords=args.keywords,
            raw_csv_path=args.raw_csv_path,
            max_pages=args.max_pages,
            skip_pages=args.skip_pages,
        )
    elif args.step == "validate":
        run_validator(category=args.category, auto_pass_all=args.auto_pass_all)
    elif args.step == "human-validate":
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/reviewer_app.py",
                "--",
                "--category",
                args.category,
            ],
            check=True,
        )
    elif args.step == "upload":
        run_uploader(category=args.category)
    elif args.step == "build-final":
        run_final_builder(category=args.category)
    elif args.step == "import-db":
        run_db_importer(category=args.category)
    elif args.step == "all":
        run_crawler(
            category=args.category,
            target=args.target,
            keywords=args.keywords,
            raw_csv_path=args.raw_csv_path,
            max_pages=args.max_pages,
            skip_pages=args.skip_pages,
        )
        run_validator(category=args.category, auto_pass_all=args.auto_pass_all)
        run_uploader(category=args.category)
        run_final_builder(category=args.category)
        run_db_importer(category=args.category)


if __name__ == "__main__":
    main()
