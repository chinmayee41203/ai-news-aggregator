"""Export the latest *sent* edition as a small public JSON file (latest.json).

The GitHub workflow publishes this file to the repo's `feed` branch after each
morning's email, so a website (the portfolio) can show "Today's edition".
It contains only public news: headlines, our own summaries, outlet names and
links — no names, email addresses or settings.

    uv run python -m app.services.export_feed            # writes data/latest.json
    uv run python -m app.services.export_feed --out x.json
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.config import ROOT_DIR, SECTIONS, TIMEZONE, load_sources
from app.database.connection import get_session
from app.database.models import Article, Digest
from app.services.email_template import SECTION_TITLES

log = logging.getLogger(__name__)

DEFAULT_OUT = ROOT_DIR / "data" / "latest.json"


def export_latest(out: Path = DEFAULT_OUT) -> Path | None:
    """Write the most recent sent edition to `out`. Returns the path, or None if
    nothing has been sent yet."""
    with get_session() as session:
        latest_date = session.execute(
            select(func.max(Digest.digest_date)).where(Digest.sent_at.is_not(None))
        ).scalar_one()
        if latest_date is None:
            log.info("No sent edition yet — nothing to export")
            return None
        rows = session.execute(
            select(Digest, Article)
            .join(Article, Article.id == Digest.article_id)
            .where(Digest.digest_date == latest_date, Digest.sent_at.is_not(None))
            .order_by(Digest.section, Digest.rank)
        ).all()

    publishers = {s["name"]: s.get("publisher", "") for s in load_sources()}
    by_section: dict[str, list[dict]] = {s: [] for s in SECTIONS}
    for digest, article in rows:
        by_section.setdefault(digest.section, []).append(
            {
                "title": article.title,
                "url": article.url,
                "outlet": article.publisher or publishers.get(article.source) or article.source,
                "summary": digest.summary,
                "about_india": digest.about_india,
            }
        )

    feed = {
        "date": latest_date.isoformat(),
        "timezone": TIMEZONE.key,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sections": [
            {"key": key, "title": SECTION_TITLES.get(key, key.title()), "stories": stories}
            for key, stories in by_section.items()
            if stories
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Exported %s edition (%d stories) to %s", latest_date, len(rows), out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the latest sent edition as JSON.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    export_latest(args.out)


if __name__ == "__main__":
    main()
