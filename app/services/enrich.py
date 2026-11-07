"""Phase 3 enrichment: download transcripts / full text for AI sources only
(sources with `fetch_content: true` in sources.yaml — YouTube and Anthropic).

News publishers (NYT, CNN, Guardian, Times Now, TOI) are never downloaded:
we only use the headline and description their feeds provide.

Run:  uv run python -m app.services.enrich
"""

import argparse
import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
import trafilatura

from app.config import REQUEST_TIMEOUT, USER_AGENT, load_sources
from app.database.repository import get_pending_content, mark_content_skipped, set_content
from app.scrapers.youtube import get_transcript

log = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 15_000  # keeps Gemini requests (and the database) small
PAGE_DELAY_SECONDS = 1.0

_robots_cache: dict[str, RobotFileParser] = {}


def allowed_by_robots(url: str) -> bool:
    """Respect the site's robots.txt for our User-Agent."""
    parts = urlsplit(url)
    host = f"{parts.scheme}://{parts.netloc}"
    if host not in _robots_cache:
        parser = RobotFileParser()
        try:
            r = requests.get(f"{host}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
            parser.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            parser.parse([])
        _robots_cache[host] = parser
    return _robots_cache[host].can_fetch(USER_AGENT, url)


def fetch_page_text(url: str) -> str | None:
    if not allowed_by_robots(url):
        log.info("robots.txt disallows %s", url)
        return None
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        log.info("Could not download %s: %s", url, exc)
        return None
    return trafilatura.extract(r.text, url=url, include_comments=False, include_tables=False)


def enrich(hours: int = 48) -> dict[str, int]:
    sources = load_sources()
    eligible = {s["name"]: s["type"] for s in sources if s.get("fetch_content")}
    skipped = mark_content_skipped(list(eligible))

    stats = {"ok": 0, "unavailable": 0, "skipped_not_ai": skipped}
    for article in get_pending_content(list(eligible), hours):
        if eligible[article.source] == "youtube":
            text = get_transcript(article.external_id) if article.external_id else None
        else:
            text = fetch_page_text(article.url)
            time.sleep(PAGE_DELAY_SECONDS)

        if text and text.strip():
            set_content(article.id, text.strip()[:MAX_CONTENT_CHARS], "ok")
            stats["ok"] += 1
            log.info("ok           %s", article.title[:80])
        else:
            # Marked so we never retry it in a loop; Phase 4 falls back to the description.
            set_content(article.id, None, "unavailable")
            stats["unavailable"] += 1
            log.info("unavailable  %s", article.title[:80])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch transcripts / full text for AI sources.")
    parser.add_argument("--hours", type=int, default=48, help="only items published in this window")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    stats = enrich(args.hours)
    print(
        f"\nContent fetched: {stats['ok']} | unavailable: {stats['unavailable']} | "
        f"marked 'skipped' (news publishers): {stats['skipped_not_ai']}"
    )


if __name__ == "__main__":
    main()
