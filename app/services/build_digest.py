"""Phase 4: filter → rank (curator) → summarize (digest agent) → save → intro.

Checkpoint:  uv run python -m app.services.build_digest
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.agent.curator_agent import CuratorAgent
from app.agent.digest_agent import DigestAgent
from app.agent.email_agent import EmailAgent, EmailIntro
from app.config import HOURS_BACK, SECTIONS
from app.database.create_tables import create_tables
from app.database.repository import get_recent_articles, get_sent_article_ids, replace_unsent_digests
from app.services.filter import filter_articles

log = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Kolkata")


@dataclass
class Story:
    article: object
    rank: int
    score: float
    reason: str
    summary: str
    about_india: bool


@dataclass
class DailyDigest:
    digest_date: date
    sections: dict[str, list[Story]]
    intro: EmailIntro | None


def build_digest(hours: int = HOURS_BACK) -> DailyDigest:
    create_tables()
    digest_date = datetime.now(LOCAL_TZ).date()

    sent = get_sent_article_ids()
    articles = [a for a in get_recent_articles(hours) if a.id not in sent]
    candidates = filter_articles(articles).candidates

    curator, writer = CuratorAgent(), DigestAgent()
    sections: dict[str, list[Story]] = {}
    for section in SECTIONS:
        picks = curator.rank(section, candidates.get(section, []))
        summaries = writer.summarize([a for a, _ in picks])
        sections[section] = [
            Story(
                article=a, rank=i, score=item.score, reason=item.reason,
                summary=summaries[a.id], about_india=item.about_india,
            )
            for i, (a, item) in enumerate(picks, start=1)
        ]
        log.info("%s: %d stories chosen from %d candidates", section, len(picks), len(candidates.get(section, [])))

    rows = [
        {
            "article_id": s.article.id, "section": section, "rank": s.rank,
            "score": s.score, "summary": s.summary, "about_india": s.about_india,
        }
        for section, stories in sections.items()
        for s in stories
    ]
    replace_unsent_digests(digest_date, rows)

    intro = None
    if rows:
        headlines = {sec: [s.article.title for s in stories] for sec, stories in sections.items() if stories}
        intro = EmailAgent().write_intro(digest_date, headlines)
    return DailyDigest(digest_date=digest_date, sections=sections, intro=intro)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank and summarize today's stories.")
    parser.add_argument("--hours", type=int, default=HOURS_BACK)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    digest = build_digest(args.hours)

    print(f"\n========== Daily digest — {digest.digest_date:%A, %d %B %Y} ==========")
    if digest.intro:
        print(f"\n{digest.intro.greeting}\n{digest.intro.intro}")
    for section, stories in digest.sections.items():
        india = sum(s.about_india for s in stories)
        print(f"\n---------- {section.upper()} ({len(stories)} stories, {india} about India) ----------")
        for s in stories:
            a = s.article
            flag = "[India] " if s.about_india else ""
            print(f"\n{s.rank}. {flag}{a.title}")
            print(f"   {a.publisher or a.source} · score {s.score:g} · {s.reason}")
            print(f"   {s.summary}")
            print(f"   {a.url}")


if __name__ == "__main__":
    main()
