import argparse
import subprocess
import sys

from src.config import DEFAULT_CATEGORY
from src.crawler import run_crawler
from src.db_importer import run_db_importer
from src.final_builder import run_final_builder
from src.uploader import run_uploader
from src.validator import run_validator


def main() -> None:
    parser = argparse.ArgumentParser(description="Fashion image data pipeline")
    parser.add_argument(
        "step",
        choices=["crawl", "validate", "human-validate", "upload", "build-final", "import-db", "all"],
        help="Pipeline step to run",
    )
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    parser.add_argument("--target", type=int)
    parser.add_argument("--keyword", action="append", dest="keywords")

    args = parser.parse_args()

    if args.step == "crawl":
        run_crawler(category=args.category, target=args.target, keywords=args.keywords)
    elif args.step == "validate":
        run_validator(category=args.category)
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
        run_crawler(category=args.category, target=args.target, keywords=args.keywords)
        run_validator(category=args.category)
        run_uploader(category=args.category)
        run_final_builder(category=args.category)
        run_db_importer(category=args.category)


if __name__ == "__main__":
    main()
