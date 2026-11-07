"""All reads/writes to the database go through here."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.database.connection import get_session
from app.database.models import Article
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


def count_articles_by_section() -> dict[tuple[str, str], int]:
    """{(section, region): count} for every stored article."""
    stmt = select(Article.section, Article.region, func.count()).group_by(
        Article.section, Article.region
    )
    with get_session() as session:
        return {(s, r): n for s, r, n in session.execute(stmt)}
