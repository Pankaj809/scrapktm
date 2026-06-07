# Hybrid Extraction Pipeline

This pipeline routes curated PDFs based on the `format_type` recorded during curation:

- **text_based** → PyMuPDF (fast text extraction)
- **scanned** → Surya OCR (GPU/MPS accelerated OCR)

It then performs semantic chunking with heading detection, and falls back to
fixed-size token chunks (512 tokens, 128 overlap) using `RecursiveCharacterTextSplitter`.

## Architecture

```
curated_corpus_manifest.jsonl
        │
        ▼
DocumentRouter ──────────────┐
  ├─ text_based → PyMuPDF     │
  └─ scanned   → Surya OCR    │
        │                     │
        ▼                     │
    extracted text            │
        │                     │
        ▼                     │
semantic chunking → fixed chunks
        │
        ▼
extraction_output/
  ├─ text/
  ├─ chunks/
  └─ extraction_summary.jsonl
```

## Routing Rules

- The router reads `format_type` from the manifest.
- `text_based` documents are always routed to PyMuPDF.
- `scanned` documents are always routed to Surya OCR.
- Unknown types default to PyMuPDF and emit a warning.

## OCR Accuracy Tracking

Surya OCR is expected to return either:

- `text`, or
- `(text, accuracy_score, accuracy_notes)`

Accuracy metrics are recorded in `extraction_summary.jsonl` to capture OCR
uncertainty as a confounding factor for downstream analysis.

## Logging

The pipeline logs:

- Routing decisions
- Processing times
- OCR accuracy metrics
- Extraction failures

Logs are written to `logs/extraction_pipeline.log` by default.

## Running

```
python extract_corpus.py --surya-entrypoint surya_entrypoint:ocr_callable
```

Speed up OCR runs by limiting pages:

```
python extract_corpus.py --ocr-max-pages 2
```

If Surya OCR is not yet installed, you can use the stub for a dry run:

```
python extract_corpus.py --surya-entrypoint surya_stub:ocr_callable
```

## Outputs

- `extraction_output/text/<doc_id>.txt`
- `extraction_output/chunks/<doc_id>_chunks.jsonl`
- `extraction_output/extraction_summary.jsonl`
