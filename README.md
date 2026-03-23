# SEC Filing Sentinel

An automated SEC filing monitor powered by OpenClaw and [Contextual AI](https://contextual.ai).

**OpenClaw** runs in a Docker container on a daily schedule, scraping recent SEC filings via [EDGAR RSS feeds](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=&dateb=&owner=include&count=40&search_text=&action=getcompany) (with optional [Brave Search](https://brave.com/search/api/) supplement), converting them to PDFs, and uploading them to a Contextual AI datastore. You query the agent from a Jupyter notebook whenever you want insights — and optionally get briefings sent to your phone via Telegram.

## Architecture

```
┌─────────────────────┐       ┌──────────────────────────┐
│  OpenClaw (Docker)  │──────▶│   Contextual AI (Cloud)  │
│  - EDGAR RSS feeds  │ PDF   │   - Datastore (indexed)  │
│  - Brave Search     │ upload│   - RAG Agent             │
│    (optional)       │       └──────────┬───────────────┘
│  - PDF conversion   │                  │ query
│  - Daily schedule   │
└─────────────────────┘
                                         ▼
                              ┌─────────────────────────┐
                              │  Notebook (your machine) │
                              │  - On-demand analysis    │
                              │  - Interactive questions  │
                              └──────────┬───────────────┘
                                         │ optional
                                         ▼
                              ┌─────────────────────────┐
                              │  Telegram Bot            │
                              │  - Daily briefings       │
                              │  - Alerts to your phone  │
                              └─────────────────────────┘
```

---

## Prerequisites

You'll need accounts and API keys from the following services before getting started.

### Required

| Service | What it's for | Sign up | Free tier? |
|---------|--------------|---------|------------|
| **Contextual AI** | Document storage + RAG agent | [contextual.ai](https://contextual.ai) | Yes |
| **Docker Desktop** | Runs OpenClaw in an isolated container | [docker.com](https://www.docker.com/products/docker-desktop/) | Yes |

> **Note:** EDGAR RSS scraping is free and requires no API key. This is the primary data source for SEC filings.

### Optional

| Service | What it's for | Sign up | Free tier? |
|---------|--------------|---------|------------|
| **Brave Search** | Supplemental web scraping for SEC filings | [brave.com/search/api](https://brave.com/search/api/) | Yes (1 query/sec, 2000/month) |
| **Telegram** | Receive briefings on your phone | [telegram.org](https://telegram.org) | Yes |
| **Anthropic** | OpenClaw agent reasoning | [console.anthropic.com](https://console.anthropic.com) | Credit required |

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/saskinosie/sec-openclaw.git
cd sec-openclaw
```

### 2. Set up API keys

```bash
cp example.env .env
```

Open `.env` and fill in your keys:

```env
# Required
CONTEXTUAL_API_KEY=your-contextual-api-key

# Optional
BRAVE_API_KEY=your-brave-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

See [Telegram Setup](#telegram-setup) below for how to get the bot token and chat ID.

### 3. Set up the Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Make sure Docker Desktop is running

Open Docker Desktop (or confirm it's running with `docker info`). OpenClaw runs entirely inside a container — nothing gets installed on your machine.

### 5. Run the notebook

Open `sec.ipynb` in VS Code (or Jupyter) and run through the parts in order:

| Part | What it does | Run when |
|------|-------------|----------|
| **Part 1** | Creates the Contextual AI datastore and agent | Once (first time setup) |
| **Part 2** | Builds and launches the OpenClaw Docker container | Each session |
| **Part 3** | Agent queries + Claude comparison | Demo showcase |
| **Part 4** | Telegram integration (4a: one-shot, 4b: SEC chat bot, 4c: full OpenClaw agent) | Optional |

---

## Docker Commands

OpenClaw runs in Docker to keep scraping isolated from your machine. It starts scraping immediately on launch and repeats every 24 hours.

```bash
# Build (required after changing scrape.py)
docker compose build --no-cache openclaw

# Start the container
docker compose up -d --build

# Watch the logs
docker compose logs -f openclaw

# Trigger a manual scrape
docker compose exec openclaw python scrape.py --once

# Stop everything
docker compose down
```

> **Note:** If you change `scrape.py`, you must rebuild with `--no-cache` or Docker will use the cached image with the old code.

---

## Telegram Setup

Telegram notifications are optional but recommended — they let OpenClaw send SEC briefings directly to your phone.

### Step 1: Create a bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a display name (e.g. "OpenClaw SEC Alerts")
4. Choose a username (must end in `bot`, e.g. `openclaw_sec_bot`)
5. BotFather replies with your **HTTP API token** — copy it

### Step 2: Get your chat ID

1. Open a chat with your new bot and send it any message (e.g. "hello")
2. Open this URL in your browser (replace `<TOKEN>` with your token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. In the JSON response, find `"chat":{"id":123456789}` — that number is your chat ID

### Step 3: Add to .env

```env
TELEGRAM_BOT_TOKEN=7123456789:AAF1234abcd...
TELEGRAM_CHAT_ID=123456789
```

### Step 4: Run Part 4 in the notebook

The cell queries the agent for a summary and sends it to your phone.

---

## Project Structure

```
sec_demo/
├── sec.ipynb              # Main notebook — setup, launch, query
├── docker-compose.yml     # Container orchestration for OpenClaw
├── requirements.txt       # Python deps for the notebook
├── example.env            # Template for API keys (safe to commit)
├── .env                   # Your actual keys (git-ignored)
├── .gitignore
├── README.md
├── AGENTS.md              # Codex project context (architecture, APIs, gotchas)
├── .codex/
│   └── config.toml        # Codex MCP server config (Context7 for live docs)
├── telegram_bot.py        # One-shot Telegram briefing script
├── telegram_sec_bot.py    # Interactive SEC chat bot for Telegram
└── openclaw/
    ├── Dockerfile         # Container image definition
    ├── requirements.txt   # Python deps for the container
    └── scrape.py          # EDGAR + Brave → PDF → Contextual upload
```

---

## Participant Resources

### Contextual AI

| Resource | Link |
|----------|------|
| Documentation | https://docs.contextual.ai/ |
| Python SDK | https://github.com/ContextualAI/contextual-client-python |
| Node SDK | https://github.com/ContextualAI/contextual-client-node |
| Agent Composer | https://contextual.ai/blog/introducing-agent-composer |
| Oryx (Agent UI) | https://github.com/ContextualAI/oryx |
| Datastore Sync | https://github.com/ContextualAI/datastore-sync |
| Demo Site | https://demo.contextual.ai/ |
| GitHub Org | https://github.com/ContextualAI |

### Tools & Frameworks

| Resource | Link |
|----------|------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |
| Brave Search API | https://brave.com/search/api/ |
| OpenAI Codex CLI | https://github.com/openai/codex |
| EDGAR Full-Text Search | https://efts.sec.gov/LATEST/search-index |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `429 Too Many Requests` from Brave | You're hitting the rate limit (1 req/sec on free tier). Wait a minute and retry. The scraper has built-in delays. |
| Docker build uses cached `scrape.py` | Run `docker compose build --no-cache openclaw` to force a fresh copy. |
| `QueryResource object is not callable` | Make sure you're using `client.agents.query.create(...)`, not `client.agents.query(...)`. |
| Telegram message not received | Confirm you sent a message to the bot first, and that your chat ID is correct. |
| Container logs show nothing | Python output may be buffered. The `PYTHONUNBUFFERED=1` env var in docker-compose.yml fixes this. |

---

## Codex Setup

[OpenAI Codex](https://github.com/openai/codex) is available natively in the coding platform used for this demo. This project includes an `AGENTS.md` and `.codex/config.toml` so Codex understands the codebase out of the box.

### Quick start

```bash
# Install Codex CLI (if not already available in your IDE)
npm install -g @openai/codex

# Trust this project (required for project-level MCP servers)
cd sec_demo
codex trust

# Start coding with Codex
codex
```

### What's preconfigured

| File | What it does |
|------|-------------|
| `AGENTS.md` | Gives Codex full project context: architecture, APIs, SDK patterns, env vars, and common gotchas |
| `.codex/config.toml` | Configures MCP servers — includes [Context7](https://github.com/upstash/context7) for live SDK doc lookups |

### Example prompts to try with Codex

```
# Ask about the Contextual AI SDK
"How do I create a new datastore and upload documents using the contextual-client Python SDK?"

# Ask it to build on the project
"Add a new tool to telegram_bot.py that lets the agent look up a company's latest filing by ticker symbol"

# Use Context7 for live docs
"Use context7 to look up the contextual-client Python SDK, then show me how to list all documents in a datastore"

# Debug help
"Why might the agent return empty results even though documents are uploaded?"
```

### Connecting Codex to Contextual AI docs

The `.codex/config.toml` includes a Context7 MCP server that can fetch library documentation on demand. To look up Contextual AI SDK docs, just ask Codex to "use context7 to look up contextual-client" in your prompt.

For deeper integration, you can also point Codex at the [Contextual AI docs](https://docs.contextual.ai/) directly by adding a custom MCP server or using [datastore-sync](https://github.com/ContextualAI/datastore-sync).

---

## Roadmap

- [ ] Telegram daily briefings on a schedule
- [ ] Track specific companies or filing types
- [ ] Alert on material events (executive changes, M&A, restatements)
