# AGENTS.md

## Project Overview

SEC Filing Sentinel is an automated SEC filing monitor that pairs **OpenClaw** (a Dockerized scraper) with **Contextual AI** (cloud-hosted RAG). OpenClaw scrapes recent SEC filings from EDGAR RSS feeds (with optional Brave Search supplement), converts them to PDFs, and uploads them to a Contextual AI datastore. A Jupyter notebook handles initial setup and on-demand queries. A Telegram bot provides persistent conversational access powered by Claude (Anthropic).

## Architecture

```
OpenClaw scraper (Docker) --> PDFs --> Contextual AI datastore --> RAG agent
                                                                    |
                                                          Notebook / Telegram bot
```

- **OpenClaw service** (`docker-compose: openclaw`): Runs `scrape.py` on a 24-hour loop. Scrapes EDGAR RSS + Brave Search, converts HTML to PDF via WeasyPrint, uploads to Contextual AI datastore.
- **Telegram bot service** (`docker-compose: telegram-bot`): Runs `telegram_bot.py`. Long-polls Telegram for user messages, routes them through Claude (with tool use) to either Brave Search or the Contextual AI agent, sends answers back.
- **Notebook** (`sec.ipynb`): Part 1 creates the datastore + agent. Part 2 builds/launches Docker. Part 3 queries the agent. Part 4 sends Telegram briefings.
- **Contextual AI (cloud)**: Hosts the indexed datastore and RAG agent. All queries go through their REST API.

Both Docker services share the same image (built from `openclaw/Dockerfile`) but run different commands.

## Key APIs & SDKs

### Contextual AI Python SDK

```python
from contextual import ContextualAI

client = ContextualAI(api_key="...")

# Create a datastore
ds = client.datastores.create(name="SEC Filings")

# Create an agent
agent = client.agents.create(
    name="SEC Agent",
    datastore_ids=[ds.id],
    ...
)

# Query the agent -- NOTE the .create() call
resp = client.agents.query.create(
    agent_id=agent.id,
    messages=[{"role": "user", "content": "What 8-K filings were filed this week?"}]
)
```

**IMPORTANT:** Use `client.agents.query.create(...)` -- NOT `client.agents.query(...)`. The latter raises `QueryResource object is not callable`.

### Contextual AI REST API

- Base URL: `https://api.contextual.ai/v1`
- Auth: `Authorization: Bearer <CONTEXTUAL_API_KEY>`
- Docs: https://docs.contextual.ai/

### Anthropic SDK

Used in `telegram_bot.py` for Claude tool-use routing:

```python
import anthropic
client = anthropic.Anthropic(api_key="...")
response = client.messages.create(model="claude-sonnet-4-20250514", ...)
```

## File Map

```
sec_demo/
  sec.ipynb                  # Main notebook: setup, launch Docker, query agent, Telegram briefings
  sec_copy_local_database.ipynb  # Secondary notebook (local database copy)
  docker-compose.yml         # Two services: openclaw (scraper) and telegram-bot
  requirements.txt           # Notebook deps: contextual-client, python-dotenv, requests, anthropic
  example.env                # Template for all env vars (safe to commit)
  .env                       # Actual secrets (gitignored)
  README.md                  # User-facing docs
  AGENTS.md                  # This file
  openclaw/
    Dockerfile               # Python 3.12-slim + WeasyPrint system deps
    requirements.txt         # Container deps: requests, weasyprint, anthropic
    scrape.py                # EDGAR RSS + Brave Search scraper, HTML->PDF, upload to Contextual AI
    telegram_bot.py          # Claude-powered Telegram agent with brave_search and query_sec_filings tools
    telegram_sec_bot.py      # (Legacy/alternate Telegram bot, copied into image)
```

## Common Patterns

### Uploading documents to Contextual AI

Multipart form POST:

```python
requests.post(
    f"https://api.contextual.ai/v1/datastores/{DATASTORE_ID}/documents",
    headers={"Authorization": f"Bearer {CONTEXTUAL_API_KEY}"},
    files={"file": (filename, file_bytes, "application/pdf")},
    data={"metadata": json.dumps({"custom_metadata": {...}})},
)
```

### Querying the agent (REST)

```python
resp = requests.post(
    f"https://api.contextual.ai/v1/agents/{AGENT_ID}/query",
    headers={
        "Authorization": f"Bearer {CONTEXTUAL_API_KEY}",
        "Content-Type": "application/json",
    },
    json={"messages": [{"role": "user", "content": "..."}]},
)
answer = resp.json()["message"]["content"]
```

### Claude tool-use loop (Telegram bot)

The bot defines tools (`brave_search`, `query_sec_filings`), sends messages to Claude, processes any `tool_use` blocks by calling the real APIs, feeds results back, and repeats up to 5 rounds until Claude returns `end_turn`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CONTEXTUAL_API_KEY` | Yes | Contextual AI API key for datastore uploads and agent queries |
| `DATASTORE_ID` | Yes | ID of the Contextual AI datastore (created in notebook Part 1) |
| `AGENT_ID` | Yes | ID of the Contextual AI RAG agent (created in notebook Part 1) |
| `BRAVE_API_KEY` | Yes* | Brave Search API key. *Scraper falls back to EDGAR-only if absent. Required for Telegram bot. |
| `ANTHROPIC_API_KEY` | For bot | Anthropic API key for Claude in the Telegram bot |
| `SEARCH_TERMS` | No | Comma-separated Brave search queries. Has sensible defaults in scrape.py. |
| `TELEGRAM_BOT_TOKEN` | For bot | Telegram bot HTTP API token from @BotFather |
| `TELEGRAM_CHAT_ID` | For bot | Your Telegram chat ID for receiving messages |
| `SEC_USER_AGENT` | No | User-Agent string for SEC EDGAR requests (has a default) |
| `PYTHONUNBUFFERED` | Auto | Set to `1` in docker-compose.yml so container stdout is not buffered |

## Gotchas

1. **SDK query method**: Use `client.agents.query.create(agent_id=..., messages=[...])` -- NOT `client.agents.query()`. The latter raises `QueryResource object is not callable`.

2. **Docker cache and COPY'd files**: If you change `scrape.py` or `telegram_bot.py`, you must rebuild with `docker compose build --no-cache openclaw` or Docker will use the cached layer with old code.

3. **EDGAR rate limit**: SEC requests max 10 req/sec. The scraper uses `time.sleep(0.2)` between filing fetches and `time.sleep(0.5)` between form-type batches. Do not remove these delays.

4. **PYTHONUNBUFFERED=1**: Required in docker-compose.yml for Docker container stdout to appear in `docker compose logs`. Without it, Python buffers output and logs appear empty.

5. **Brave Search rate limit**: Free tier allows 1 req/sec, 2000/month. The scraper has 2-second delays between queries and catches 429 errors.

6. **WeasyPrint system deps**: The Dockerfile installs `libpango`, `libcairo`, etc. If you change the base image, these must be present or PDF generation fails silently.

7. **Response format**: Contextual AI agent query responses use `resp.json()["message"]["content"]` -- not `resp.json()["content"]` or `resp.json()["response"]`.
