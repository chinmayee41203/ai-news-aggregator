"""YouTube channels: RSS feed first (as in the video), YouTube Data API v3 as fallback.

The RSS endpoint (feeds/videos.xml) is free and needs no key, but in 2026 it
often returns 404/500 for valid channels. When that happens for a channel, we
read its uploads through the official API instead (free key, 1 quota unit per
channel per run; free quota is 10,000 units/day).
"""

import logging
import time
from datetime import datetime

import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from app.config import YOUTUBE_API_KEY
from app.scrapers.base import Article, BaseScraper, strip_html
from app.scrapers.rss import entry_datetime

log = logging.getLogger(__name__)

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"


class YouTubeScraper(BaseScraper):
    def fetch(self) -> list[Article]:
        articles = []
        for channel_id, channel_name in self.options["channels"].items():
            try:
                articles.extend(self.fetch_channel(channel_id, channel_name))
            except Exception as exc:  # one bad channel shouldn't stop the rest
                log.warning("%s: channel %s failed: %s", self.name, channel_name, exc)
        return articles

    def fetch_channel(self, channel_id: str, channel_name: str) -> list[Article]:
        try:
            return self.fetch_via_rss(channel_id, channel_name)
        except requests.HTTPError as exc:
            if not YOUTUBE_API_KEY:
                raise RuntimeError(f"RSS failed ({exc}) and YOUTUBE_API_KEY is not set") from exc
            log.info("%s: RSS failed for %s, using the API", self.name, channel_name)
            return self.fetch_via_api(channel_id, channel_name)

    # ---------- RSS (no key) ----------
    def fetch_via_rss(self, channel_id: str, channel_name: str, attempts: int = 2) -> list[Article]:
        for attempt in range(1, attempts + 1):
            try:
                content = self.http_get(FEED_URL.format(channel_id)).content
                break
            except requests.HTTPError:
                if attempt == attempts:
                    raise
                time.sleep(2)

        videos = []
        for entry in feedparser.parse(content).entries:
            link = entry.get("link", "")
            published = entry_datetime(entry)
            if "/shorts/" in link or not published:
                continue  # skip Shorts: usually clips of longer videos
            videos.append(
                self.make_article(
                    url=link,
                    title=entry.get("title", ""),
                    description=strip_html(entry.get("summary", "")),
                    published_at=published,
                    publisher=channel_name,
                    external_id=entry.get("yt_videoid"),
                )
            )
        return videos

    # ---------- YouTube Data API v3 (fallback) ----------
    def fetch_playlist(self, playlist_id: str) -> list[dict]:
        response = self.http_get(
            PLAYLIST_ITEMS_URL,
            params={
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 15,
                "key": YOUTUBE_API_KEY,
            },
        )
        return response.json().get("items", [])

    def fetch_via_api(self, channel_id: str, channel_name: str) -> list[Article]:
        suffix = channel_id[2:]  # channel ids look like "UC" + 22 chars
        try:
            # "UULF…" = the channel's long-form uploads (no Shorts, no live streams).
            items = self.fetch_playlist("UULF" + suffix)
        except requests.HTTPError:
            # Fallback: "UU…" = all uploads, including Shorts.
            items = self.fetch_playlist("UU" + suffix)

        videos = []
        for item in items:
            snippet = item["snippet"]
            video_id = item["contentDetails"]["videoId"]
            published = item["contentDetails"].get("videoPublishedAt") or snippet["publishedAt"]
            videos.append(
                self.make_article(
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=snippet["title"],
                    description=strip_html(snippet.get("description", "")),
                    published_at=datetime.fromisoformat(published.replace("Z", "+00:00")),
                    publisher=channel_name,
                    external_id=video_id,
                )
            )
        return videos


def get_transcript(video_id: str) -> str | None:
    """Return the English transcript as plain text, or None if unavailable."""
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
    except Exception as exc:
        log.info("No transcript for %s: %s", video_id, exc)
        return None
    return " ".join(snippet.text for snippet in fetched)
