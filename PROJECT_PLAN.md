# AI-Powered News Aggregator — Project Breakdown & Build Plan (100% free stack)

Based on *"Build a Complete End-to-End GenAI Project in 3 Hours"* — Dave Ebbelaar (Datalumina), YouTube `E8zpgNPx8jE`.
We follow the video's architecture with two big changes:
1. **Every paid piece is replaced with a free one.** The LLM is **Google Gemini Flash (free tier)**.
2. **The scope is wider than AI news.** The daily email has three sections, **Tech, Business and Politics**, combining global sources (NYT, CNN, The Guardian) with **Indian** sources (Times Now, Times of India).

---

## 1. What the project is

A Python pipeline that runs **once a day** and:

1. **Collects** headlines from official RSS feeds and free APIs, grouped by section: Tech (including AI), Business and Politics.
2. **Stores** them in **PostgreSQL** in one `articles` table, tagged with `source`, `section` and `region` (global or India).
3. **Filters and dedupes**: removes old items, duplicates and stories that are off-topic for their section.
4. **Curates with Gemini**: one call per section ranks that section's headlines against **your profile** and picks the top N, keeping at least 2 Indian stories per section.
5. **Summarizes with Gemini**: a 2–3 sentence summary for each chosen story only. AI-specific tech items (YouTube videos and AI lab blogs) are summarized from their full transcript or article text.
6. **Writes the email**: Gemini writes a short intro, and the HTML email lists the **Tech, Business and Politics** sections, each with headline, summary, source and link.
7. **Sends** it through Gmail SMTP with an app password.
8. **Runs for free in the cloud**: a **GitHub Actions** scheduled workflow with a **Neon** free Postgres database.

### Tech stack (all free)

| Concern | Video used | **We use (free)** |
|---|---|---|
| Language / env | Python + uv | Python 3.12+ + **uv** |
| Feeds | `feedparser` | `feedparser` (with `etag`/`modified` caching) |
| YouTube | Channel RSS + `youtube-transcript-api` | Same |
| Article text (AI lab blogs only) | docling → `html-to-markdown` | **`trafilatura`** |
| Data models | Pydantic | Pydantic |
| Database (local) | Postgres 17 in Docker | **Postgres 17 in Docker Desktop** |
| Database (cloud) | Render Postgres (paid) | **Neon free tier** |
| ORM | SQLAlchemy, one table per source | SQLAlchemy, **one `articles` table** |
| **LLM** | OpenAI `gpt-4.1-mini` (paid) | **Gemini Flash, free tier**, through the `google-genai` SDK with Pydantic structured output |
| Email | Gmail SMTP | Gmail SMTP |
| Scheduler | Render cron (paid) | **GitHub Actions** `schedule:` |
| Secrets | Render env vars | **GitHub repository secrets** |
| Transcript proxy | Webshare (paid) | **None.** Fall back to the video description. |
| DB GUI | TablePlus | **DBeaver Community** |
| Editor / AI helper | Cursor | VS Code + Claude Code |

---

## 2. Sources by section

**✅ = feed tested on 6 Nov 2026:** it responded with fresh items.
**🔎 = check when we add it.**

Sources: **NYT, CNN, The Guardian, Times Now and Times of India (India)**, plus the AI sources from the video (**OpenAI, Anthropic, YouTube**).

### Tech
| Source | Region | Feed / API | Status |
|---|---|---|---|
| NYT Technology | Global | `https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml` | ✅ |
| CNN Tech (through Google News) | Global | `https://news.google.com/rss/search?q=site:cnn.com+technology+when:1d&hl=en-US&gl=US&ceid=US:en` | 🔎 |
| Times Now Tech & Science | 🇮🇳 India | `https://www.timesnownews.com/feeds/gns-en-technology-science.xml` | ✅ |
| Times of India Tech (through Google News) | 🇮🇳 India | `https://news.google.com/rss/search?q=site:timesofindia.indiatimes.com+technology+when:1d&hl=en-IN&gl=IN&ceid=IN:en` | ✅ |
| The Guardian Technology | Global | Guardian Open Platform API, `section=technology` (free key) | 🔎 key needed |
| OpenAI News | Global (AI) | OpenAI RSS feed | 🔎 |
| Anthropic news / research / engineering | Global (AI) | Community RSS feeds (from the video) | 🔎 |
| YouTube channels you choose | Global (AI) | `youtube.com/feeds/videos.xml?channel_id=...` | 🔎 |

