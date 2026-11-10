"""Curator: one Gemini call per section picks the best news *events* for the
reader. The answer is shaped so the model lists each event once, plus a
separate list of the best India events. Two rules are then enforced in code:
- one story per event (labels are compared again, across both lists)
- at least MIN_INDIA_BY_SECTION[section] stories about India, when there are any
"""

import logging
import re
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from app.agent.base import GeminiAgent
from app.profiles.user_profile import MIN_INDIA_BY_SECTION, STORIES_PER_SECTION, USER_PROFILE

log = logging.getLogger(__name__)

TOP_EVENTS = 10
INDIA_EVENTS = 5


class EventPick(BaseModel):
    event: str = Field(description="3-8 word label of the news event")
    best_id: int = Field(description="id of the single best story about this event")
    score: float = Field(description="0-10: how much the reader would want this")
    reason: str = Field(description="a few words on why")
    about_india: bool = Field(description="true if the event is mainly about India")


class Ranking(BaseModel):
    top_events: list[EventPick]
    india_events: list[EventPick]


SECTION_GUIDANCE = {
    "education": (
        "{name} is an international master's student in the US (New Jersey) on an F-1 visa. "
        "Pick stories that matter to them: changes to F-1, OPT, STEM OPT, H-1B or other visa rules, "
        "fees, deadlines, lottery/cap news, USCIS or State Department announcements, court rulings on "
        "these rules, and major news about international students or US universities. "
        "Official rule changes and deadlines come first. Skip unrelated diaspora or celebrity stories."
    ),
}

SYSTEM_PROMPT = """You are the editor of a personal daily news digest for {name}.
You are choosing stories for the {section} section.

{name}'s interests in this section: {interests}.
{guidance}

First group the candidate stories by the news event they report (several outlets often cover the same event).
Then return:
- top_events: the {top} events {name} would most want to read about today, best first. Each event appears
  ONCE, with the id of the single best story about it (prefer the clearest headline with a description).
- india_events: the {india} best events that are mainly about India (Indian politics, economy, companies,
  people), best first, same format. An Indian outlet covering US or global news is NOT about India.
  These may also appear in top_events. Return fewer only if there are not enough.

Prefer significant, concrete, new developments that match the interests above.
Push down: how-to guides, listicles, festival greetings, daily gold/fuel price lists, live-blog or roundup
pages, minor local incidents, clickbait, TV-panel commentary, and opinion pieces with no news.
Use only ids from the list."""


def _describe(article) -> str:
    outlet = "Indian outlet" if article.region == "india" else "Global outlet"
    who = article.publisher or article.source
    text = f"{article.id}: [{outlet} | {who}] {article.title}"
    if article.description:
        text += f" — {article.description[:250]}"
    return text


def _norm(label: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", label.lower()))


def same_event(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / len(ta | tb) >= 0.6 or SequenceMatcher(None, a, b).ratio() >= 0.8


def _dedupe(picks: list[EventPick], valid_ids: set[int], taken: list[EventPick] | None = None) -> list[EventPick]:
    """Drop picks with unknown ids and picks repeating an id or event already kept."""
    kept: list[EventPick] = []
    for p in picks:
        pool = kept + (taken or [])
        if p.best_id not in valid_ids:
            continue
        if any(p.best_id == k.best_id or same_event(p.event, k.event) for k in pool):
            continue
        kept.append(p)
    return kept


def choose(top: list[EventPick], india: list[EventPick], n: int, min_india: int) -> list[EventPick]:
    """Top n events, then swap the lowest non-India picks for India events
    until `min_india` India events are included."""
    chosen = top[:n]
    spare = [p for p in india if not any(p.best_id == c.best_id or same_event(p.event, c.event) for c in chosen)]
    spare += [p for p in top[n:] if p.about_india and p not in spare]
    while sum(p.about_india for p in chosen) < min_india and spare:
        others = [p for p in chosen if not p.about_india]
        if not others:
            break
        chosen.remove(others[-1])
        chosen.append(spare.pop(0))
    return sorted(chosen, key=lambda p: -p.score)


class CuratorAgent:
    def __init__(self):
        self.agent = GeminiAgent()

    def rank(self, section: str, candidates: list) -> list[tuple[object, EventPick]]:
        """Returns [(article, pick)] for the chosen stories, best first."""
        if not candidates:
            return []
        name = USER_PROFILE["name"]
        system = SYSTEM_PROMPT.format(
            name=name,
            section=section,
            interests=", ".join(USER_PROFILE["interests"][section]),
            guidance=SECTION_GUIDANCE.get(section, "").format(name=name),
            top=TOP_EVENTS,
            india=INDIA_EVENTS,
        )
        prompt = "Candidates (id: [outlet type | outlet] headline — description):\n\n" + "\n".join(
            _describe(a) for a in candidates
        )
        ranking = self.agent.generate_structured(prompt, Ranking, system=system, temperature=0.2)

        by_id = {a.id: a for a in candidates}
        top = _dedupe(ranking.top_events, set(by_id))
        india = [p for p in _dedupe(ranking.india_events, set(by_id)) if p.about_india]
        min_india = MIN_INDIA_BY_SECTION.get(section, 0)
        chosen = choose(top, india, STORIES_PER_SECTION, min_india)

        india_count = sum(p.about_india for p in chosen)
        if india_count < min_india:
            log.warning("%s: only %d India stories available today", section, india_count)
        return [(by_id[p.best_id], p) for p in chosen]
