"""Map ground-truth chunk IDs (from chunks_v2) to actual corpus chunk IDs (extraction_output/chunks).

Why this exists
---------------
Your query bank `research_query_bank_v2.md` references chunk IDs from `chunks_v2` (e.g.
`LMC_MUN_004_sec2_chunk_4`), but the evaluation corpus uses a different chunk_id format
(e.g. `LMC_MUN_004_section_17`).

Evaluation metrics (Recall@K/MRR) require exact chunk_id matching, so we must map
"v2 IDs" -> "corpus IDs".

Approach (A1)
-------------
For each query row:
  1) Read the ground-truth chunk text from chunks_v2 JSONL using the referenced chunk_id.
  2) Search only within the same document's corpus chunks (from extraction_output/chunks).
  3) Score candidates by lexical similarity (token Jaccard on normalized text).
  4) Pick the best corpus chunk_id and emit a mapping.

Outputs
-------
- A JSON mapping file: { query_id: {doc_id, v2_chunk_id, mapped_chunk_id, score} }

Usage
-----
./.venv/bin/python ground_truth_mapper.py \
  --chunks-v2-dir extraction_output/chunks_v2 \
  --chunks-dir extraction_output/chunks \
  --query-bank-md research_query_bank_v2.md \
  --output-json ground_truth_mapping.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


@dataclass(frozen=True)
class QueryRow:
    query_id: str
    doc_id: str
    v2_chunk_ids: Tuple[str, ...]


_MD_ROW_RE = re.compile(
    r"^\|\s*(Q\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)


def parse_query_bank(md_path: Path) -> List[QueryRow]:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    rows: List[QueryRow] = []

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("| ---"):
            continue
        if line.lower().startswith("| qid |"):
            continue

        m = _MD_ROW_RE.match(line)
        if not m:
            continue

        qid, _query_cell, _failure_mode, target_docs, expected_loc = m.groups()
        doc_id = re.split(r"[\s,]+", target_docs.strip())[0]
        v2_ids = tuple(re.findall(r"`([^`]+)`", expected_loc))
        if not v2_ids:
            continue
        rows.append(QueryRow(query_id=qid, doc_id=doc_id, v2_chunk_ids=v2_ids))

    if not rows:
        raise SystemExit(f"No query rows parsed from {md_path}")
    return rows


def normalize_text(s: str) -> str:
    s = s.lower()
    # keep letters/digits from both Latin and Devanagari; drop punctuation
    s = re.sub(r"[^\w\u0900-\u097F]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def token_set(s: str) -> set[str]:
    s = normalize_text(s)
    toks = [t for t in s.split(" ") if t]
    return set(toks)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def load_v2_chunk_text(chunks_v2_dir: Path, doc_id: str, chunk_id: str) -> str:
    fp = chunks_v2_dir / f"{doc_id}_chunks.jsonl"
    if not fp.exists():
        raise FileNotFoundError(fp)
    for obj in _iter_jsonl(fp):
        if obj.get("chunk_id") == chunk_id:
            return str(obj.get("text", ""))
    raise KeyError(f"chunk_id {chunk_id} not found in {fp}")


def load_corpus_doc_chunks(chunks_dir: Path, doc_id: str) -> List[Tuple[str, str]]:
    fp = chunks_dir / f"{doc_id}_chunks.jsonl"
    if not fp.exists():
        raise FileNotFoundError(fp)
    out: List[Tuple[str, str]] = []
    for obj in _iter_jsonl(fp):
        cid = obj.get("chunk_id")
        txt = obj.get("text")
        if isinstance(cid, str) and isinstance(txt, str) and cid and txt:
            out.append((cid, txt))
    if not out:
        raise ValueError(f"No chunks found in {fp}")
    return out


def map_query(
    chunks_v2_dir: Path, chunks_dir: Path, row: QueryRow
) -> Dict[str, object]:
    # Use the first v2 chunk id as primary (ranges include both endpoints).
    v2_primary = row.v2_chunk_ids[0]
    v2_text = load_v2_chunk_text(chunks_v2_dir, row.doc_id, v2_primary)
    v2_tokens = token_set(v2_text)

    corpus_chunks = load_corpus_doc_chunks(chunks_dir, row.doc_id)

    best = ("", -1.0)
    for cid, txt in corpus_chunks:
        score = jaccard(v2_tokens, token_set(txt))
        if score > best[1]:
            best = (cid, score)

    return {
        "query_id": row.query_id,
        "doc_id": row.doc_id,
        "v2_chunk_id": v2_primary,
        "mapped_chunk_id": best[0],
        "score": best[1],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks-v2-dir", type=Path, default=Path("extraction_output/chunks_v2"))
    ap.add_argument("--chunks-dir", type=Path, default=Path("extraction_output/chunks"))
    ap.add_argument("--query-bank-md", type=Path, default=Path("research_query_bank_v2.md"))
    ap.add_argument("--output-json", type=Path, default=Path("ground_truth_mapping.json"))
    args = ap.parse_args()

    rows = parse_query_bank(args.query_bank_md)

    mapping: Dict[str, object] = {}
    for r in rows:
        # Only rows whose doc exists in chunks_v2 can be mapped this way.
        v2_fp = args.chunks_v2_dir / f"{r.doc_id}_chunks.jsonl"
        corpus_fp = args.chunks_dir / f"{r.doc_id}_chunks.jsonl"
        if not v2_fp.exists() or not corpus_fp.exists():
            mapping[r.query_id] = {
                "query_id": r.query_id,
                "doc_id": r.doc_id,
                "v2_chunk_id": r.v2_chunk_ids[0],
                "mapped_chunk_id": None,
                "score": None,
                "reason": "missing_doc_in_chunks_v2_or_corpus",
            }
            continue

        mapping[r.query_id] = map_query(args.chunks_v2_dir, args.chunks_dir, r)

    args.output_json.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote mapping: {args.output_json}")


if __name__ == "__main__":
    main()