### Business
| Source | Region | Feed / API | Status |
|---|---|---|---|
| NYT Business | Global | `https://rss.nytimes.com/services/xml/rss/nyt/Business.xml` | ✅ |
| CNN Business (through Google News) | Global | `https://news.google.com/rss/search?q=site:cnn.com+business+when:1d&hl=en-US&gl=US&ceid=US:en` | 🔎 |
| Times Now Business & Economy | 🇮🇳 India | `https://www.timesnownews.com/feeds/gns-en-business-economy.xml` | ✅ |
| Times of India Business | 🇮🇳 India | `https://timesofindia.indiatimes.com/rssfeeds/1898055.cms` | ✅ |
| The Guardian Business | Global | Guardian API, `section=business` | 🔎 key needed |

### Politics
| Source | Region | Feed / API | Status |
|---|---|---|---|
| NYT Politics | Global (US) | `https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml` | ✅ |
| CNN Politics (through Google News) | Global (US) | `https://news.google.com/rss/search?q=site:cnn.com+politics+when:1d&hl=en-US&gl=US&ceid=US:en` | ✅ |
| Times Now Politics (through Google News) | 🇮🇳 India | `https://news.google.com/rss/search?q=site:timesnownews.com+politics+when:1d&hl=en-IN&gl=IN&ceid=IN:en` | ✅ |
| Times of India Politics (through Google News) | 🇮🇳 India | `https://news.google.com/rss/search?q=site:timesofindia.indiatimes.com+politics+when:1d&hl=en-IN&gl=IN&ceid=IN:en` | ✅ |
| The Guardian Politics | Global (UK) | Guardian API, `section=politics` | 🔎 key needed |

Notes:
- **Times Now** has direct feeds for tech and business, but no politics feed, so its politics stories come through Google News.
- **Times of India's** own tech feeds stopped updating (newest items from 2024 and Oct 2026), so its tech and politics stories come through Google News. Its business feed is fresh and used directly.
- **CNN's** own RSS feeds stopped updating in 2016, so all CNN stories come through Google News.
- **The Guardian** needs a free API key from open-platform.theguardian.com; the public `test` key was rejected.

### Rules for every source
- Collect only what the feed gives: **headline + short description + link**. We never download full pages from news publishers or try to get around paywalls.
- The email contains **short summaries in our own words, plus links** to the original. Readers click through to the publisher for the full story.
- Send a generic User-Agent (`ai-news-aggregator/1.0`) and wait between requests.

### `sources.yaml` (adding a source = adding one entry)
```yaml
- name: nyt_tech
  type: rss
  section: tech
  region: global
  url: https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml
- name: timesnow_tech
  type: rss
  section: tech
  region: india
  url: https://www.timesnownews.com/feeds/gns-en-technology-science.xml
- name: guardian_politics
  type: guardian
  section: politics
  region: global
  guardian_section: politics
- name: cnn_politics
  type: google_news
  section: politics
  region: global
  query: "site:cnn.com politics"
- name: ai_youtube
  type: youtube
  section: tech
  region: global
  channel_ids: [UC..., UC...]
```

---

## 3. Architecture

