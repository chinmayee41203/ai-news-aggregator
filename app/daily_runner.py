"""The whole daily pipeline in one run:
create tables → collect → fetch AI content → filter/rank/summarize → email → clean up.

    uv run main.py                  full run, sends the email
    uv run main.py --no-send        everything except sending (writes a preview)
    uv run main.py --skip-if-sent   do nothing if today's email already went out
                                    (used by the scheduled retry run)
    uv run main.py --not-before 08:00
                                    do nothing if it's earlier than 08:00 in TIMEZONE
                                    (GitHub's schedule is UTC-only; this keeps 9 AM
                                    Eastern correct through daylight-saving changes)
"""

import argparse
import logging
import os
import time
from datetime import datetime, time as dtime

from app.config import HOURS_BACK, TIMEZONE

log = logging.getLogger("daily_runner")

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))  # older articles are deleted


def run(
    hours: int = HOURS_BACK,
    send: bool = True,
    skip_if_sent: bool = False,
    not_before: dtime | None = None,
) -> int:
    now = datetime.now(TIMEZONE)
    if not_before and now.time() < not_before:
        log.info("It's %s in %s, before %s — skipping this run", now.strftime("%H:%M"), TIMEZONE.key, not_before.strftime("%H:%M"))
        return 0

    from app.database.connection import describe_database
    from app.database.create_tables import create_tables
    from app.database.repository import delete_old_articles, digest_already_sent, save_articles
    from app.runner import run_scrapers
    from app.services.build_digest import build_digest
    from app.services.enrich import enrich
    from app.services.process_email import process_email

    started = time.monotonic()

    log.info("1/6 Preparing database (%s)", describe_database())
    create_tables()

    today = now.date()
    if skip_if_sent and digest_already_sent(today):
        log.info("Today's digest (%s) was already sent — nothing to do", today)
        return 0

    log.info("2/6 Collecting news (last %dh)", hours)
    articles, report = run_scrapers(hours)
    failed = [name for name, n in report.items() if isinstance(n, str)]
    inserted, already, dupes = save_articles(articles)
    log.info("    %d new, %d already stored, %d duplicates%s", inserted, already, dupes,
             f"; failed sources: {', '.join(failed)}" if failed else "")

    log.info("3/6 Fetching transcripts / full text for AI sources")
    stats = enrich(hours=max(hours, 48))
    log.info("    %d fetched, %d unavailable", stats["ok"], stats["unavailable"])

    log.info("4/6 Ranking and summarizing with Gemini")
    digest = build_digest(hours)
    total = sum(len(s) for s in digest.sections.values())
    log.info("    %d stories chosen", total)

    log.info("5/6 %s", "Sending email" if send else "Writing preview (not sending)")
    sent = process_email(digest.digest_date, preview=not send, intro=digest.intro)

    if send and sent:
        from app.services.export_feed import export_latest

        export_latest()  # data/latest.json — the workflow publishes it to the `feed` branch

    log.info("6/6 Deleting articles older than %d days", RETENTION_DAYS)
    log.info("    %d deleted", delete_old_articles(RETENTION_DAYS))

    log.info("Done in %.0fs", time.monotonic() - started)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full daily news pipeline.")
    parser.add_argument("--hours", type=int, default=HOURS_BACK)
    parser.add_argument("--no-send", action="store_true", help="write a preview instead of emailing")
    parser.add_argument("--skip-if-sent", action="store_true", help="exit if today's email was already sent")
    parser.add_argument("--not-before", metavar="HH:MM", help="exit if local time (TIMEZONE) is earlier than this")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    not_before = datetime.strptime(args.not_before, "%H:%M").time() if args.not_before else None
    run(hours=args.hours, send=not args.no_send, skip_if_sent=args.skip_if_sent, not_before=not_before)


if __name__ == "__main__":
    main()
