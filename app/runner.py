"""Runs every source in sources.yaml and collects recent articles.

Phase 1 checkpoint:  uv run python -m app.runner --dry-run
(Saving to the database is added in Phase 2.)
"""

import argparse
import logging
from collections import defaultdict

from app.config import HOURS_BACK, SECTIONS, load_sources
from app.scrapers.base import Article, BaseScraper
from app.scrapers.google_news import GoogleNewsScraper
from app.scrapers.guardian import GuardianScraper
from app.scrapers.rss import RSSScraper
from app.scrapers.youtube import YouTubeScraper

log = logging.getLogger(__name__)

# type in sources.yaml -> scraper class
SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "rss": RSSScraper,
    "google_news": GoogleNewsScraper,
    "guardian": GuardianScraper,
    "youtube": YouTubeScraper,
}


def build_scrapers() -> list[BaseScraper]:
    scrapers = []
    for src in load_sources():
        cls = SCRAPER_REGISTRY.get(src["type"])
        if cls is None:
            raise ValueError(f"{src['name']}: unknown type '{src['type']}'")
        scrapers.append(cls(**src))
    return scrapers


def run_scrapers(hours_back: int = HOURS_BACK) -> tuple[list[Article], dict[str, int | str]]:
    """Run all scrapers. A failing source is logged and skipped."""
    articles: list[Article] = []
    report: dict[str, int | str] = {}
    for scraper in build_scrapers():
        try:
            found = scraper.get_articles(hours_back)
            articles.extend(found)
            report[scraper.name] = len(found)
        except Exception as exc:
            log.warning("%s failed: %s", scraper.name, exc)
            report[scraper.name] = f"FAILED ({exc.__class__.__name__})"
    return articles, report


def print_summary(articles: list[Article], report: dict, show: int) -> None:
    print("\nPer source:")
    for name, count in report.items():
        print(f"  {name:<24} {count}")

    grouped: dict[tuple[str, str], list[Article]] = defaultdict(list)
    for a in articles:
        grouped[(a.section, a.region)].append(a)

    for section in SECTIONS:
        for region in ("global", "india"):
            items = sorted(grouped[(section, region)], key=lambda a: a.published_at, reverse=True)
            print(f"\n=== {section.upper()} / {region} — {len(items)} articles ===")
            for a in items[:show]:
                who = a.publisher or a.source
                print(f"  [{a.published_at:%d %b %H:%M} UTC] {a.title}  ({who})")
    print(f"\nTotal: {len(articles)} articles")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect recent news from all sources.")
    parser.add_argument("--hours", type=int, default=HOURS_BACK, help="look back this many hours")
    parser.add_argument("--show", type=int, default=5, help="headlines to print per group")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only print results (the database is added in Phase 2, so this is the only mode for now)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    articles, report = run_scrapers(args.hours)
    print_summary(articles, report, args.show)


if __name__ == "__main__":
    main()