```
            ┌──────────── Daily run (main.py ← GitHub Actions cron, or local) ─────────────┐
            │                                                                              │
 sources.yaml  1. COLLECT        2. FILTER           3. CURATE              4. SUMMARIZE   │ 5. EMAIL
 ──────────    ──────────        ─────────           ─────────              ────────────   │ ────────
 NYT  (RSS) ─► RSSScraper     ─┐ last 24h          Gemini: 1 call/section  Gemini: only    │ Gemini intro
 Times Now  ─► GoogleNews     ─┤ dedupe (URL+title) rank vs your profile    the chosen     │ + HTML with
 CNN  (GN)  ─► GuardianAPI    ─┤ keyword pre-filter top N, ≥2 India each   stories        │ sections:
 Guardian   ─► YouTubeScraper ─┤                                           (AI items use  │ Tech
 AI labs    ─► (one base class)┘                                                          │
 YouTube                                                                    transcripts)  │ Business
            │        │                  │                    │                  │         │ Politics
            │        ▼                  ▼                    ▼                  ▼         │ → Gmail SMTP
            │  ┌─────────── PostgreSQL (Docker locally / Neon in the cloud) ───────────┐  │
            │  │ articles (source, section, region, …) │ digests (rank, summary, sent_at) │  │
            │  └──────────────────────────────────────────────────────────────────────┘  │
            └──────────────────────────────────────────────────────────────────────────────┘
```

**Key design choice: rank first, then summarize.** The feeds produce **hundreds of headlines a day** (Google News and NYT Business alone return 50–100 items each). Summarizing every one would blow through Gemini's free limits. Instead:
- **Curate:** one Gemini call per section ranks that section's headlines and descriptions.
- **Summarize:** a batched Gemini call writes summaries for just the winners.
- **Intro:** one more call writes the email intro.

**Total: about 7–10 Gemini requests a day.** That's well inside the free tier.

### Folder structure

```
ai-news-aggregator/
├── main.py
├── pyproject.toml / uv.lock
├── sources.yaml                  # every feed: name, type, section, region, url/query
├── .env / .env.example           # GEMINI_API_KEY, GEMINI_MODEL, GUARDIAN_API_KEY, MY_EMAIL, GMAIL_APP_PASSWORD, DATABASE_URL, ENVIRONMENT
├── .github/workflows/daily.yml
├── docker/docker-compose.yml
├── docs/deployment.md
└── app/
    ├── config.py                 # loads sources.yaml; SECTIONS, TOP_N_PER_SECTION, MIN_INDIA_PER_SECTION, HOURS_BACK
    ├── runner.py                 # scraper registry: type → scraper class
    ├── daily_runner.py           # collect → filter → curate → summarize → email
    ├── scrapers/
    │   ├── base.py               # BaseScraper + Article model (+ time filter, URL cleaning)
    │   ├── rss.py                # generic RSS (NYT, Times Now, AI labs)
    │   ├── google_news.py        # Google News search feeds (CNN, Times Now politics)
    │   ├── guardian.py           # Guardian Open Platform API
    │   └── youtube.py            # channel feed, skip Shorts, transcripts
    ├── database/
    │   ├── connection.py         # ENVIRONMENT=local|production
    │   ├── models.py             # Article, Digest
    │   ├── repository.py
    │   ├── create_tables.py
    │   └── check_connection.py
    ├── agent/
    │   ├── base.py               # Gemini client, generate_structured(), throttle + retry on 429
    │   ├── curator_agent.py      # per-section ranking
    │   ├── digest_agent.py       # batched summaries for the chosen stories
    │   └── email_agent.py        # greeting + intro
    ├── profiles/user_profile.py  # name, background, interests per section
    └── services/
        ├── filter.py             # dedupe + keyword pre-filter
        ├── enrich.py             # transcripts / article text, AI tech items only
        ├── process_email.py      # build sections → HTML → send → mark sent_at
        └── email.py              # SMTP helper
```

### Database tables

| Table | Key fields |
|---|---|
| `articles` | `id`, `url` (unique, cleaned of tracking parameters), `source`, `section` (tech/business/politics), `region` (global/india), `title`, `description`, `published_at`, `content` (nullable: transcript or article text, AI items only), `content_status` (pending/ok/unavailable), `created_at` |
| `digests` | `id`, `article_id` (FK), `section`, `rank`, `score`, `summary`, `digest_date`, `sent_at` (nullable) |

