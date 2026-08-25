"""Local embedding benchmark for semantic retrieval (FAISS + sentence-transformers).

What it does
------------
1) Loads a chunk corpus from JSONL files (default: extraction_output/chunks/*.jsonl)
2) Builds an in-memory FAISS index (cosine similarity via inner product on L2-normalized vectors)
3) Evaluates 11 research queries from research_query_bank_v1.md against two embedding models:
   - sentence-transformers/all-MiniLM-L6-v2 (baseline English)
   - BAAI/bge-m3 (multilingual)
4) Computes per-query metrics:
   - Recall@5 (hit-rate): 1 if ground-truth chunk appears in top-5, else 0
   - MRR: 1/rank of the first correct chunk (rank is 1-based), else 0
5) Writes a CSV suitable for reporting:
   model_name | query_id | recall_at_5 | mrr | retrieved_chunk_ids | ground_truth_chunk_id

Usage
-----
./.venv/bin/python embedding_benchmark.py \
  --chunks-dir extraction_output/chunks \
  --query-bank-md research_query_bank_v1.md \
  --output-csv retrieval_benchmark_results.csv

Notes
-----
- No external services; everything runs in-memory.
- This script assumes chunk JSONL objects contain at least: {chunk_id, text}.
- The query bank markdown is expected to have the table shown in research_query_bank_v1.md.
"""

from __future__ import annotations

# NOTE(macOS stability):
# FAISS (OpenMP) + PyTorch can load multiple OpenMP runtimes on macOS, which may abort
# or segfault. We set these env vars *before* importing heavy numeric libs as a pragmatic
# workaround for local research runs.
import os
import sys

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
# Hugging Face network defaults can be too aggressive on slow links.
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "120")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
# Honor the offline CLI flag before importing sentence-transformers/transformers.
# Those libraries read offline-related environment variables during import.
if "--local-files-only" in sys.argv:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse
import csv
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import torch

try:
    import faiss  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "faiss is required. Install faiss-cpu (or faiss) and retry. "
        f"Import error: {e}"
    )

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "sentence-transformers is required. Install sentence-transformers and retry. "
        f"Import error: {e}"
    )


# ----------------------------
# Data structures
# ----------------------------


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    doc_id: str | None = None


@dataclass(frozen=True)
class QueryCase:
    query_id: str
    query_text: str
    ground_truth_chunk_ids: Tuple[str, ...]
    target_doc_ids: Tuple[str, ...] = ()


# ----------------------------
# Corpus loading
# ----------------------------


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_corpus(chunks_dir: Path) -> List[Chunk]:
    jsonl_files = sorted(chunks_dir.glob("*_chunks.jsonl"))
    if not jsonl_files:
        raise SystemExit(f"No *_chunks.jsonl files found in: {chunks_dir}")

    chunks: List[Chunk] = []
    seen_ids: set[str] = set()

    for fp in jsonl_files:
        for obj in _iter_jsonl(fp):
            chunk_id = obj.get("chunk_id")
            text = obj.get("text")
            if not chunk_id or not isinstance(chunk_id, str):
                continue
            if not text or not isinstance(text, str):
                continue
            if chunk_id in seen_ids:
                # Deduplicate defensively to avoid index/ID mismatch.
                continue
            seen_ids.add(chunk_id)
            chunks.append(Chunk(chunk_id=chunk_id, text=text, doc_id=obj.get("doc_id")))

    if not chunks:
        raise SystemExit(f"No valid chunks loaded from: {chunks_dir}")

    return chunks


# ----------------------------
# Query bank parsing
# ----------------------------


