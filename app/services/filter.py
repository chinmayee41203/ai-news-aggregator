"""Phase 3 filter: turns the last 24h of stored articles into clean candidates
per section, before anything is sent to Gemini.

Steps, in order:
1. drop junk pages (e.g. CNN stock-quote pages)
2. fix sections for Google News items (their section only comes from the search
   query, so a CNN politics story can arrive through the "technology" search);
   drop them if they match no section's keywords
3. merge near-identical headlines within a section (same story, several outlets)

Checkpoint:  uv run python -m app.services.filter
"""

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.config import HOURS_BACK, SECTIONS, load_sources

JUNK_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"symbol__",
        r"stock quote price and forecast",
    )
]

SECTION_KEYWORDS: dict[str, list[str]] = {
    "tech": [
        "ai", "artificial intelligence", "openai", "chatgpt", "gemini", "anthropic", "claude",
        "llm", "chatbot", "deepfake", "algorithm", "chip", "chips", "semiconductor", "nvidia",
        "apple", "iphone", "android", "google", "microsoft", "meta", "amazon", "samsung",
        "smartphone", "app", "apps", "software", "startup", "cyber", "cybersecurity", "hack",
        "hacker", "data", "cloud", "robot", "robotics", "tech", "technology", "internet",
        "social media", "tesla", "electric vehicle", "ev", "space", "satellite", "isro", "nasa",
        "quantum", "5g", "crypto", "bitcoin", "gadget", "laptop", "elon musk",
    ],
    "business": [
        "market", "markets", "stock", "stocks", "shares", "sensex", "nifty", "wall street",
        "dow", "nasdaq", "economy", "economic", "gdp", "inflation", "recession", "rbi", "fed",
        "federal reserve", "interest rate", "rates", "bank", "banks", "earnings", "profit",
        "revenue", "ipo", "deal", "merger", "acquisition", "investor", "investors", "trade",
        "tariff", "tariffs", "oil", "prices", "company", "companies", "ceo", "business",
        "finance", "tax", "budget", "rupee", "dollar", "funding", "layoffs", "jobs", "retail",
        "consumer", "billion", "million", "crore", "lakh",
    ],
    "politics": [
        "election", "elections", "vote", "voters", "poll", "polls", "midterm", "minister",
        "government", "parliament", "congress", "senate", "senator", "president", "prime minister",
        "modi", "trump", "bjp", "aap", "party", "campaign", "policy", "law", "bill", "court",
        "supreme court", "governor", "cabinet", "opposition", "diplomat", "diplomatic", "war",
        "sanctions", "white house", "lok sabha", "rajya sabha", "chief minister", "democrat",
        "democrats", "republican", "republicans", "gop", "mla", "protest", "rally", "nato",
        "ceasefire", "military", "immigration",
    ],
}

_KEYWORD_RE = {
    section: re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
    for section, words in SECTION_KEYWORDS.items()
}

STOPWORDS = set("a an the of to in on for and or is are was were be by with at from as it its this that".split())


def section_scores(title: str, description: str) -> dict[str, int]:
    """Keyword hits per section; title hits count double."""
    return {
        s: 2 * len(rx.findall(title)) + len(rx.findall(description or ""))
        for s, rx in _KEYWORD_RE.items()
    }


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
    off_topic: int = 0
    moved: int = 0
    merged: int = 0


def filter_articles(articles: list) -> FilterResult:
    """`articles`: objects with title, description, section, source, published_at."""
    untrusted = {s["name"] for s in load_sources() if s["type"] == "google_news"}
    result = FilterResult()
    by_section: dict[str, list] = defaultdict(list)

    for a in articles:
        result.before[a.section] += 1
        if any(p.search(a.title) for p in JUNK_PATTERNS):
            result.junk += 1
            continue

        section = a.section
        if a.source in untrusted:
            scores = section_scores(a.title, a.description)
            best = max(scores, key=lambda s: (scores[s], s == a.section))
            if scores[best] == 0:
                result.off_topic += 1
                continue
            if best != a.section:
                result.moved += 1
                section = best
        by_section[section].append(a)

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

    from app.database.repository import get_recent_articles

    result = filter_articles(get_recent_articles(args.hours))

    print(f"Last {args.hours}h — before → after filtering")
    for s in SECTIONS:
        print(f"  {s:<9} {result.before[s]:>4} → {result.after[s]:>4}")
    print(f"  total     {sum(result.before.values()):>4} → {sum(result.after.values()):>4}")
    print(
        f"\nDropped junk: {result.junk} | off-topic (no keywords): {result.off_topic} | "
        f"moved to another section: {result.moved} | merged duplicates: {result.merged}"
    )
    for s in SECTIONS:
        india = sum(1 for a in result.candidates[s] if a.region == "india")
        print(f"\n=== {s.upper()} — {result.after[s]} candidates ({india} India) ===")
        for a in result.candidates[s][: args.show]:
            flag = "IN " if a.region == "india" else "   "
            print(f"  {flag}{a.title}  ({a.publisher or a.source})")


if __name__ == "__main__":
    main()