### User profile example
```python
USER_PROFILE = {
    "name": "Chinmayee",
    "background": "...",
    "interests": {
        "tech": ["AI/LLMs", "startups", "Indian tech ecosystem"],
        "business": ["markets", "Indian economy", "big tech earnings"],
        "politics": ["Indian national politics", "US politics", "geopolitics"],
    },
}
```

---

## 4. What the video covers (reference)

| # | Time | Topic | Key points | Our version |
|---|---|---|---|---|
| 1–4 | 00:00–13:00 | Intro, setup, brainstorm | `uv init`, plan with AI before coding, name the stack and folders yourself | Same |
| 5 | 13:08 | YouTube service | Channel ID (not @handle), `YouTubeTranscriptApi().fetch(id)`, Pydantic | Same (Tech section) |
| 6–7 | 30:02 | OpenAI & Anthropic scrapers | Use RSS; OpenAI's site blocks scraping; Anthropic has 3 community feeds | Become `type: rss` entries |
| 8 | 43:13 | Runner | Channel list in config; two-stage design | `sources.yaml` + registry |
| 9–10 | 49:16 | Database | Docker Postgres, SQLAlchemy, repository, PK dedupe, skip Shorts | One `articles` table |
| 11 | 1:07:40 | Enrichment | Add columns, migration, mark "unavailable" | AI tech items only |
| 12 | 1:19:56 | Digest agent | OpenAI structured output for each article | Gemini, **only for the chosen stories** |
| 13 | 1:32:00 | Curator | Score + rank against the profile | Gemini, **per section**, India quota |
| 14–15 | 1:39:16 | Email | Intro + top 10, Gmail SMTP, markdown → HTML | **3 sections** |
| 16 | 1:52:17 | Single runner | One daily runner; digest date = article date | Same |
| 17–20 | 1:58–2:16 | Deploy (Render) | Blueprint, out of memory, missing tables, uv in Docker | **GitHub Actions + Neon** |
| 21 | 2:16:28 | Hardening | `sent_at`, local/prod switch, prod migration confirmation | Same |
| 22 | 2:30:54 | Refactor | BaseScraper, registry, BaseAgent, README + Mermaid | Built in from the start |
| 23 | 2:41:10 | Proxy | Webshare (paid) | Skipped |
| 24 | 2:49:18 | Next steps | More feeds, tune prompts, lock down DB access, SaaS idea | Same ideas |

---

## 5. Build plan (each phase ends in something you can run)

### Phase 0 — Environment & free accounts (≈30 min)
- Install **Python 3.12+**, **uv**, **Docker Desktop**, **Git**, **DBeaver Community**.
- **Gemini API key** from Google AI Studio. No card needed. Note the current **Flash** model name and its free limits.
- **Gmail app password**.
- **Guardian API key** (free) from open-platform.theguardian.com.
- `uv init`, `git init`, `.gitignore` (with `.env`) and `.env.example`.
- ✅ Checkpoint: a 5-line script gets a reply from Gemini Flash.

### Phase 1 — Scrapers (≈1.5 h)
- `BaseScraper` + `Article` model, then `rss.py`, `google_news.py`, `guardian.py`, `youtube.py`.
- `sources.yaml` with the ✅ feeds above, and `config.py` to load it.
- ✅ Checkpoint: `uv run python -m app.runner --dry-run` prints the last 24h of headlines, grouped by section and region.

### Phase 2 — Database (≈1 h)
- `docker-compose.yml`, `Article`/`Digest` models, repository, `create_tables.py`.
- The runner saves articles, skipping URLs it already has.
- ✅ Checkpoint: run it twice and the rows appear once (check in DBeaver), with the right section and region.

### Phase 3 — Filter & enrich (≈45 min)
- `filter.py`: URL cleaning, title-similarity dedupe, and keyword pre-filter by section.
- `enrich.py`: transcripts and article text for AI tech items only, with the "unavailable" fallback and transcripts trimmed to about 15k characters.
- ✅ Checkpoint: a count of articles per section before and after filtering.