_MD_ROW_RE = re.compile(
    r"^\|\s*(Q\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)


def _strip_wrapping_quotes(s: str) -> str:
    s = s.strip()
    # Handles “ ... ” and "...".
    if (s.startswith("\"") and s.endswith("\"")) or (s.startswith("“") and s.endswith("”")):
        return s[1:-1].strip()
    return s


def _extract_ground_truth_chunk_ids(expected_location_cell: str) -> Tuple[str, ...]:
    """Extract chunk IDs from the last column.

    Supports:
    - `CHUNK_ID`
    - `CHUNK_ID_A`–`CHUNK_ID_B`

    Returns one or more chunk_ids. For a range, we include BOTH endpoints as acceptable.
    (We *don't* expand the range because chunk naming may not be purely numeric.)
    """

    # Backtick-enclosed chunk IDs occur in the markdown.
    ids = re.findall(r"`([^`]+)`", expected_location_cell)
    if not ids:
        # Fallback: sometimes users may remove backticks.
        ids = re.findall(r"([A-Z]{2,}_\w+_chunk_\d+)", expected_location_cell)

    if not ids:
        raise ValueError(f"No ground-truth chunk_id found in: {expected_location_cell}")

    # Handle an en-dash range between two backticked IDs.
    # Example: `A`–`B` -> ids == ['A','B'] already.
    return tuple(dict.fromkeys(ids))  # preserve order, de-dupe


def _parse_target_doc_ids(target_docs_cell: str) -> Tuple[str, ...]:
    # Target Doc ID(s) column is usually like: LMC_MUN_004
    # Accept multiple ids separated by commas/spaces.
    parts = re.split(r"[\s,]+", target_docs_cell.strip())
    parts = [p for p in parts if p]
    return tuple(parts)


def _maybe_map_v2_chunk_id_to_corpus_chunk_id(gt_chunk_id: str, doc_id: str) -> str:
    """Best-effort mapping from chunks_v2-style IDs to extraction_output/chunks IDs.

    chunks_v2 IDs look like: DOC_sec9_chunk_1
    corpus IDs look like:    DOC_section_89

    There is no reversible mapping without additional metadata. However, your v2 IDs
    include a section number (e.g., sec9). In the base corpus, sections are sequential
    over the document. Empirically these docs tend to have many sections, so we map:

      DOC_sec{N}_chunk_*  ->  DOC_section_{N}

    This isn't perfect, but it gets evaluation off the "ghost ID" failure mode and is
    a reasonable first pass for research iteration.
    """

    m = re.search(r"_sec(\d+)_chunk_\d+", gt_chunk_id)
    if m:
        n = int(m.group(1))
        return f"{doc_id}_section_{n}"
    return gt_chunk_id


def load_query_bank_md(md_path: Path) -> List[QueryCase]:
    text = md_path.read_text(encoding="utf-8", errors="replace")

    cases: List[QueryCase] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("| ---"):
            continue
        # Skip header row
        if line.lower().startswith("| qid |"):
            continue

        m = _MD_ROW_RE.match(line)
        if not m:
            continue

        qid, query_cell, _failure_mode, target_docs, expected_loc = m.groups()
        query_text = _strip_wrapping_quotes(query_cell)
        gt_ids = _extract_ground_truth_chunk_ids(expected_loc)
        doc_ids = _parse_target_doc_ids(target_docs)

        # Apply a best-effort normalization/mapping of v2-style IDs to corpus IDs.
        mapped_ids: List[str] = []
        for gt in gt_ids:
            if doc_ids:
                mapped_ids.append(_maybe_map_v2_chunk_id_to_corpus_chunk_id(gt, doc_ids[0]))
            else:
                mapped_ids.append(gt)

        cases.append(
            QueryCase(
                query_id=qid,
                query_text=query_text,
                ground_truth_chunk_ids=tuple(mapped_ids),
                target_doc_ids=doc_ids,
            )
        )

    if not cases:
        raise SystemExit(f"No query rows parsed from: {md_path}")

    # Expecting exactly 11 (Q001..Q011) per your prompt.
    # If it changes later, we still run, but log the count.
    return cases


def apply_ground_truth_mapping(
    queries: List[QueryCase], mapping_path: Path | None
) -> List[QueryCase]:
    """Override ground-truth chunk IDs with a mapping file.

    The mapping file is produced by `ground_truth_mapper.py` and has shape:
      { "Q001": {"mapped_chunk_id": "DOC_section_...", ...}, ... }

    If a query_id is missing or mapped_chunk_id is null, that query's ground truth is unchanged.
    """

    if not mapping_path:
        return queries
    if not mapping_path.exists():
        raise SystemExit(f"ground-truth mapping file not found: {mapping_path}")

    raw = json.loads(mapping_path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise SystemExit(f"Invalid mapping JSON (expected object): {mapping_path}")

    out: List[QueryCase] = []
    for q in queries:
        entry = raw.get(q.query_id)
        mapped = None
        if isinstance(entry, dict):
            mapped = entry.get("mapped_chunk_id")
        if isinstance(mapped, str) and mapped:
            out.append(
                QueryCase(
                    query_id=q.query_id,
                    query_text=q.query_text,
                    ground_truth_chunk_ids=(mapped,),
                    target_doc_ids=q.target_doc_ids,
                )
            )
        else:
            out.append(q)
    return out


# ----------------------------
# FAISS indexing (cosine)
# ----------------------------


def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(norms, eps)


def build_faiss_cosine_index(vectors: np.ndarray) -> faiss.IndexFlatIP:
    """Cosine similarity via inner-product on L2-normalized vectors."""
    if vectors.dtype != np.float32:
        vectors = vectors.astype(np.float32)

    vectors = l2_normalize(vectors)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    try:
        faiss.omp_set_num_threads(1)
    except Exception:
        pass
    index.add(vectors)
    return index


# ----------------------------
# Metrics
# ----------------------------


def recall_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str], k: int) -> int:
    top_k = set(retrieved_ids[:k])
    return int(any(gt in top_k for gt in ground_truth_ids))


