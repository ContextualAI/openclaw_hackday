"""
OpenClaw SEC Scraper
Scrapes SEC filings from EDGAR (free, no API key) and optionally Brave Search,
converts results to PDFs, and uploads them to a Contextual AI datastore.
"""

import os
import sys
import json
import hashlib
import tempfile
import time
import requests
from datetime import datetime, timedelta


CONTEXTUAL_API_KEY = os.environ["CONTEXTUAL_API_KEY"]
DATASTORE_ID = os.environ["DATASTORE_ID"]
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

CONTEXTUAL_UPLOAD_URL = f"https://api.contextual.ai/v1/datastores/{DATASTORE_ID}/documents"

# EDGAR full-text search API (free, no key needed)
EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# SEC requires a User-Agent header with contact info
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "OpenClaw SEC Monitor (demo@example.com)")

# Filing types to scrape from EDGAR
EDGAR_FILING_TYPES = ["8-K", "10-K", "10-Q", "20-F", "DEF 14A"]


def edgar_search(form_type: str, date_from: str = None, count: int = 40) -> list[dict]:
    """Search EDGAR full-text search for filings by form type."""
    if not date_from:
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    url = "https://efts.sec.gov/LATEST/search-index"
    params = {
        "q": f'formType:"{form_type}"',
        "dateRange": "custom",
        "startdt": date_from,
        "enddt": datetime.now().strftime("%Y-%m-%d"),
        "from": 0,
        "size": count,
    }
    headers = {"User-Agent": SEC_USER_AGENT}

    # Use the simpler EDGAR full-text search API
    search_url = "https://efts.sec.gov/LATEST/search-index"

    # Fall back to the EDGAR filing search
    resp = requests.get(
        "https://www.sec.gov/cgi-bin/browse-edgar",
        params={
            "action": "getcompany",
            "type": form_type,
            "dateb": "",
            "owner": "include",
            "count": count,
            "search_text": "",
            "output": "atom",
        },
        headers=headers,
    )
    resp.raise_for_status()
    return resp.text


def edgar_full_text_search(query: str, form_types: list[str] = None,
                            date_from: str = None, count: int = 50) -> list[dict]:
    """Search EDGAR using the full-text search API."""
    if not date_from:
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    params = {
        "q": query,
        "dateRange": "custom",
        "startdt": date_from,
        "enddt": datetime.now().strftime("%Y-%m-%d"),
    }
    if form_types:
        params["forms"] = ",".join(form_types)

    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}

    resp = requests.get(
        "https://efts.sec.gov/LATEST/search-index",
        params=params,
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("hits", {}).get("hits", [])


def fetch_edgar_filing_page(filing_url: str) -> str:
    """Fetch the actual filing page from EDGAR."""
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = requests.get(filing_url, headers=headers)
    resp.raise_for_status()
    return resp.text


def search_edgar_filings(form_type: str, date_from: str = None, count: int = 50) -> list[dict]:
    """Search EDGAR for recent filings using the full-text search API."""
    if not date_from:
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}

    resp = requests.get(
        "https://efts.sec.gov/LATEST/search-index",
        params={
            "q": f'"{form_type}"',
            "forms": form_type,
            "dateRange": "custom",
            "startdt": date_from,
            "enddt": datetime.now().strftime("%Y-%m-%d"),
        },
        headers=headers,
    )

    if resp.status_code != 200:
        # Fallback: use the EDGAR full-text search
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": form_type, "from": "0", "size": str(count)},
            headers=headers,
        )

    if resp.status_code != 200:
        print(f"  EDGAR search failed ({resp.status_code}), trying alternative...")
        return search_edgar_rss(form_type, count)

    try:
        data = resp.json()
        return data.get("hits", {}).get("hits", [])
    except Exception:
        return search_edgar_rss(form_type, count)


def search_edgar_rss(form_type: str, count: int = 40) -> list[dict]:
    """Fallback: use EDGAR RSS feed for recent filings."""
    import xml.etree.ElementTree as ET

    headers = {"User-Agent": SEC_USER_AGENT}

    # EDGAR RSS feed for recent filings
    resp = requests.get(
        "https://www.sec.gov/cgi-bin/browse-edgar",
        params={
            "action": "getcurrent",
            "type": form_type,
            "company": "",
            "dateb": "",
            "owner": "include",
            "count": count,
            "search_text": "",
            "start": 0,
            "output": "atom",
        },
        headers=headers,
    )
    resp.raise_for_status()

    results = []
    try:
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            link = entry.find("atom:link", ns)
            summary = entry.find("atom:summary", ns)
            updated = entry.find("atom:updated", ns)

            results.append({
                "title": title.text if title is not None else "Untitled",
                "url": link.get("href", "") if link is not None else "",
                "description": summary.text if summary is not None else "",
                "date": updated.text if updated is not None else "",
                "form_type": form_type,
                "source": "edgar_rss",
            })
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")

    return results


