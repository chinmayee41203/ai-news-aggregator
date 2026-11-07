"""Phase 5: turn today's unsent digest into an email, send it, mark it sent.

Preview only (writes data/digest_preview.html, sends nothing):
    uv run python -m app.services.process_email --preview
Send:
    uv run python -m app.services.process_email
"""

import argparse
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import ROOT_DIR, SECTIONS, load_sources
from app.database.repository import get_unsent_digests, mark_digests_sent
from app.profiles.user_profile import USER_PROFILE
from app.services.email import send_email
from app.services.email_template import EmailStory, build_html, build_subject, build_text

log = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Kolkata")
PREVIEW_FILE = ROOT_DIR / "data" / "digest_preview.html"  # data/ is gitignored


def _intro(digest_date: date, sections: dict[str, list[EmailStory]], intro=None) -> tuple[str, str]:
    """Use the intro from build_digest if given; otherwise ask Gemini; if that
    fails, fall back to a plain greeting so the email still goes out."""
    if intro is not None:
        return intro.greeting, intro.intro
    try:
        from app.agent.email_agent import EmailAgent

        written = EmailAgent().write_intro(
            digest_date, {s: [st.title for st in stories] for s, stories in sections.items() if stories}
        )
        return written.greeting, written.intro
    except Exception as exc:
        log.warning("Intro could not be written (%s); using a plain greeting", exc)
        return f"Good morning, {USER_PROFILE['name']}!", "Here are today's top stories."


def process_email(digest_date: date | None = None, preview: bool = False, intro=None) -> int:
    """Returns the number of stories emailed (0 if there was nothing to send)."""
    digest_date = digest_date or datetime.now(LOCAL_TZ).date()
    rows = get_unsent_digests(digest_date)
    if not rows:
        log.info("No unsent stories for %s — nothing to email", digest_date)
        return 0

    # Outlet names from sources.yaml (also covers rows saved before `publisher` existed).
    publishers = {s["name"]: s.get("publisher", "") for s in load_sources()}
    sections: dict[str, list[EmailStory]] = {s: [] for s in SECTIONS}
    for digest, article in rows:
        sections.setdefault(digest.section, []).append(
            EmailStory(
                title=article.title,
                url=article.url,
                outlet=article.publisher or publishers.get(article.source) or article.source,
                summary=digest.summary,
                about_india=digest.about_india,
            )
        )

    greeting, intro_text = _intro(digest_date, sections, intro)
    html = build_html(digest_date, greeting, intro_text, sections)
    text = build_text(digest_date, greeting, intro_text, sections)

    if preview:
        PREVIEW_FILE.parent.mkdir(exist_ok=True)
        Path(PREVIEW_FILE).write_text(html, encoding="utf-8")
        log.info("Preview written to %s (nothing sent)", PREVIEW_FILE)
        return len(rows)

    send_email(build_subject(digest_date), html, text)
    mark_digests_sent([d.id for d, _ in rows])
    log.info("Email sent with %d stories; marked as sent", len(rows))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Email today's digest.")
    parser.add_argument("--preview", action="store_true", help="write an HTML preview instead of sending")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    process_email(preview=args.preview)


if __name__ == "__main__":
    main()
