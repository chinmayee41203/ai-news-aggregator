"""Phase 3 filter: turns the last 24h of stored articles into clean candidates
per section, before ranking.

Steps, in order:
1. drop junk pages (e.g. CNN stock-quote pages)
2. Google News items only: Gemini labels each with its real section
   (tech / business / politics / none) — their section otherwise only comes
   from the search query. "none" items are dropped. Direct feeds keep their
   feed's section. If Gemini is unavailable, Google News items are left out
   for this run rather than risk the wrong section.
3. merge near-identical headlines within a section (same story, several outlets)

Checkpoint:  uv run python -m app.services.filter
"""

import argparse
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.config import HOURS_BACK, SECTIONS, load_sources

log = logging.getLogger(__name__)

JUNK_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"symbol__",
        r"stock quote price and forecast",
    )
]

STOPWORDS = set("a an the of to in on for and or is are was were be by with at from as it its this that".split())

Classifier = Callable[[list[tuple[int, str, str]]], dict[int, str]]


def normalize_title(title: str) -> str:
    title = re.sub(r"\s*[|\-–]\s*(cnn|cnn politics|cnn business|the times of india|times now)\s*$", "", title, flags=re.I)
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in STOPWORDS)


def similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ta, tb = set(a.split()), set(b.split())
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard >= 0.7 or SequenceMatcher(None, a, b).ratio() >= 0.88


@dataclass
class FilterResult:
    candidates: dict[str, list] = field(default_factory=dict)  # section -> articles
    before: Counter = field(default_factory=Counter)
    after: Counter = field(default_factory=Counter)
    junk: int = 0
    off_topic: int = 0  # Gemini said "none" (or skipped the item)
    moved: int = 0  # Gemini put it in a different section
    unclassified: int = 0  # Gemini unavailable -> left out
    merged: int = 0


def _default_classifier(items: list[tuple[int, str, str]]) -> dict[int, str]:
    from app.agent.section_classifier import classify_sections

    return classify_sections(items)


def filter_articles(articles: list, classify: Classifier = _default_classifier) -> FilterResult:
    """`articles`: objects with id, title, description, section, source, published_at."""
    untrusted = {s["name"] for s in load_sources() if s["type"] == "google_news"}
    result = FilterResult()
    by_section: dict[str, list] = defaultdict(list)
    to_classify: list = []

    for a in articles:
        result.before[a.section] += 1
        if any(p.search(a.title) for p in JUNK_PATTERNS):
            result.junk += 1
        elif a.source in untrusted:
            to_classify.append(a)
        else:
            by_section[a.section].append(a)

    if to_classify:
        try:
            labels = classify([(a.id, a.title, a.description or "") for a in to_classify])
        except Exception as exc:
            log.warning("Section classifier failed, leaving out %d Google News items: %s", len(to_classify), exc)
            result.unclassified = len(to_classify)
            labels = None

        if labels is not None:
            for a in to_classify:
                label = labels.get(a.id, "none")
                if label not in SECTIONS:
                    result.off_topic += 1
                    continue
                if label != a.section:
                    result.moved += 1
                by_section[label].append(a)

    for section in SECTIONS:
        kept: list = []
        kept_norm: list[str] = []
        # Prefer direct feeds over Google News, then items with a description, then newest.
        ordered = sorted(
            by_section[section],
            key=lambda a: (a.source in untrusted, not a.description, -a.published_at.timestamp()),
        )
        for a in ordered:
            norm = normalize_title(a.title)
            if any(similar(norm, k) for k in kept_norm):
                result.merged += 1
                continue
            kept.append(a)
            kept_norm.append(norm)
        kept.sort(key=lambda a: a.published_at, reverse=True)
        result.candidates[section] = kept
        result.after[section] = len(kept)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Show what the filter keeps.")
    parser.add_argument("--hours", type=int, default=HOURS_BACK)
    parser.add_argument("--show", type=int, default=5, help="headlines to print per section")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from app.database.repository import get_recent_articles

    result = filter_articles(get_recent_articles(args.hours))

    print(f"\nLast {args.hours}h — before → after filtering")
    for s in SECTIONS:
        print(f"  {s:<9} {result.before[s]:>4} → {result.after[s]:>4}")
    print(f"  total     {sum(result.before.values()):>4} → {sum(result.after.values()):>4}")
    print(
        f"\nDropped junk: {result.junk} | off-topic (Gemini: none): {result.off_topic} | "
        f"moved to another section: {result.moved} | merged duplicates: {result.merged}"
        + (f" | left out (Gemini unavailable): {result.unclassified}" if result.unclassified else "")
    )
    for s in SECTIONS:
        india = sum(1 for a in result.candidates[s] if a.region == "india")
        print(f"\n=== {s.upper()} — {result.after[s]} candidates ({india} India) ===")
        for a in result.candidates[s][: args.show]:
            flag = "IN " if a.region == "india" else "   "
            print(f"  {flag}{a.title}  ({a.publisher or a.source})")


if __name__ == "__main__":
    main()
