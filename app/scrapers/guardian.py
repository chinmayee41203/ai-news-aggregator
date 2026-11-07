"""The Guardian Open Platform API (free key: open-platform.theguardian.com)."""

import logging
from datetime import datetime, timedelta, timezone

from app.config import GUARDIAN_API_KEY
from app.scrapers.base import Article, BaseScraper, strip_html

log = logging.getLogger(__name__)

API_URL = "https://content.guardianapis.com/search"


class GuardianScraper(BaseScraper):
    def fetch(self) -> list[Article]:
        if not GUARDIAN_API_KEY:
            log.warning("%s skipped: GUARDIAN_API_KEY is not set", self.name)
            return []

        since = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        response = self.http_get(
            API_URL,
            params={
                "section": self.options["guardian_section"],
                "from-date": since,
                "order-by": "newest",
                "page-size": 50,
                "show-fields": "trailText",
                "api-key": GUARDIAN_API_KEY,
            },
        )
        results = response.json()["response"]["results"]

        return [
            self.make_article(
                url=item["webUrl"],
                title=item["webTitle"],
                description=strip_html(item.get("fields", {}).get("trailText", "")),
                published_at=datetime.fromisoformat(item["webPublicationDate"]),
                publisher="The Guardian",
            )
            for item in results
        ]
