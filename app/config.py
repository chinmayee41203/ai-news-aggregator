"""Project settings and the source list (sources.yaml)."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT_DIR / "sources.yaml"

load_dotenv(ROOT_DIR / ".env")

SECTIONS = ("tech", "business", "politics")
REGIONS = ("global", "india")

HOURS_BACK = int(os.getenv("HOURS_BACK", "24"))
USER_AGENT = "ai-news-aggregator/1.0"
REQUEST_TIMEOUT = 20  # seconds

GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


def load_sources(path: Path = SOURCES_FILE) -> list[dict]:
    """Read sources.yaml and check each entry has the shared fields."""
    with open(path, encoding="utf-8") as f:
        sources = yaml.safe_load(f) or []

    names = set()
    for src in sources:
        for field in ("name", "type", "section", "region"):
            if field not in src:
                raise ValueError(f"Source {src!r} is missing '{field}'")
        if src["section"] not in SECTIONS:
            raise ValueError(f"{src['name']}: unknown section '{src['section']}'")
        if src["region"] not in REGIONS:
            raise ValueError(f"{src['name']}: unknown region '{src['region']}'")
        if src["name"] in names:
            raise ValueError(f"Duplicate source name '{src['name']}'")
        names.add(src["name"])
    return sources