### Phase 4 — Gemini agents (≈1.5 h)
- `agent/base.py`: `generate_structured(prompt, PydanticModel)` with throttling and retry.
- `CuratorAgent`: one call per section, returning ranked IDs, scores and reasoning, with the India quota enforced.
- `DigestAgent`: one batched call per section for the chosen stories.
- `EmailAgent`: greeting and intro.
- ✅ Checkpoint: the terminal prints the top stories per section with summaries.

### Phase 5 — Email + daily runner (≈45 min)
- HTML template: intro, then a **Tech / Business / Politics** block per section, each story with headline, summary, source, an 🇮🇳 tag for Indian stories, and a link.
- `process_email.py` uses only unsent digests and sets `sent_at` after sending.
- `main.py` creates the tables if they're missing.
- ✅ **Milestone 1:** one command delivers the 3-section digest to your inbox.

### Phase 6 — Free cloud deployment (≈1 h)
- Neon project + connection string, `ENVIRONMENT` switch, `check_connection.py`.
- `.github/workflows/daily.yml`: cron + `workflow_dispatch`. Steps: install uv → `uv sync` → `uv run main.py`.
- GitHub Secrets: `GEMINI_API_KEY`, `GEMINI_MODEL`, `GUARDIAN_API_KEY`, `MY_EMAIL`, `GMAIL_APP_PASSWORD`, `DATABASE_URL`, `ENVIRONMENT=production`.
- ✅ **Milestone 2:** the email arrives on its own every morning (cron set to Indian time, e.g. 7:00 IST = `30 1 * * *` UTC).

### Phase 7 — Polish & hardening (≈1 h)
- README with a Mermaid diagram, `docs/deployment.md`, and `pytest` tests with saved feed samples.
- A feed health log: a warning when a source returns nothing for 3 days in a row.
- A cleanup job that deletes articles older than 30 days, to stay inside Neon's free storage.
- ✅ **Milestone 3:** clean, documented, easy to extend.

### Phase 8 — Extensions (pick any)
- More sections (World, Sports, Science) — just new `section:` values in `sources.yaml`.
- "Story clusters": group several outlets' coverage of the same event into one item with multiple links.
- A weekly roundup email.
- A small FastAPI page to browse past digests.

---

## 6. Gotchas

1. YouTube RSS needs a **channel ID**, not an `@handle`. Skip Shorts.
2. `youtube-transcript-api`: use `YouTubeTranscriptApi().fetch(id)`. Check the README.
3. Don't name a module after a package (e.g. `openai.py`).
4. `create_all()` doesn't add columns to existing tables. Use a migration script or Alembic.
5. Put `.env` in `.gitignore` before the first commit. In the cloud, use GitHub Secrets.
6. Use an explicit `ENVIRONMENT` variable to switch local/prod.
7. Create tables on startup, so a fresh Neon database works.
8. **Gemini free tier, 429 errors:** throttle and retry with backoff. Rank first, summarize later.
9. **Feeds are large** (up to 200 items) and many are older than 24h, so always filter by `published_at`. Feeds also use different date formats and time zones (IST vs UTC), so normalise everything to UTC.
10. **Google News links** go through a `news.google.com` redirect. Store them as-is and use the title + source for display.
11. **Feeds change or die:** CNN's own RSS stopped in 2016. The feed health log catches feeds that go quiet.
12. **Same story, many outlets.** Dedupe by cleaned URL and similar titles so one event doesn't take 3 slots.
13. YouTube may block transcript requests from **GitHub's cloud IPs**. Fall back to the description, or run the job locally with Windows Task Scheduler.
14. GitHub disables scheduled workflows after 60 days with no repo activity.
15. Neon free databases sleep when idle, so retry the first connection.
16. **Copyright:** headlines, short descriptions and our own summaries with links only. Never copy full articles from news publishers.

> The video was recorded in Nov 2025. Feeds marked 🔎 and the Gemini model name get checked when we reach them.
