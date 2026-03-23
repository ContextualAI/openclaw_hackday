"""
OpenClaw SEC Chat Bot — simple back-and-forth with the Contextual AI SEC agent.
No Claude, no web search — just your SEC filing database via Telegram.
"""

import os
import time
import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CONTEXTUAL_API_KEY = os.environ["CONTEXTUAL_API_KEY"]
AGENT_ID = os.environ["AGENT_ID"]

CONTEXTUAL_BASE = "https://api.contextual.ai/v1"


def query_sec_agent(question: str) -> str:
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


def main():
    print("OpenClaw SEC chat bot starting...")

    last_update_id = None
    existing = get_updates()
    if existing.get("result"):
        last_update_id = existing["result"][-1]["update_id"] + 1
        print(f"Skipped {len(existing['result'])} old message(s).")

    print("Listening for messages...\n")

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
                send_telegram("Searching SEC filings...")

                try:
                    answer = query_sec_agent(text)
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
