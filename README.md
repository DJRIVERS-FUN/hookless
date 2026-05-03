# Hookless Rim Media Discourse Scraper

This project extracts mentions of **hooked rims** and **hookless rims** from cycling-related media sources.

## Purpose

Supports research on:
- technological discourse in cycling media
- safety narratives and risk framing
- adoption and resistance to hookless rim systems

## Output

- `data/results.json`
- `data/results.csv`

Each record includes:
- URL
- domain
- extracted paragraph containing keyword match

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python src/hookless_scraper.py
```

## Config

Edit:
```
config/sites.json
```

- add domains
- add seed URLs
- modify keywords

## Notes

- This scraper is polite (delays between requests)
- Does not bypass paywalls
- Designed for research text extraction only

## Next Steps

- Add search API (Google / SerpAPI / Bing)
- Add NLP classification (risk vs performance framing)
- Add time-series tracking of discourse