def reciprocal_rank(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str]) -> float:
    gt = set(ground_truth_ids)
    for i, rid in enumerate(retrieved_ids):
        if rid in gt:
            return 1.0 / (i + 1)
    return 0.0


# ----------------------------
# Benchmark loop
# ----------------------------


@dataclass
class PerQueryResult:
    model_name: str
    query_id: str
    recall_at_5: int
    mrr: float
    retrieved_chunk_ids: List[str]
    ground_truth_chunk_id: str


def embed_texts(model: SentenceTransformer, texts: List[str], batch_size: int = 64) -> np.ndarray:
    # sentence-transformers returns np.ndarray when convert_to_numpy=True.
    # We keep float32 for FAISS.
    emb = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=False,
        show_progress_bar=True,
    )
    emb = np.asarray(emb, dtype=np.float32)
    return emb


def run_benchmark_for_model(
    model_name: str,
    model: SentenceTransformer,
    chunks: List[Chunk],
    queries: List[QueryCase],
    top_k: int = 5,
    batch_size: int = 64,
) -> Tuple[List[PerQueryResult], float, float]:
    # Returns: (per-query rows, avg_recall@k, avg_mrr)

    corpus_texts = [c.text for c in chunks]
    chunk_ids = [c.chunk_id for c in chunks]

    print(f"[1/4] Embedding corpus ({len(corpus_texts)} chunks)…")
    t0 = time.perf_counter()
    corpus_vecs = embed_texts(model, corpus_texts, batch_size=batch_size)
    t1 = time.perf_counter()

    print("[2/4] Building FAISS index (cosine)…")
    index = build_faiss_cosine_index(corpus_vecs)

    # Embed queries (small; do it in a batch).
    q_texts = [q.query_text for q in queries]
    print(f"[3/4] Embedding queries ({len(q_texts)})…")
    t2 = time.perf_counter()
    q_vecs = embed_texts(model, q_texts, batch_size=min(batch_size, len(q_texts)))
    t3 = time.perf_counter()
    q_vecs = l2_normalize(q_vecs)

    # Search
    print(f"[4/4] FAISS search (top-{top_k})…")
    t4 = time.perf_counter()
    scores, idxs = index.search(q_vecs.astype(np.float32), top_k)
    t5 = time.perf_counter()

    rows: List[PerQueryResult] = []

    recalls: List[int] = []
    rrs: List[float] = []

    for qi, q in enumerate(queries):
        retrieved = [chunk_ids[j] for j in idxs[qi].tolist() if j >= 0]
        r_at_5 = recall_at_k(retrieved, q.ground_truth_chunk_ids, k=top_k)
        rr = reciprocal_rank(retrieved, q.ground_truth_chunk_ids)

        # For the CSV schema, keep a single ground-truth chunk id.
        # If there are multiple (range endpoints), store the first as primary.
        gt_primary = q.ground_truth_chunk_ids[0]

        rows.append(
            PerQueryResult(
                model_name=model_name,
                query_id=q.query_id,
                recall_at_5=r_at_5,
                mrr=rr,
                retrieved_chunk_ids=retrieved,
                ground_truth_chunk_id=gt_primary,
            )
        )
        recalls.append(r_at_5)
        rrs.append(rr)

    avg_recall = float(np.mean(recalls))
    avg_mrr = float(np.mean(rrs))

    embed_time = (t1 - t0)
    query_embed_time = (t3 - t2)
    search_time = (t5 - t4)

    print(f"\n=== Model: {model_name} ===")
    print(f"Corpus chunks: {len(chunks)} | Queries: {len(queries)}")
    print(f"Corpus embedding time: {embed_time:.2f}s")
    print(f"Query embedding time:   {query_embed_time:.2f}s")
    print(f"FAISS search time:      {search_time:.4f}s")
    print(f"Recall@{top_k}: {avg_recall:.3f}")
    print(f"MRR:        {avg_mrr:.3f}")

    return rows, avg_recall, avg_mrr


