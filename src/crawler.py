"""Pipeline Step 1: crawl product metadata and image URLs.

This module intentionally stays as the stable public entrypoint. The Lazada
implementation lives in ``src.crawler_lazada`` and is called by ``main.py``.
"""

from src.crawler_lazada import run_crawler

__all__ = ["run_crawler"]
