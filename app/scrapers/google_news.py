"""Google News search feeds — used for sites whose own RSS is missing or stale
(CNN, Times Now politics, Times of India tech/politics)."""

from datetime import datetime
from urllib.parse import quote_plus

from app.scrapers.base import Article
from app.scrapers.rss import RSSScraper

LOCALES = {
    "us": "hl=en-US&gl=US&ceid=US:en",
    "in": "hl=en-IN&gl=IN&ceid=IN:en",
}


class GoogleNewsScraper(RSSScraper):
    def feed_url(self) -> str:
        query = quote_plus(f"{self.options['query']} when:1d")
        locale = LOCALES[self.options.get("locale", "us")]
        return f"https://news.google.com/rss/search?q={query}&{locale}"

    def parse_entry(self, entry, link: str, title: str, published: datetime) -> Article:
        # Google News titles end with " - Publisher"; keep them separate.
        publisher = entry.get("source", {}).get("title", "")
        suffix = f" - {publisher}"
        if publisher and title.endswith(suffix):
            title = title[: -len(suffix)]
        # The description is just the title again as HTML, so it is skipped.
        # Links are news.google.com redirects; stored as-is.
        return self.make_article(
            url=link,
            title=title,
            published_at=published,
            publisher=publisher,
        )
