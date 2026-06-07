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

## Curated corpus (30–50 PDFs)

This repo includes a gold-standard subset of 50 PDFs in `curated_corpus/` with:

- `curated_corpus_manifest.jsonl` (per-document metadata)
- `curated_corpus_summary.md` (counts + listing)

To regenerate the curated corpus:

```bash
python curate_corpus.py
```

You can override source roots if your scrape outputs are in different folders:

```bash
python curate_corpus.py \
  --ktm-root /path/to/kathmandu_laws_scrape_YYYYMMDD_HHMMSS \
  --lmc-root /path/to/kathmandu_laws_scrape_YYYYMMDD_HHMMSS \
  --bkt-root /path/to/kathmandu_laws_scrape_YYYYMMDD_HHMMSS
```

## Hybrid extraction pipeline

The extraction layer routes `text_based` PDFs to PyMuPDF and `scanned` PDFs to Surya OCR (configured with an entrypoint and `mps` device for Apple Silicon acceleration). It also applies semantic chunking where headings are detected, falling back to fixed-size chunks.

Run the pipeline against the curated manifest:

```bash
python extract_corpus.py --surya-entrypoint surya_entrypoint:ocr_callable
```

Speed up OCR for scanned PDFs:

```bash
python extract_corpus.py --ocr-max-pages 2
```

Outputs are written to:

- `extraction_output/text/` (raw extracted text)
- `extraction_output/chunks/` (JSONL chunks)
- `extraction_output/extraction_summary.jsonl` (routing + metrics + errors)

Notes:

- The Surya OCR callable must accept `(pdf_path: Path, device: str)` and return either text or `(text, accuracy_score, accuracy_notes)`.
- OCR accuracy metrics are tracked per document as a confounding factor for downstream analysis.

## Embedding retrieval benchmark (FAISS)

This repo includes `embedding_benchmark.py`, a local (in-memory) semantic retrieval benchmark for evaluating embedding models on your chunk corpus.

### Metrics

- **Recall@5**: 1 if the ground-truth chunk appears in the top-5 neighbors, else 0 (averaged over queries)
- **MRR** (Mean Reciprocal Rank): average of $1/rank$ for the first correct chunk, else 0

### Run

On macOS, FAISS + PyTorch can conflict over OpenMP runtimes. The safest way to run is with these environment variables:

```bash
KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 ./.venv/bin/python embedding_benchmark.py \
  --chunks-dir extraction_output/chunks \
  --query-bank-md research_query_bank_v1.md \
  --output-csv retrieval_benchmark_results.csv \
  --top-k 5 \
  --batch-size 128
```

If `BAAI/bge-m3` is too slow to download (it’s a large model), you can run the baseline-only benchmark:

```bash
KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 ./.venv/bin/python embedding_benchmark.py \
  --chunks-dir extraction_output/chunks \
  --query-bank-md research_query_bank_v1.md \
  --output-csv retrieval_benchmark_results.csv \
  --skip-bge-m3
```