def extract_text_from_html(html_content: str, max_chars: int = 100000) -> str:
    """Extract clean text from HTML, skipping scripts/styles."""
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.skip_tags = {"script", "style", "head"}
            self.current_skip = False

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self.current_skip = True

        def handle_endtag(self, tag):
            if tag in self.skip_tags:
                self.current_skip = False

        def handle_data(self, data):
            if not self.current_skip:
                stripped = data.strip()
                if stripped:
                    self.text_parts.append(stripped)

    extractor = TextExtractor()
    extractor.feed(html_content[:max_chars])
    return "\n".join(extractor.text_parts)


def fetch_actual_filing(index_url: str) -> str:
    """Given an EDGAR index page URL, find and fetch the actual filing document."""
    import re
    headers = {"User-Agent": SEC_USER_AGENT}

    try:
        resp = requests.get(index_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return ""

        # Find the actual filing .htm link (not the index itself)
        # EDGAR index pages have links like /Archives/edgar/data/.../filename.htm
        htm_links = re.findall(r'href="(/Archives/edgar/data/[^"]+\.htm)"', resp.text)
        if not htm_links:
            # Try inline viewer links
            ix_links = re.findall(r'href="/ix\?doc=(/Archives/edgar/data/[^"]+\.htm)"', resp.text)
            if ix_links:
                htm_links = ix_links

        if not htm_links:
            return ""

        # Fetch the actual filing document
        filing_url = f"https://www.sec.gov{htm_links[0]}"
        time.sleep(0.2)  # Be polite to SEC servers
        filing_resp = requests.get(filing_url, headers=headers, timeout=20)
        if filing_resp.status_code == 200:
            return extract_text_from_html(filing_resp.text, max_chars=200000)
    except Exception as e:
        print(f"    Could not fetch filing content: {e}")

    return ""


def filing_to_html(filing: dict) -> str:
    """Convert a filing result into an HTML document for PDF conversion."""
    title = filing.get("title", "Untitled")
    url = filing.get("url", "")
    description = filing.get("description", "No description available.")
    date = filing.get("date", "")
    form_type = filing.get("form_type", "")

    # Fetch the ACTUAL filing content (not just the index page)
    filing_content = ""
    if url and "sec.gov" in url:
        print(f"    Fetching full filing from EDGAR...")
        raw_text = fetch_actual_filing(url)
        if raw_text:
            filing_content = f"<h2>Full Filing Content</h2><pre>{raw_text[:80000]}</pre>"
        else:
            # Fallback: extract what we can from the index page
            try:
                headers = {"User-Agent": SEC_USER_AGENT}
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    extracted = extract_text_from_html(resp.text)
                    if extracted:
                        filing_content = f"<h2>Filing Index Content</h2><pre>{extracted[:40000]}</pre>"
            except Exception:
                pass

    # Clean description of HTML tags
    if description:
        clean_desc = extract_text_from_html(f"<p>{description}</p>")
        description = clean_desc or description

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{title}</h1>
<p><strong>Form Type:</strong> {form_type}</p>
<p><strong>Source:</strong> <a href="{url}">{url}</a></p>
<p><strong>Date:</strong> {date}</p>
<hr>
<p>{description}</p>
{filing_content}
</body>
</html>"""


def html_to_pdf(html_content: str, output_path: str):
    """Convert HTML string to PDF using weasyprint."""
    from weasyprint import HTML
    HTML(string=html_content).write_pdf(output_path)


def upload_to_contextual(pdf_path: str, metadata: dict) -> str:
    """Upload a PDF to the Contextual AI datastore."""
    headers = {"Authorization": f"Bearer {CONTEXTUAL_API_KEY}"}
    with open(pdf_path, "rb") as f:
        files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
        data = {"metadata": json.dumps({"custom_metadata": metadata})}
        resp = requests.post(CONTEXTUAL_UPLOAD_URL, headers=headers, files=files, data=data)
    resp.raise_for_status()
    return resp.json().get("id", "unknown")


def dedupe_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def run_edgar_scrape():
    """Scrape filings directly from EDGAR (no API key needed)."""
    seen = set()
    uploaded = 0
    skipped = 0

    for form_type in EDGAR_FILING_TYPES:
        print(f"\n--- EDGAR: Fetching {form_type} filings ---")
        time.sleep(0.5)  # SEC asks for max 10 requests/sec

        results = search_edgar_rss(form_type, count=40)
        print(f"  Found {len(results)} results")

        for filing in results:
            url = filing.get("url", "")
            if not url:
                continue

            doc_hash = dedupe_id(url)
            if doc_hash in seen:
                continue
            seen.add(doc_hash)

            title = filing.get("title", "Untitled")
            print(f"  Processing: {title[:80]}")

            try:
                html = filing_to_html(filing)
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    pdf_path = tmp.name
                html_to_pdf(html, pdf_path)

                metadata = {
                    "title": title[:200],
                    "url": url,
                    "form_type": filing.get("form_type", ""),
                    "source": "edgar",
                    "scraped_at": datetime.now().isoformat(),
                }
                doc_id = upload_to_contextual(pdf_path, metadata)
                print(f"    Uploaded -> {doc_id}")
                uploaded += 1

                # Be polite to SEC servers
                time.sleep(0.2)

            except Exception as e:
                print(f"    ERROR: {e}")
            finally:
                if 'pdf_path' in locals() and os.path.exists(pdf_path):
                    os.remove(pdf_path)

    print(f"\n=== EDGAR scrape done: {uploaded} uploaded, {skipped} skipped ===")
    return uploaded


def run_brave_scrape():
    """Scrape via Brave Search (uses API key, has rate limits)."""
    if not BRAVE_API_KEY:
        print("No BRAVE_API_KEY set, skipping Brave scrape.")
        return 0

    SEARCH_QUERIES = os.environ.get(
        "SEARCH_TERMS",
        ",".join([
            "site:sec.gov 8-K current report 2026",
            "site:sec.gov 10-K annual report 2026",
            "site:sec.gov DEF 14A proxy statement 2026",
        ])
    ).split(",")

    # Domains to reject
    BLOCKED_DOMAINS = [
        "wikipedia.org", "youtube.com", "reddit.com", "twitter.com",
        "x.com", "facebook.com", "tiktok.com", "instagram.com",
        "vmware.com", "quora.com", "medium.com", "stackoverflow.com",
    ]

    SEC_KEYWORDS = [
        "10-k", "10-q", "8-k", "20-f", "def 14a", "proxy",
        "sec filing", "sec report", "annual report", "quarterly report",
        "current report", "edgar", "securities and exchange",
        "form s-", "form 4", "form 3", "10k", "10q", "8k",
    ]

    seen = set()
    uploaded = 0

    for i, query in enumerate(SEARCH_QUERIES):
        query = query.strip()
        if i > 0:
            print("  Waiting 2s (rate limit)...")
            time.sleep(2)

        print(f"\n--- Brave: {query} ---")
        try:
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
                params={"q": query, "count": 20, "freshness": "pw"},
            )
            resp.raise_for_status()
            results = resp.json().get("web", {}).get("results", [])
            print(f"  Found {len(results)} results")
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                print(f"  Rate limited, skipping remaining Brave queries.")
                break
            raise

        for result in results:
            url = result.get("url", "")
            doc_hash = dedupe_id(url)
            if doc_hash in seen:
                continue
            seen.add(doc_hash)

            title = result.get("title", "Untitled")
            url_lower = url.lower()
            title_lower = title.lower()

            if any(d in url_lower for d in BLOCKED_DOMAINS):
                continue
            if not any(kw in title_lower for kw in SEC_KEYWORDS):
                continue

            print(f"  Processing: {title[:80]}")
            try:
                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{title}</h1>
<p><strong>Source:</strong> <a href="{url}">{url}</a></p>
<p><strong>Date:</strong> {result.get('age', '')}</p>
<hr>
<p>{result.get('description', '')}</p>
{''.join(f'<p>{s}</p>' for s in result.get('extra_snippets', []))}
</body></html>"""

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    pdf_path = tmp.name
                html_to_pdf(html, pdf_path)

                metadata = {
                    "title": title[:200],
                    "url": url,
                    "source": "brave_search",
                    "search_query": query,
                    "scraped_at": datetime.now().isoformat(),
                }
                doc_id = upload_to_contextual(pdf_path, metadata)
                print(f"    Uploaded -> {doc_id}")
                uploaded += 1
            except Exception as e:
                print(f"    ERROR: {e}")
            finally:
                if 'pdf_path' in locals() and os.path.exists(pdf_path):
                    os.remove(pdf_path)

    print(f"\n=== Brave scrape done: {uploaded} uploaded ===")
    return uploaded


def run_scrape():
    """Run one full scrape cycle — EDGAR first (free), then Brave (optional)."""
    print("=" * 60)
    print("Starting SEC filing scrape")
    print("=" * 60)

    # Phase 1: EDGAR (free, no rate limit issues)
    edgar_count = run_edgar_scrape()

    # Phase 2: Brave Search (optional, uses API quota)
    brave_count = run_brave_scrape()

    total = edgar_count + brave_count
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total} documents uploaded ({edgar_count} EDGAR + {brave_count} Brave)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_scrape()
    elif "--edgar-only" in sys.argv:
        run_edgar_scrape()
    else:
        # Scheduled mode: run once per day
        while True:
            print(f"\n[{datetime.now().isoformat()}] Starting scheduled scrape...")
            run_scrape()
            print("Sleeping 24 hours until next run...")
            time.sleep(86400)