def write_results_csv(output_csv: Path, results: List[PerQueryResult]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "model_name",
                "query_id",
                "recall_at_5",
                "mrr",
                "retrieved_chunk_ids",
                "ground_truth_chunk_id",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.model_name,
                    r.query_id,
                    r.recall_at_5,
                    f"{r.mrr:.6f}",
                    " ".join(r.retrieved_chunk_ids),
                    r.ground_truth_chunk_id,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding benchmark (FAISS + sentence-transformers)")
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("extraction_output/chunks"),
        help="Directory containing *_chunks.jsonl files (default: extraction_output/chunks)",
    )
    parser.add_argument(
        "--query-bank-md",
        type=Path,
        default=Path("research_query_bank_v1.md"),
        help="Markdown query bank with ground-truth chunk IDs (default: research_query_bank_v1.md)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("retrieval_benchmark_results.csv"),
        help="Output CSV path (default: retrieval_benchmark_results.csv)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-K to retrieve (default: 5)",
    )
    parser.add_argument(
        "--ground-truth-mapping",
        type=Path,
        default=Path("ground_truth_mapping.json"),
        help=(
            "Optional mapping from query_id -> mapped_chunk_id (default: ground_truth_mapping.json). "
            "Use the mapper script to generate this when query bank references chunks_v2 IDs."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Embedding batch size (default: 64)",
    )
    parser.add_argument(
        "--skip-bge-m3",
        action="store_true",
        help="Skip downloading/running BAAI/bge-m3 (useful on slow/blocked networks).",
    )
    parser.add_argument(
        "--fallback-multilingual-model",
        type=str,
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help=(
            "Fallback multilingual model to use if bge-m3 can't be loaded "
            "(default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)."
        ),
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Use only local cached files for Hugging Face models, do not connect to the internet.",
    )

    args = parser.parse_args()

    print("Loading corpus...")
    chunks = load_corpus(args.chunks_dir)

    print("Loading query bank...")
    queries = load_query_bank_md(args.query_bank_md)
    # Apply mapping if present (helps avoid 0.000 scores due to mismatched chunk_id formats).
    if args.ground_truth_mapping and args.ground_truth_mapping.exists():
        queries = apply_ground_truth_mapping(queries, args.ground_truth_mapping)
        print(f"Applied ground-truth mapping: {args.ground_truth_mapping}")
    print(f"Parsed {len(queries)} queries from {args.query_bank_md}")

    models: List[Tuple[str, str]] = [("all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2")]
    if not args.skip_bge_m3:
        models.append(("bge-m3", "BAAI/bge-m3"))

    all_results: List[PerQueryResult] = []

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")

    for short_name, hf_name in models:
        print(f"\nLoading model: {hf_name}")
        print("(If this is the first run, Hugging Face may download model weights; this can take a while.)")
        # device selection is handled by sentence-transformers; on Apple Silicon it may use MPS.
        model = None
        try:
            model = SentenceTransformer(hf_name, device=device, local_files_only=args.local_files_only)
        except Exception as e:
            # Most common failure here: slow/blocked HF downloads for bge-m3 or baseline model.
            print(f"Failed to load {hf_name}: {e}")
            if hf_name == "BAAI/bge-m3":
                fb = args.fallback_multilingual_model
                print(f"Falling back to smaller multilingual model: {fb}")
                try:
                    model = SentenceTransformer(fb, device=device, local_files_only=args.local_files_only)
                    short_name = f"fallback:{Path(fb).name}"
                except Exception as fb_e:
                    print(f"Failed to load fallback model {fb}: {fb_e}")
                    print("Skipping this model.")
                    continue
            else:
                print(f"Skipping {hf_name} due to load failure.")
                continue

        if not model:
            continue

        rows, _avg_recall, _avg_mrr = run_benchmark_for_model(
            model_name=short_name,
            model=model,
            chunks=chunks,
            queries=queries,
            top_k=args.top_k,
            batch_size=args.batch_size,
        )
        all_results.extend(rows)

    write_results_csv(args.output_csv, all_results)
    print(f"\nWrote CSV: {args.output_csv}")


if __name__ == "__main__":
    main()
