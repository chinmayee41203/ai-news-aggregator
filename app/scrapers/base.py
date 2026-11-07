"""Shared Article model and BaseScraper that every scraper inherits from."""

import html
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from pydantic import BaseModel

from app.config import REQUEST_TIMEOUT, USER_AGENT

TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "ref", "cmpid", "smid", "partner")


class Article(BaseModel):
    """One news item, whatever source it came from."""

    url: str
    title: str
    description: str = ""
    published_at: datetime  # always timezone-aware UTC
    source: str  # e.g. "nyt_tech"
    section: str  # tech | business | politics
    region: str  # global | india
    publisher: str = ""  # e.g. "CNN" for Google News items
    external_id: str | None = None  # e.g. YouTube video id


def clean_url(url: str) -> str:
    """Drop tracking query params and fragments so the same story dedupes."""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PARAMS)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def strip_html(text: str, max_len: int = 600) -> str:
    """Turn an HTML snippet into short plain text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:max_len]


class BaseScraper(ABC):
    """Fetches items from one source and returns those newer than `hours_back`."""

    def __init__(self, name: str, section: str, region: str, fetch_content: bool = False, **options):
        self.name = name
        self.section = section
        self.region = region
        self.fetch_content = fetch_content  # used by app/services/enrich.py
        self.options = options

    @abstractmethod
    def fetch(self) -> list[Article]:
        """Return every item the source currently offers."""

    def get_articles(self, hours_back: int) -> list[Article]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        return [a for a in self.fetch() if a.published_at >= cutoff]

    def http_get(self, url: str, **kwargs) -> requests.Response:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def make_article(self, **fields) -> Article:
        return Article(source=self.name, section=self.section, region=self.region, **fields)
