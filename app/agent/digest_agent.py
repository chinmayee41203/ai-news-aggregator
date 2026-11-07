"""Digest agent: one Gemini call per section writes short summaries for the
stories the curator chose."""

from pydantic import BaseModel

from app.agent.base import GeminiAgent

MAX_CONTENT_CHARS_PER_STORY = 6_000  # transcripts / full text are trimmed further here


class StorySummary(BaseModel):
    id: int
    summary: str


class Summaries(BaseModel):
    summaries: list[StorySummary]


SYSTEM_PROMPT = """You write the summaries for a personal daily news digest.

For every story, write a 2-3 sentence summary in your own words: what happened and why it matters.
Rules:
- Use only the information given for that story. Do not add facts, numbers, names or quotes that are not there.
- If only a headline is given, write one neutral sentence explaining what the headline reports.
- Plain, calm language. No hype, no clickbait, no emojis.
- Do not copy sentences from the description; paraphrase.
- Write about the news itself; never say "this article", "this summary" or "the story".
Return one summary for every id."""


def _story_block(article) -> str:
    parts = [f"id: {article.id}", f"headline: {article.title}"]
    if article.description:
        parts.append(f"description: {article.description}")
    if getattr(article, "content", None):
        parts.append(f"full text (trimmed): {article.content[:MAX_CONTENT_CHARS_PER_STORY]}")
    return "\n".join(parts)


class DigestAgent:
    def __init__(self):
        self.agent = GeminiAgent()

    def summarize(self, articles: list) -> dict[int, str]:
        """Returns {article_id: summary}."""
        if not articles:
            return {}
        prompt = "Stories:\n\n" + "\n\n---\n\n".join(_story_block(a) for a in articles)
        result = self.agent.generate_structured(prompt, Summaries, system=SYSTEM_PROMPT, temperature=0.3)
        wanted = {a.id for a in articles}
        summaries = {s.id: s.summary.strip() for s in result.summaries if s.id in wanted}
        # Never leave a story without text: fall back to its description or headline.
        for a in articles:
            if not summaries.get(a.id):
                summaries[a.id] = (a.description or a.title).strip()
        return summaries
