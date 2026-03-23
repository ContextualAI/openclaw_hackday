"""
OpenClaw Telegram Agent — Claude-powered assistant with tools.

Tools available:
  - brave_search: Search the live web for anything
  - query_sec_filings: Query your Contextual AI SEC filing datastore

Claude decides which tools to use (or none) based on the question.
"""

import os
import json
import time
import requests
import anthropic

# --- Config ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CONTEXTUAL_API_KEY = os.environ["CONTEXTUAL_API_KEY"]
AGENT_ID = os.environ["AGENT_ID"]
BRAVE_API_KEY = os.environ["BRAVE_API_KEY"]

CONTEXTUAL_BASE = "https://api.contextual.ai/v1"

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are OpenClaw, a helpful AI assistant that specializes in SEC filings, \
financial analysis, and general research. You have access to tools that let you:

1. Search the live web for current information (brave_search)
2. Query a curated database of recent SEC filings (query_sec_filings)

Use your tools when the user's question would benefit from real-time information or SEC filing data. \
For general knowledge questions, you can answer directly without tools.

Keep responses concise and well-formatted. When citing SEC filings, include the company name, \
filing type, and date when available."""

# --- Tool definitions for Claude ---
TOOLS = [
    {
        "name": "brave_search",
        "description": "Search the live web using Brave Search. Use this for current events, "
        "news, prices, company info, or anything that needs up-to-date information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results (default 5, max 20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_sec_filings",
        "description": "Query the SEC filing database for information about recent filings, "
        "regulatory changes, compliance risks, 8-K, 10-K, 10-Q, proxy statements, "
        "and other SEC documents that have been scraped and indexed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask about SEC filings",
                },
            },
            "required": ["question"],
        },
    },
]


# --- Tool implementations ---
def brave_search(query: str, count: int = 5) -> str:
    """Execute a Brave web search."""
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
        params={"q": query, "count": min(count, 20)},
    )
    resp.raise_for_status()
    results = resp.json().get("web", {}).get("results", [])
    formatted = []
    for r in results:
        formatted.append(f"**{r.get('title', '')}**\n{r.get('description', '')}\nURL: {r.get('url', '')}")
    return "\n\n".join(formatted) if formatted else "No results found."


def query_sec_filings(question: str) -> str:
    """Query the Contextual AI SEC agent."""
    resp = requests.post(
        f"{CONTEXTUAL_BASE}/agents/{AGENT_ID}/query",
        headers={
            "Authorization": f"Bearer {CONTEXTUAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"messages": [{"role": "user", "content": question}]},
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def run_tool(name: str, input_data: dict) -> str:
    """Dispatch a tool call."""
    if name == "brave_search":
        return brave_search(input_data["query"], input_data.get("count", 5))
    elif name == "query_sec_filings":
        return query_sec_filings(input_data["question"])
    else:
        return f"Unknown tool: {name}"


# --- Claude agent loop ---
def ask_openclaw(user_message: str) -> str:
    """Send a message to Claude with tools, handle tool calls, return final answer."""
    messages = [{"role": "user", "content": user_message}]

    # Allow up to 5 tool-use rounds
    for _ in range(5):
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # If Claude is done (no tool use), extract the text
        if response.stop_reason == "end_turn":
            text_parts = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_parts)

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  Tool call: {block.name}({json.dumps(block.input)[:100]})")
                try:
                    result = run_tool(block.name, block.input)
                except Exception as e:
                    result = f"Tool error: {e}"
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )

        # Feed tool results back to Claude
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "I ran out of steps trying to answer your question. Try being more specific."


# --- Telegram functions ---
def send_telegram(text: str):
    """Send a message via Telegram (splits long messages)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk})


def get_updates(offset=None):
    """Long-poll Telegram for new messages."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# --- Main loop ---
def main():
    print("OpenClaw agent starting (Claude + Brave + SEC filings)...")

    last_update_id = None
    existing = get_updates()
    if existing.get("result"):
        last_update_id = existing["result"][-1]["update_id"] + 1
        print(f"Skipped {len(existing['result'])} old message(s).")

    print("Listening for Telegram messages...\n")

    while True:
        try:
            updates = get_updates(offset=last_update_id)
            for update in updates.get("result", []):
                last_update_id = update["update_id"] + 1
                message = update.get("message", {})
                text = message.get("text", "")
                chat_id = str(message.get("chat", {}).get("id", ""))

                if chat_id != TELEGRAM_CHAT_ID or not text:
                    continue

                print(f"Question: {text}")
                send_telegram("Thinking...")

                try:
                    answer = ask_openclaw(text)
                    print(f"Answer: {answer[:200]}...\n")
                    send_telegram(answer)
                except Exception as e:
                    error_msg = f"Sorry, I hit an error: {e}"
                    print(error_msg)
                    send_telegram(error_msg)

        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
