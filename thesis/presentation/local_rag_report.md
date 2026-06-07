# Local LangChain RAG Results

This run uses `langchain-core`, a local TF-IDF database, and an offline extractive answer generator.
The database is stored in `local_rag_db/documents.jsonl`.

## Evaluation

- Query set: 15 layperson/code-switched queries from `query_bank_unicode_v2.jsonl`
- Top-k: 3
- Recall@3: 1.000
- MRR: 1.000
- Query types: {'baseline_nepali': 5, 'code_switched_mixed': 5, 'code_switched_roman': 5}

## Sample Answer

**Question:** नक्सा pass application सँग कुन documents बुझाउनुपर्छ?

**Answer:** For Bhaktapur map-pass application, attach land ownership paper, latest tax receipt, cadastral map/blueprint, citizenship copy, site plan, designer certificate, neighbor consent if required, photos, construction-date proof, and ward recommendation.

**Citations:**
- `BKT_MUN_001_sec3_chunk_1` (`BKT_MUN_001`), score=0.3828
- `LMC_MUN_004_sec2_chunk_4` (`LMC_MUN_004`), score=0.1587
- `BKT_MUN_001_sec3_chunk_5` (`BKT_MUN_001`), score=0.1084

## Interpretation

The normalized local DB performs well because the chunks are stored in readable language.
The raw PDF corpus still needs font normalization/OCR cleanup before the same performance can be expected over all 50 documents.
