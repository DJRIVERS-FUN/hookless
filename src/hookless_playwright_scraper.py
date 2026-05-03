import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from tqdm import tqdm

CONFIG_PATH = "config/sites.json"
RAW_JSON = "data/playwright_results.json"
RAW_CSV = "data/playwright_results.csv"
CLASSIFIED_JSON = "data/classified_results.json"
CLASSIFIED_CSV = "data/classified_results.csv"
SUMMARY_JSON = "data/classification_summary.json"

CLASSIFICATION_RULES = {
    "risk_safety": [
        "risk", "safety", "unsafe", "danger", "dangerous", "failure", "fail",
        "blow off", "blow-off", "blowout", "burp", "crash", "incident", "accident",
        "pressure limit", "maximum pressure", "72.5 psi", "5 bar", "tire pressure",
        "tyre pressure", "overinflate", "compatibility warning"
    ],
    "performance_efficiency": [
        "performance", "aero", "aerodynamic", "faster", "speed", "rolling resistance",
        "weight", "lightweight", "stiffness", "efficiency", "wider", "comfort",
        "handling", "traction", "ride quality"
    ],
    "compatibility_constraint": [
        "compatible", "compatibility", "approved", "tire list", "tyre list",
        "approved tire", "approved tyre", "rim width", "internal width", "minimum width",
        "maximum width", "tubeless", "mounting", "bead", "sealant", "pressure chart"
    ],
    "standards_compliance": [
        "iso", "etrto", "uci", "standard", "standards", "regulation", "regulations",
        "certified", "certification", "compliance", "approved by", "guideline", "protocol"
    ],
    "manufacturer_authority": [
        "zipp", "sram", "dt swiss", "enve", "giant", "cadex", "reserve", "boyd",
        "manufacturer", "engineered", "designed", "tested", "lab tested", "quality control",
        "our wheels", "our rims", "we recommend", "we designed"
    ],
    "user_experience_opinion": [
        "i think", "i feel", "my experience", "i have", "i've", "i was", "i had",
        "forum", "reddit", "rider", "riders", "people say", "anecdotal", "experience",
        "trust", "confidence", "concern", "worried", "would not", "wouldn't"
    ],
    "controversy_debate": [
        "debate", "controversy", "controversial", "criticism", "criticised", "criticized",
        "argument", "dispute", "question", "concern", "backlash", "polarising", "polarizing"
    ]
}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalise(text):
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def term_present(text, term):
    return normalise(term) in normalise(text)


def classify_text(text, source_group):
    text_norm = normalise(text)
    labels = []
    scores = {}

    for label, keywords in CLASSIFICATION_RULES.items():
        hits = [kw for kw in keywords if kw in text_norm]
        if hits:
            labels.append(label)
            scores[label] = len(hits)

    # Source-group informed weak label. This does not replace text-based labels.
    if source_group == "manufacturer" and "manufacturer_authority" not in labels:
        labels.append("manufacturer_authority")
        scores["manufacturer_authority"] = 0.5
    if source_group == "forum_social_public" and "user_experience_opinion" not in labels:
        labels.append("user_experience_opinion")
        scores["user_experience_opinion"] = 0.5
    if source_group == "standards_policy" and "standards_compliance" not in labels:
        labels.append("standards_compliance")
        scores["standards_compliance"] = 0.5

    if not labels:
        labels = ["uncategorised"]
        scores["uncategorised"] = 0

    primary_label = max(scores, key=scores.get)
    return labels, primary_label, scores


def extract_blocks(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    blocks = []
    seen = set()
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "blockquote", "figcaption"]):
        txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if len(txt) > 30 and txt not in seen:
            seen.add(txt)
            blocks.append(txt)
    return blocks


def scrape_page(page, url, config):
    try:
        page.goto(url, timeout=config.get("timeout_seconds", 60000), wait_until="domcontentloaded")
        time.sleep(config.get("request_delay_seconds", 2.0))
        html = page.content()

        blocks = extract_blocks(html)
        matches = []

        for b in blocks:
            matched = [t for t in config["terms"] if term_present(b, t)]
            if matched:
                matches.append({"text": b, "terms": matched})

        return matches, {"ok": True, "blocks": len(blocks), "matches": len(matches), "error": None}

    except Exception as e:
        return [], {"ok": False, "blocks": 0, "matches": 0, "error": str(e)}


def build_summary(df):
    if df.empty:
        return {
            "total_records": 0,
            "by_source_group": {},
            "by_primary_label": {},
            "label_counts": {},
        }

    label_counts = {}
    for labels in df["labels"]:
        for label in str(labels).split(";"):
            label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "total_records": int(len(df)),
        "by_source_group": df["source_group"].value_counts().to_dict(),
        "by_primary_label": df["primary_label"].value_counts().to_dict(),
        "label_counts": dict(sorted(label_counts.items(), key=lambda x: x[1], reverse=True)),
    }


def main():
    config = load_config()
    results = []
    logs = []

    os.makedirs("data", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=config.get("user_agent"))
        page = context.new_page()

        for group in config["source_groups"]:
            group_name = group["name"]
            print(f"\nProcessing group: {group_name}")

            for url in tqdm(group["seed_urls"]):
                matches, log = scrape_page(page, url, config)
                log.update({"source_group": group_name, "url": url, "domain": urlparse(url).netloc})
                logs.append(log)

                for m in matches:
                    labels, primary_label, scores = classify_text(m["text"], group_name)
                    results.append({
                        "source_group": group_name,
                        "domain": urlparse(url).netloc,
                        "url": url,
                        "terms": ";".join(sorted(set(m["terms"]))),
                        "labels": ";".join(labels),
                        "primary_label": primary_label,
                        "classification_scores": json.dumps(scores, ensure_ascii=False),
                        "text": m["text"],
                        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    })

        browser.close()

    df = pd.DataFrame(results)
    df.to_csv(RAW_CSV, index=False)
    df.to_csv(CLASSIFIED_CSV, index=False)

    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    with open(CLASSIFIED_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    with open("data/scrape_log.json", "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    summary = build_summary(df)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(results)} classified records")
    print("\nSource breakdown:")
    print(summary.get("by_source_group", {}))
    print("\nPrimary-label breakdown:")
    print(summary.get("by_primary_label", {}))
    print(f"\nWrote {CLASSIFIED_CSV}")
    print(f"Wrote {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
