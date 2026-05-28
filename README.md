# Kathmandu Laws Scraper

This project scrapes all paginated listings under three categories on `law.kathmandu.gov.np`, visits each law detail page, extracts all linked PDFs, and downloads them into a structured output directory.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python scrape_kathmandu_laws.py
```

Optional knobs:

```bash
python scrape_kathmandu_laws.py --delay 1.2 --jitter 0.8 --timeout 30
```

## Output

Each run creates a timestamped folder like:

- `kathmandu_laws_scrape_YYYYMMDD_HHMMSS/`
  - `national_laws/`, `provincial_laws/`, `historical_laws/`
    - `pdfs/<law-title>/<nn>_<pdf-name>.pdf`
    - `items.jsonl` (per-detail-page metadata)
    - `items.csv` (per-detail-page metadata, CSV)
    - `manifest.json` (counts + errors)
  - `run_summary.json`
  - `scrape.log`

Note: The site currently presents an SSL chain issue. The scraper retries failed SSL handshakes without verification and logs a warning so the crawl can complete.

