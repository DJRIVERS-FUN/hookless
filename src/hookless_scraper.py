import json
import time
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

CONFIG_PATH = "config/sites.json"
OUTPUT_JSON = "data/results.json"
OUTPUT_CSV = "data/results.csv"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_html(url, headers, timeout):
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None


def extract_paragraphs(html):
    soup = BeautifulSoup(html, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return paragraphs


def match_terms(paragraphs, terms):
    matches = []
    for p in paragraphs:
        for t in terms:
            if re.search(rf"\\b{re.escape(t)}\\b", p, re.IGNORECASE):
                matches.append(p)
                break
    return matches


def process_url(url, config):
    headers = {"User-Agent": config["user_agent"]}
    html = fetch_html(url, headers, config["timeout_seconds"])
    if not html:
        return []

    paragraphs = extract_paragraphs(html)
    matches = match_terms(paragraphs, config["terms"])

    records = []
    for m in matches:
        records.append({
            "url": url,
            "domain": urlparse(url).netloc,
            "text": m
        })
    return records


def main():
    config = load_config()
    all_records = []

    print("Processing seed URLs...")
    for url in tqdm(config["seed_urls"]):
        records = process_url(url, config)
        all_records.extend(records)
        time.sleep(config["request_delay_seconds"])

    # Save JSON
    import os
    os.makedirs("data", exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    # Save CSV
    import pandas as pd
    pd.DataFrame(all_records).to_csv(OUTPUT_CSV, index=False)

    print(f"Saved {len(all_records)} records")


if __name__ == "__main__":
    main()
