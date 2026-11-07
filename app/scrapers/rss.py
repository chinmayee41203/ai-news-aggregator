"""Generic RSS/Atom scraper (NYT, Times Now, Times of India, OpenAI, Anthropic)."""

import calendar
from datetime import datetime, timezone

import feedparser

from app.scrapers.base import Article, BaseScraper, clean_url, strip_html


def entry_datetime(entry) -> datetime | None:
    """feedparser gives dates as UTC struct_time; convert to aware datetime."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


class RSSScraper(BaseScraper):
    def feed_url(self) -> str:
        return self.options["url"]

    def fetch(self) -> list[Article]:
        response = self.http_get(self.feed_url())
        feed = feedparser.parse(response.content)

        articles = []
        for entry in feed.entries:
            published = entry_datetime(entry)
            link = entry.get("link")
            title = strip_html(entry.get("title", ""), max_len=300)
            if not (published and link and title):
                continue
            articles.append(self.parse_entry(entry, link, title, published))
        return articles

    def parse_entry(self, entry, link: str, title: str, published: datetime) -> Article:
        return self.make_article(
            url=clean_url(link),
            title=title,
            description=strip_html(entry.get("summary", "")),
            published_at=published,
        )
