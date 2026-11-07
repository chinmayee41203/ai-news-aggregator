"""Email agent: writes the greeting and a short intro for the day's digest."""

from datetime import date

from pydantic import BaseModel

from app.agent.base import GeminiAgent
from app.profiles.user_profile import USER_PROFILE


class EmailIntro(BaseModel):
    greeting: str
    intro: str


SYSTEM_PROMPT = """You write the opening of a personal daily news digest email.
- greeting: one short line addressed to the reader by name, e.g. "Good morning, {name}!"
- intro: 2-3 friendly sentences previewing the most important stories across the sections.
Use only the headlines given. No hype, no emojis."""


class EmailAgent:
    def __init__(self):
        self.agent = GeminiAgent()

    def write_intro(self, digest_date: date, headlines_by_section: dict[str, list[str]]) -> EmailIntro:
        lines = [f"Date: {digest_date:%A, %d %B %Y}", f"Reader: {USER_PROFILE['name']}", ""]
        for section, headlines in headlines_by_section.items():
            lines.append(f"{section.upper()}:")
            lines.extend(f"- {h}" for h in headlines)
            lines.append("")
        return self.agent.generate_structured(
            "\n".join(lines),
            EmailIntro,
            system=SYSTEM_PROMPT.format(name=USER_PROFILE["name"]),
            temperature=0.5,
        )
