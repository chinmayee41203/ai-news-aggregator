"""SQLAlchemy tables: one `articles` table for every source, plus `digests`."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)  # dedupe key
    source: Mapped[str] = mapped_column(String(64), index=True)  # name in sources.yaml
    section: Mapped[str] = mapped_column(String(16), index=True)  # tech | business | politics
    region: Mapped[str] = mapped_column(String(16))  # global | india
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    publisher: Mapped[str] = mapped_column(String(128), default="")
    external_id: Mapped[str | None] = mapped_column(String(64))  # e.g. YouTube video id
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Google News items only: Gemini's section (tech | business | politics | none).
    # Saved so each item is classified once, even across reruns.
    section_label: Mapped[str | None] = mapped_column(String(16))
    # Full text / transcript — filled in Phase 3 for AI tech items only.
    content: Mapped[str | None] = mapped_column(Text)
    content_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | ok | unavailable
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Digest(Base):
    """A story chosen for an email, with its rank and Gemini summary (Phase 4)."""

    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    section: Mapped[str] = mapped_column(String(16))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    about_india: Mapped[bool] = mapped_column(Boolean, default=False)  # Gemini's tag; drives the 🇮🇳 badge
    digest_date: Mapped[date] = mapped_column(Date, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
