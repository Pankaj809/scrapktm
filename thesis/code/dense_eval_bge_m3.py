"""BGE-M3 CPU-only dense-retrieval row, added to dense_eval_local.py's table.

Same queries/chunks/repair-gate/metrics as dense_eval_local.py, but isolated
into its own process so a crash here can't take down the other two encoders'
results. Forced CPU, max_seq_length capped at 512 (BGE-M3 defaults to 8192,
which is almost certainly why the earlier attempt OOM'd), small batch size,
and per-batch RSS logging so we can see where memory actually goes.

Run from the repository root:

    ./.venv/bin/python thesis/code/dense_eval_bge_m3.py
"""

from __future__ import annotations

import json
import os
import re
import resource
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import torch  # noqa: E402

torch.set_num_threads(4)

from sentence_transformers import SentenceTransformer  # noqa: E402
from sentence_transformers.util import cos_sim  # noqa: E402

from preeti_to_unicode import convert as preeti_convert  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
QUERY_BANK = ROOT / "thesis" / "data" / "research_query_bank_v2.md"
CHUNKS_DIR = ROOT / "extraction_output" / "chunks"
GEN = ROOT / "thesis" / "ieee_paper" / "generated"

MODEL_ID = "BAAI/bge-m3"
LABEL = "BGE-M3 (ML)"
BATCH_SIZE = 4
MAX_SEQ_LEN = 512

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
    texts = []
    for c in chunks:
        content = c["text"]
        if repair and devanagari_ratio(content) < 0.10:
            content = preeti_convert(content)
        texts.append(content)
    return texts


def metrics(queries, ranked_chunk_ids, ranked_doc_ids, k=3):
    hits = rr = doc_hits = 0.0
    for q, cids, dids in zip(queries, ranked_chunk_ids, ranked_doc_ids):
        topk = cids[:k]
        rank = next((i + 1 for i, cid in enumerate(topk) if cid == q["chunk"]), None)
        hits += int(rank is not None)
        rr += (1.0 / rank) if rank else 0.0
        doc_hits += int(q["doc"] in dids[:k])
    n = len(queries)
    return hits / n, rr / n, doc_hits / n


def encode_batched(model, texts, label):
    embs = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        e = model.encode(batch, batch_size=BATCH_SIZE, convert_to_tensor=True,
                          normalize_embeddings=True, show_progress_bar=False)
        embs.append(e)
        if (i // BATCH_SIZE) % 20 == 0:
            print(f"    {label} {i + len(batch)}/{len(texts)}  peak_rss={rss_mb():.0f}MB")
    return torch.cat(embs, dim=0)


def evaluate(model, queries, chunks, texts):
    # "Index time" = one-time offline cost of embedding the 446 raw chunks.
    t0 = time.time()
    emb = encode_batched(model, texts, "chunks")
    chunk_encode_time = time.time() - t0
    qemb = encode_batched(model, [q["query"] for q in queries], "queries")
    sims = cos_sim(qemb, emb)
    ranked_cids, ranked_dids = [], []
    for i in range(len(queries)):
        order = torch.argsort(sims[i], descending=True)[:10].tolist()
        ranked_cids.append([chunks[j]["chunk_id"] for j in order])
        ranked_dids.append([chunks[j]["doc_id"] for j in order])
    del emb, qemb, sims
    return ranked_cids, ranked_dids, chunk_encode_time


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    queries = load_queries()
    chunks = load_chunks()
    print(f"queries={len(queries)} chunks={len(chunks)} (CPU, threads=4, "
          f"batch={BATCH_SIZE}, max_seq_len={MAX_SEQ_LEN})")

    print(f"loading {MODEL_ID} ... peak_rss={rss_mb():.0f}MB")
    model = SentenceTransformer(MODEL_ID, device="cpu")
    model.max_seq_length = MAX_SEQ_LEN
    print(f"loaded. peak_rss={rss_mb():.0f}MB")

    raw_texts = build_texts(chunks, repair=False)
    rep_texts = build_texts(chunks, repair=True)

    row = {}
    index_time_s = None
    for cfg, texts in (("raw", raw_texts), ("repaired", rep_texts)):
        print(f"\n== {cfg} ==")
        cids, dids, chunk_time = evaluate(model, queries, chunks, texts)
        if cfg == "raw":
            index_time_s = chunk_time
        r3, mrr3, doc3 = metrics(queries, cids, dids, k=3)
        row[cfg] = {"recall3": r3, "mrr3": mrr3, "doc_recall3": doc3}
        print(f"  {cfg:9s} R@3={r3:.3f} MRR@3={mrr3:.3f} DocR@3={doc3:.3f} "
              f"peak_rss={rss_mb():.0f}MB")

    results = {"n_queries": len(queries), "n_chunks": len(chunks),
               "model": MODEL_ID, "label": LABEL, "params": 568_000_000,
               "index_time_s": index_time_s, "peak_rss_mb": rss_mb(), **row}
    (GEN / "dense_bge_m3.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    for cfg, disp in (("raw", "raw corrupted"), ("repaired", "Preeti-repaired")):
        v = row[cfg]
        lines.append(
            f"{LABEL}, {disp} & {v['recall3']:.3f} & {v['mrr3']:.3f} "
            f"& {v['doc_recall3']:.3f} \\\\"
        )
    (GEN / "dense_bge_m3_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nfinal peak_rss:", f"{rss_mb():.0f}MB")
    print("wrote", (GEN / "dense_bge_m3.json").relative_to(ROOT))
    print("wrote", (GEN / "dense_bge_m3_table.tex").relative_to(ROOT))


if __name__ == "__main__":
    main()
