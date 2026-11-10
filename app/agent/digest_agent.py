"""Digest agent: writes short summaries for the stories the curator chose.

- Articles: one batched Gemini call per section.
- YouTube videos without a transcript (YouTube blocks transcript downloads from
  cloud servers like GitHub's): Gemini watches the video itself from its link.
  To keep this within the free tier, only chosen videos are watched, at most
  MAX_VIDEOS_WATCHED per run, only the first VIDEO_CLIP_SECONDS, at low
  resolution and 0.5 frames per second. If that fails, the video is summarized
  from its description like any other story.
"""

import logging

from google.genai import types
from pydantic import BaseModel

from app.agent.base import GeminiAgent

log = logging.getLogger(__name__)

MAX_CONTENT_CHARS_PER_STORY = 6_000  # transcripts / full text are trimmed further here
MAX_VIDEOS_WATCHED = 2  # per run (each is one Gemini request)
VIDEO_CLIP_SECONDS = 20 * 60  # watch only the first 20 minutes


class StorySummary(BaseModel):
    id: int
    summary: str


class Summaries(BaseModel):
    summaries: list[StorySummary]


class VideoSummary(BaseModel):
    summary: str


SYSTEM_PROMPT = """You write the summaries for a personal daily news digest.

For every story, write a 2-3 sentence summary in your own words: what happened and why it matters.
Rules:
- Use only the information given for that story. Do not add facts, numbers, names or quotes that are not there.
- If only a headline is given, write one neutral sentence explaining what the headline reports.
- Plain, calm language. No hype, no clickbait, no emojis.
- Do not copy sentences from the description; paraphrase.
- Write about the news itself; never say "this article", "this summary" or "the story".
Return one summary for every id."""

VIDEO_PROMPT = """Summarize this YouTube video for a personal daily news digest in 2-3 sentences:
the main news or ideas it covers and why they matter. Use only what is said or shown in the video.
Plain, calm language, no hype, no emojis. Write about the content itself; never say "this video"."""


def _story_block(article) -> str:
    parts = [f"id: {article.id}", f"headline: {article.title}"]
    if article.description:
        parts.append(f"description: {article.description}")
    if getattr(article, "content", None):
        parts.append(f"full text (trimmed): {article.content[:MAX_CONTENT_CHARS_PER_STORY]}")
    return "\n".join(parts)


def _is_video_to_watch(article) -> bool:
    return bool(getattr(article, "external_id", None)) and "youtube.com/watch" in article.url and not getattr(article, "content", None)


class DigestAgent:
    def __init__(self):
        self.agent = GeminiAgent()

    def watch_video(self, article) -> str | None:
        """Summary of a YouTube video, written by Gemini from the video itself."""
        video = types.Part(
            file_data=types.FileData(file_uri=article.url),
            video_metadata=types.VideoMetadata(end_offset=f"{VIDEO_CLIP_SECONDS}s", fps=0.5),
        )
        try:
            result = self.agent.generate_structured(
                [video, types.Part(text=f"Video title: {article.title}\n\n{VIDEO_PROMPT}")],
                VideoSummary,
                temperature=0.3,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            )
            return result.summary.strip() or None
        except Exception as exc:
            log.warning("Could not watch video %s (%s); using its description", article.url, exc)
            return None

    def summarize(self, articles: list) -> dict[int, str]:
        """Returns {article_id: summary}."""
        if not articles:
            return {}
        summaries: dict[int, str] = {}

        for article in [a for a in articles if _is_video_to_watch(a)][:MAX_VIDEOS_WATCHED]:
            if text := self.watch_video(article):
                summaries[article.id] = text
                log.info("Summarized video from the video itself: %s", article.title[:80])

        rest = [a for a in articles if a.id not in summaries]
        if rest:
            prompt = "Stories:\n\n" + "\n\n---\n\n".join(_story_block(a) for a in rest)
            result = self.agent.generate_structured(prompt, Summaries, system=SYSTEM_PROMPT, temperature=0.3)
            wanted = {a.id for a in rest}
            summaries.update({s.id: s.summary.strip() for s in result.summaries if s.id in wanted})

        # Never leave a story without text: fall back to its description or headline.
        for a in articles:
            if not summaries.get(a.id):
                summaries[a.id] = (a.description or a.title).strip()
        return summaries
