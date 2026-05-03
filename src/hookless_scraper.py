import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

CONFIG_PATH = "config/sites.json"
OUTPUT_JSON = "data/results.json"
OUTPUT_CSV = "data/results.csv"
LOG_JSON = "data/scrape_log.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_html(url, headers, timeout):
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return {
            "ok": r.status_code == 200,
            "status_code": r.status_code,
            "html": r.text if r.status_code == 200 else "",
            "final_url": r.url,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "html": "",
            "final_url": url,
            "error": str(exc),
        }


def extract_title_and_blocks(html):
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Remove non-content elements.
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        tag.decompose()

    # Use common article text blocks, not just <p>, because some sites use div/li headings.
    selectors = ["h1", "h2", "h3", "p", "li", "figcaption", "blockquote"]
    blocks = []
    seen = set()
    for element in soup.find_all(selectors):
        text = element.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 25:
            continue
        if text not in seen:
            seen.add(text)
            blocks.append(text)
    return title, blocks


def normalise(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def term_present(text, term):
    """Robust phrase matcher.

    Uses case-insensitive substring matching with whitespace normalization.
    This is intentionally less brittle than word-boundary regex because cycling
    media often uses punctuation, hyphenation, or plural forms inconsistently.
    """
    return normalise(term) in normalise(text)


def match_terms(blocks, terms):
    matches = []
    for block in blocks:
        matched_terms = [term for term in terms if term_present(block, term)]
        if matched_terms:
            matches.append({
                "text": block,
                "matched_terms": sorted(set(matched_terms)),
            })
    return matches


def process_url(url, config):
    headers = {"User-Agent": config["user_agent"]}
    response = fetch_html(url, headers, config["timeout_seconds"])

    log = {
        "url": url,
        "final_url": response["final_url"],
        "status_code": response["status_code"],
        "ok": response["ok"],
        "error": response["error"],
        "blocks_extracted": 0,
        "matches_found": 0,
    }

    if not response["ok"]:
        return [], log

    title, blocks = extract_title_and_blocks(response["html"])
    matches = match_terms(blocks, config["terms"])
    log["blocks_extracted"] = len(blocks)
    log["matches_found"] = len(matches)
    log["title"] = title

    records = []
    for idx, match in enumerate(matches, start=1):
        records.append({
            "source_url": url,
            "final_url": response["final_url"],
            "domain": urlparse(response["final_url"]).netloc,
            "title": title,
            "match_index": idx,
            "matched_terms": match["matched_terms"],
            "text": match["text"],
            "scraped_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })
    return records, log


def main():
    config = load_config()
    all_records = []
    logs = []

    print("Processing seed URLs...")
    for url in tqdm(config["seed_urls"]):
        records, log = process_url(url, config)
        all_records.extend(records)
        logs.append(log)
        time.sleep(config["request_delay_seconds"])

    os.makedirs("data", exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    pd.DataFrame(all_records).to_csv(OUTPUT_CSV, index=False)

    print("\nScrape summary:")
    for log in logs:
        print(f"- {log['status_code']} | blocks={log['blocks_extracted']} | matches={log['matches_found']} | {log['url']}")
    print(f"\nSaved {len(all_records)} records")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_CSV}")
    print(f"Wrote {LOG_JSON}")


if __name__ == "__main__":
    main()
