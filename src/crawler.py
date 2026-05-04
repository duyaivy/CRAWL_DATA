"""Pipeline Step 1: crawl product metadata and image URLs.

This module is the stable crawler entrypoint. It dispatches to the source
specific crawlers in ``src.crawler_lazada``, ``src.crawler_tiki``, and
``src.crawler_asos``.
"""

from __future__ import annotations

from typing import Literal

CrawlerSource = Literal["lazada", "tiki", "asos"]

SOURCES: tuple[CrawlerSource, ...] = ("lazada", "tiki", "asos")


def run_crawler(
    category: str | None = None,
    target: int | None = None,
    keywords: list[str] | None = None,
    raw_csv_path: str | None = None,
    max_pages: int | None = None,
    source: CrawlerSource | None = None,
) -> None:
    if source is None:
        from src.config import CRAWLER_SOURCE

        source = CRAWLER_SOURCE

    source = source.lower()

    if source == "lazada":
        try:
            from src.crawler_lazada import run_crawler as run_lazada_crawler
        except ModuleNotFoundError:
            from crawler_lazada import run_crawler as run_lazada_crawler

        run_lazada_crawler(
            category=category,
            target=target,
            keywords=keywords,
            raw_csv_path=raw_csv_path,
            max_pages=max_pages,
        )
        return

    if source == "tiki":
        try:
            from src.crawler_tiki import run_crawler as run_tiki_crawler
        except ModuleNotFoundError:
            from crawler_tiki import run_crawler as run_tiki_crawler

        run_tiki_crawler(
            category=category,
            target=target,
            keywords=keywords,
            raw_csv_path=raw_csv_path,
            max_pages=max_pages,
        )
        return

    if source == "asos":
        try:
            from src.crawler_asos import run_crawler as run_asos_crawler
        except ModuleNotFoundError:
            from crawler_asos import run_crawler as run_asos_crawler

        run_asos_crawler(
            category=category,
            target=target,
            keywords=keywords,
            raw_csv_path=raw_csv_path,
            max_pages=max_pages,
        )
        return

    raise ValueError(
        f"Unknown crawler source: {source}. Choose one of: {', '.join(SOURCES)}"
    )


def main() -> None:
    run_crawler()


if __name__ == "__main__":
    main()


__all__ = ["run_crawler"]
