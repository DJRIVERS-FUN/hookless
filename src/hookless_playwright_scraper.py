import json
import time
import re
import os
from datetime import datetime
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

CONFIG_PATH = "config/sites.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalise(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def term_present(text, term):
    return normalise(term) in normalise(text)


def extract_blocks(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    blocks = []
    for el in soup.find_all(["p", "li", "h2", "h3", "blockquote"]):
        txt = el.get_text(" ", strip=True)
        if len(txt) > 30:
            blocks.append(txt)
    return blocks


def scrape_page(page, url, config):
    try:
        page.goto(url, timeout=30000)
        time.sleep(2)
        html = page.content()

        blocks = extract_blocks(html)
        matches = []

        for b in blocks:
            matched = [t for t in config["terms"] if term_present(b, t)]
            if matched:
                matches.append({
                    "text": b,
                    "terms": matched
                })

        return matches

    except Exception as e:
        print(f"Error: {url} -> {e}")
        return []


def main():
    config = load_config()
    results = []

    os.makedirs("data", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for url in tqdm(config["seed_urls"]):
            matches = scrape_page(page, url, config)

            for m in matches:
                results.append({
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "text": m["text"],
                    "terms": ",".join(m["terms"]),
                    "timestamp": datetime.utcnow().isoformat()
                })

        browser.close()

    with open("data/playwright_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    pd.DataFrame(results).to_csv("data/playwright_results.csv", index=False)

    print(f"Saved {len(results)} records")


if __name__ == "__main__":
    main()
