"""Gemini labels Google News items with their real section.

Their section otherwise only comes from the search query, so a CNN politics
story can arrive through the "technology" search. Direct feeds (NYT Tech,
Times Now Business, ...) are not sent here — their section is already right.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from app.agent.base import GeminiAgent

log = logging.getLogger(__name__)

Label = Literal["tech", "business", "politics", "none"]


class ItemLabel(BaseModel):
    id: int
    section: Label


class Labels(BaseModel):
    labels: list[ItemLabel]


SYSTEM_PROMPT = """You sort news headlines into sections for a daily news digest.

Sections:
- tech: technology companies and products, AI, software, gadgets, the internet, cybersecurity, telecom, chips, space technology.
- business: the economy, markets, stocks, companies' finances, earnings, deals, jobs, prices, trade, banking, personal finance.
- politics: government, elections, political parties and leaders, legislation, policy, courts ruling on political matters, diplomacy, wars and conflicts.
- none: anything else — sports, entertainment, celebrities, lifestyle, festivals, crime, accidents, weather, environment, health — unless the story is mainly about tech, business or politics.

Judge by what the story is mainly about, not by single words (a farm-fires story that mentions a NASA satellite image is "none").
Return exactly one label for every id you are given."""


def classify_sections(items: list[tuple[int, str, str]], batch_size: int = 200) -> dict[int, str]:
    """items: (id, title, description). Returns {id: section}; 'none' = off-topic.

    Ids missing from Gemini's answer are left out of the result.
    """
    agent = GeminiAgent()
    result: dict[int, str] = {}
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        lines = "\n".join(
            f"{item_id}: {title}" + (f" — {desc[:200]}" if desc else "")
            for item_id, title, desc in batch
        )
        answer = agent.generate_structured(
            prompt=f"Label each headline (id: headline — description):\n\n{lines}",
            schema=Labels,
            system=SYSTEM_PROMPT,
            temperature=0.0,
        )
        wanted = {item_id for item_id, _, _ in batch}
        result.update({lbl.id: lbl.section for lbl in answer.labels if lbl.id in wanted})
        missing = len(wanted) - len(wanted & result.keys())
        if missing:
            log.warning("Gemini skipped %d of %d items in a batch", missing, len(batch))
    return result
