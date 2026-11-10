"""All reads/writes to the database go through here."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.database.connection import get_session
from app.database.models import Article, Digest
from app.scrapers.base import Article as ScrapedArticle


def save_articles(articles: list[ScrapedArticle]) -> tuple[int, int, int]:
    """Insert new articles; skip ones whose URL is already stored.

    Returns (inserted, already_stored, duplicates_in_this_run).
    """
    if not articles:
        return 0, 0, 0

    # The same URL can appear in two feeds in one run — keep the first.
    unique = {a.url: a for a in reversed(articles)}
    rows = [a.model_dump() for a in unique.values()]

    stmt = (
        insert(Article)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["url"])
        .returning(Article.id)
    )
    with get_session() as session:
        inserted = len(session.execute(stmt).all())
    return inserted, len(rows) - inserted, len(articles) - len(rows)


def _cutoff(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def get_recent_articles(hours: int) -> list[Article]:
    """Articles published in the last `hours`, newest first."""
    stmt = (
        select(Article)
        .where(Article.published_at >= _cutoff(hours))
        .order_by(Article.published_at.desc())
    )
    with get_session() as session:
        return list(session.scalars(stmt))


def mark_content_skipped(eligible_sources: list[str]) -> int:
    """Pending rows from sources we never download (news publishers) -> 'skipped'."""
    stmt = (
        update(Article)
        .where(Article.content_status == "pending", Article.source.not_in(eligible_sources))
        .values(content_status="skipped")
    )
    with get_session() as session:
        return session.execute(stmt).rowcount


def get_pending_content(eligible_sources: list[str], hours: int) -> list[Article]:
    """Recent rows from AI sources that still need a transcript / full text."""
    stmt = select(Article).where(
        Article.content_status == "pending",
        Article.source.in_(eligible_sources),
        Article.published_at >= _cutoff(hours),
    )
    with get_session() as session:
        return list(session.scalars(stmt))


def save_section_labels(labels: dict[int, str]) -> None:
    """Store Gemini's section label per article id."""
    if not labels:
        return
    with get_session() as session:
        for article_id, label in labels.items():
            session.execute(update(Article).where(Article.id == article_id).values(section_label=label))


def set_content(article_id: int, content: str | None, status: str) -> None:
    stmt = update(Article).where(Article.id == article_id).values(content=content, content_status=status)
    with get_session() as session:
        session.execute(stmt)


def get_sent_article_ids() -> set[int]:
    """Articles already included in an email that was sent — never repeat them."""
    stmt = select(Digest.article_id).where(Digest.sent_at.is_not(None))
    with get_session() as session:
        return set(session.scalars(stmt))


def replace_unsent_digests(digest_date: date, rows: list[dict]) -> int:
    """Store today's picks. Re-running the same day replaces the unsent picks
    instead of piling up duplicates. Returns the number of rows saved."""
    with get_session() as session:
        session.execute(
            delete(Digest).where(Digest.digest_date == digest_date, Digest.sent_at.is_(None))
        )
        session.add_all(Digest(digest_date=digest_date, **row) for row in rows)
    return len(rows)


def get_unsent_digests(digest_date: date) -> list[tuple[Digest, Article]]:
    """Today's picks that haven't been emailed yet, by section and rank."""
    stmt = (
        select(Digest, Article)
        .join(Article, Article.id == Digest.article_id)
        .where(Digest.digest_date == digest_date, Digest.sent_at.is_(None))
        .order_by(Digest.section, Digest.rank)
    )
    with get_session() as session:
        return [(d, a) for d, a in session.execute(stmt)]


def digest_already_sent(digest_date: date) -> bool:
    """True if an email for this date already went out (used by the retry run)."""
    stmt = select(func.count()).select_from(Digest).where(
        Digest.digest_date == digest_date, Digest.sent_at.is_not(None)
    )
    with get_session() as session:
        return session.execute(stmt).scalar_one() > 0


def mark_digests_sent(digest_ids: list[int]) -> None:
    stmt = update(Digest).where(Digest.id.in_(digest_ids)).values(sent_at=func.now())
    with get_session() as session:
        session.execute(stmt)


def count_articles_by_section() -> dict[tuple[str, str], int]:
    """{(section, region): count} for every stored article."""
    stmt = select(Article.section, Article.region, func.count()).group_by(
        Article.section, Article.region
    )
    with get_session() as session:
        return {(s, r): n for s, r, n in session.execute(stmt)}
