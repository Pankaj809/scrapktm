"""RAM-safe local dense-retrieval evaluation on identical chunk IDs.

Answers the reviewer question "does deterministic repair alone fix *dense*
retrieval?" by scoring two Sentence-Transformer encoders on the same 50-query
bank, chunk set, ground truth, repair gate, and metrics as the sparse analysis
(``paper_analysis.py``), so the dense and sparse rows are directly comparable.

Two encoders, both already cached locally, both small enough for CPU:
  * ``all-MiniLM-L6-v2``                       (22.7M params, English-centric)
  * ``paraphrase-multilingual-MiniLM-L12-v2``  (118M params, 50+ languages incl.
    Nepali/Devanagari) -- the one that *should* benefit from repair.

SAFETY: forced onto CPU with capped threads. The machine's earlier hard-restarts
came from BGE-M3 (2.2 GB) through Apple MPS unified memory, which panics the
kernel instead of OOM-killing. These two models on CPU peak well under 2 GB, so
they are RAM-safe. Do NOT add BGE-M3 or MPS here.

Each model runs in its own spawned subprocess so peak-RSS and index-time are
measured in isolation (not contaminated by the other model's high-water mark),
matching the resource table requested for the paper's memory-budget claim.

Run from the repository root:

    ./.venv/bin/python thesis/code/dense_eval_local.py

Emits:
  thesis/ieee_paper/generated/dense_table.tex     -- LaTeX retrieval rows
  thesis/ieee_paper/generated/dense_analysis.json -- retrieval + resource stats
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
import resource
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "4")

from preeti_to_unicode import convert as preeti_convert  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
QUERY_BANK = ROOT / "thesis" / "data" / "research_query_bank_v2.md"
CHUNKS_DIR = ROOT / "extraction_output" / "chunks"
GEN = ROOT / "thesis" / "ieee_paper" / "generated"

MODELS = [
    ("all-MiniLM-L6-v2", "MiniLM-L6 (EN)", 22_700_000),
    ("paraphrase-multilingual-MiniLM-L12-v2", "mMiniLM-L12 (ML)", 118_000_000),
]

_QROW = re.compile(r"^\|\s*(Q\d+)\s*\|")


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def load_queries():
    out = []
    for line in QUERY_BANK.read_text(encoding="utf-8").splitlines():
        if not _QROW.match(line):
            continue
        p = [x.strip() for x in line.strip("|").split("|")]
        if len(p) < 5:
            continue
        q = re.sub(r"[“”`]", "", p[1])
        out.append(
            {"qid": p[0], "query": q, "doc": p[3].split(",")[0].strip(),
             "chunk": p[4].split(" ")[0].strip("`")}
        )
    return out


def load_chunks():
    chunks = []
    for fp in sorted(CHUNKS_DIR.glob("*_chunks.jsonl")):
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def devanagari_ratio(text: str) -> float:
    dev = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    lat = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    tot = dev + lat
    return (dev / tot) if tot else 0.0


def build_texts(chunks, repair: bool):
    """Identical repair gate to paper_analysis.build_texts (Devanagari<0.10)."""
    texts = []
    for c in chunks:
        content = c["text"]
        if repair and devanagari_ratio(content) < 0.10:
            content = preeti_convert(content)
        texts.append(content)
    return texts


def metrics(queries, ranked_chunk_ids, ranked_doc_ids, k=3):
    """Exact-chunk Recall@k, MRR@k, relaxed document-level Recall@k."""
    hits = rr = doc_hits = 0.0
    for q, cids, dids in zip(queries, ranked_chunk_ids, ranked_doc_ids):
        topk = cids[:k]
        rank = next((i + 1 for i, cid in enumerate(topk) if cid == q["chunk"]), None)
        hits += int(rank is not None)
        rr += (1.0 / rank) if rank else 0.0
        doc_hits += int(q["doc"] in dids[:k])
    n = len(queries)
    return hits / n, rr / n, doc_hits / n


def _worker(model_id, label, params, queries, chunks, raw_texts, rep_texts, out_path):
    """Runs in its own spawned process: isolated peak-RSS + index-time measurement."""
    import torch
    torch.set_num_threads(4)
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim

    doc = SentenceTransformer(model_id, device="cpu")

    def encode(texts):
        return doc.encode(texts, batch_size=16, convert_to_tensor=True,
                           normalize_embeddings=True, show_progress_bar=False)

    # "Index time" = one-time offline cost of embedding the 446 raw chunks,
    # the job a reviewer would actually run before deployment.
    t0 = time.time()
    raw_emb = encode(raw_texts)
    index_time_s = time.time() - t0

    row = {}
    for cfg, texts, precomputed in (("raw", raw_texts, raw_emb), ("repaired", rep_texts, None)):
        chunk_emb = precomputed if precomputed is not None else encode(texts)
        qemb = encode([q["query"] for q in queries])
        sims = cos_sim(qemb, chunk_emb)
        ranked_cids, ranked_dids = [], []
        for i in range(len(queries)):
            order = torch.argsort(sims[i], descending=True)[:10].tolist()
            ranked_cids.append([chunks[j]["chunk_id"] for j in order])
            ranked_dids.append([chunks[j]["doc_id"] for j in order])
        r3, mrr3, doc3 = metrics(queries, ranked_cids, ranked_dids, k=3)
        row[cfg] = {"recall3": r3, "mrr3": mrr3, "doc_recall3": doc3}

    result = {
        "label": label, "params": params,
        "index_time_s": index_time_s, "peak_rss_mb": rss_mb(),
        **row,
    }
    Path(out_path).write_text(json.dumps(result), encoding="utf-8")


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    queries = load_queries()
    chunks = load_chunks()
    print(f"queries={len(queries)} chunks={len(chunks)} (CPU, threads=4, subprocess-isolated)")

    raw_texts = build_texts(chunks, repair=False)
    rep_texts = build_texts(chunks, repair=True)

    ctx = mp.get_context("spawn")
    results = {"n_queries": len(queries), "n_chunks": len(chunks), "models": {}}
    for model_id, label, params in MODELS:
        print(f"\n== {model_id} (isolated subprocess) ==")
        out_path = GEN / f"_tmp_{model_id.replace('/', '_')}.json"
        p = ctx.Process(target=_worker, args=(model_id, label, params, queries, chunks,
                                               raw_texts, rep_texts, str(out_path)))
        p.start()
        p.join()
        row = json.loads(out_path.read_text(encoding="utf-8"))
        out_path.unlink()
        results["models"][model_id] = row
        print(f"  peak_rss={row['peak_rss_mb']:.0f}MB index_time={row['index_time_s']:.1f}s")
        for cfg in ("raw", "repaired"):
            v = row[cfg]
            print(f"  {cfg:9s} R@3={v['recall3']:.3f} MRR@3={v['mrr3']:.3f} "
                  f"DocR@3={v['doc_recall3']:.3f}")

    (GEN / "dense_analysis.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    for model_id, label, _ in MODELS:
        m = results["models"][model_id]
        for cfg, disp in (("raw", "raw corrupted"), ("repaired", "Preeti-repaired")):
            v = m[cfg]
            lines.append(
                f"{label}, {disp} & {v['recall3']:.3f} & {v['mrr3']:.3f} "
                f"& {v['doc_recall3']:.3f} \\\\"
            )
    (GEN / "dense_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nwrote", (GEN / "dense_analysis.json").relative_to(ROOT))
    print("wrote", (GEN / "dense_table.tex").relative_to(ROOT))


if __name__ == "__main__":
    main()
