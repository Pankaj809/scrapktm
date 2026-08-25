"""Reproducible analysis backing every quantitative claim in the IEEE paper.

Run from the repository root:

    ./.venv/bin/python thesis/code/paper_analysis.py

RAM-safe: sparse TF-IDF (scikit-learn) only. No dense models, no OCR.

Emits machine-generated LaTeX/pgfplots fragments into
thesis/ieee_paper/generated/ so the paper never hand-transcribes a number:

  corpus_stats.tex        - \newcommand macros with corpus counts
  corruption_table.tex    - per-document Devanagari ratio (corruption evidence)
  chunksize_table.tex     - chunk-size distribution (extraction-yield finding)
  retrieval_table.tex     - main retrieval accuracy table (real numbers)
  recall_curve.dat        - Recall@k for k=1..10, both configs (pgfplots)
  aliasweight.dat         - MRR@3 vs alias multiplier (pgfplots)
  analysis.json           - all raw numbers for inspection
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from preeti_to_unicode import convert as preeti_convert

ROOT = Path(__file__).resolve().parents[2]
QUERY_BANK = ROOT / "thesis" / "data" / "research_query_bank_v1.md"
CHUNKS_DIR = ROOT / "extraction_output" / "chunks"
SUMMARY = ROOT / "extraction_output" / "extraction_summary.jsonl"
GEN = ROOT / "thesis" / "ieee_paper" / "generated"

# Alias dictionary — identical to local_langchain_rag.py. Keys are the exact
# ground-truth chunk_ids, which is precisely why the aliased run is an oracle.
ALIASES = {
    "LMC_MUN_004_section_2": "Lalitpur business registration application required documents list citizenship ward recommendation photos दर्ता प्रमाणपत्र format appendix multiple locations same owner renewal deadline fiscal year specific months",
    "BKT_MUN_001_section_3": "Bhaktapur नक्सा पास application documents required exact list fee गुणा pass registration restriction घर भवन बेच्न भाडामा",
    "KTM_FIN_002_section_2": "Kathmandu property tax लगाउने आधार annex schedule rate",
    "KTM_FIN_002_section_9": "Property tax slab १–२ करोड rate exact %",
    "KTM_FIN_002_section_63": "Kathmandu public parking two-wheeler four-wheeler fee first half-hour per rate",
    "KTM_FIN_002_section_61": "Signboard advertisement fee sq ft flex digital board rate",
}

_QUERY_ROW_RE = re.compile(r"^\|\s*(Q\d+)\s*\|")


def load_queries():
    md = QUERY_BANK.read_text(encoding="utf-8")
    out = []
    for line in md.splitlines():
        if not _QUERY_ROW_RE.match(line):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 5:
            continue
        qid = parts[0]
        q = re.sub(r"[“”`]", "", parts[1])
        target_doc = parts[3].split(",")[0].strip()
        target_chunk = parts[4].split(" ")[0].strip("`")
        out.append((qid, q, target_doc, target_chunk))
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


def build_texts(chunks, alias_weight: int, repair: bool = False):
    """Return corpus texts.

    repair=True applies deterministic Preeti->Unicode repair to any chunk whose
    Devanagari ratio is below 0.10 (i.e. font-corrupted), leaving already-Unicode
    chunks untouched. alias_weight injects each alias that many times (0 = off).
    """
    texts = []
    for c in chunks:
        content = c["text"]
        if repair and devanagari_ratio(content) < 0.10:
            content = preeti_convert(content)
        if alias_weight and c["chunk_id"] in ALIASES:
            content += "\n\n[METADATA ALIASES]: " + (ALIASES[c["chunk_id"]] + " ") * alias_weight
        texts.append(content)
    return texts


def rank_lists(queries, chunks, texts, k_max=10):
    """Return, per query, the ranked chunk_ids and doc_ids up to k_max."""
    vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, max_features=50000)
    X = vec.fit_transform(texts)
    Q = vec.transform([q for _, q, _, _ in queries])
    S = cosine_similarity(Q, X)
    per = []
    for i, _ in enumerate(queries):
        order = S[i].argsort()[::-1][:k_max]
        per.append(
            {
                "chunk_ids": [chunks[j]["chunk_id"] for j in order],
                "doc_ids": [chunks[j]["doc_id"] for j in order],
            }
        )
    return per


def metrics(queries, per, k):
    """Exact-chunk Recall@k, MRR@k, and relaxed document-level Recall@k."""
    hits = 0
    rr = 0.0
    doc_hits = 0
    for (qid, q, t_doc, t_chunk), r in zip(queries, per):
        topk = r["chunk_ids"][:k]
        rank = next((idx + 1 for idx, cid in enumerate(topk) if cid == t_chunk), None)
        hits += int(rank is not None)
        rr += (1.0 / rank) if rank else 0.0
        doc_topk = r["doc_ids"][:k]
        doc_hits += int(t_doc in doc_topk)
    n = len(queries)
    return hits / n, rr / n, doc_hits / n


def w(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    queries = load_queries()
    chunks = load_chunks()
    assert len(queries) == 11, f"expected 11 queries, got {len(queries)}"

    result = {"n_queries": len(queries), "n_chunks": len(chunks)}

    # ---- Corpus composition -------------------------------------------------
    docs = sorted({c["chunk_id"].rsplit("_section_", 1)[0].rsplit("_chunk_", 1)[0] for c in chunks})
    n_docs = len(set(fp.name.replace("_chunks.jsonl", "") for fp in CHUNKS_DIR.glob("*_chunks.jsonl")))
    per_doc_text = {}
    for c in chunks:
        d = c["chunk_id"].rsplit("_section_", 1)[0].rsplit("_chunk_", 1)[0]
        per_doc_text.setdefault(d, []).append(c["text"])
    corruption = {d: devanagari_ratio("".join(t)) for d, t in per_doc_text.items()}
    n_corrupt = sum(1 for r in corruption.values() if r < 0.10)
    n_clean = sum(1 for r in corruption.values() if r >= 0.90)
    chunk_lens = [len(c["text"]) for c in chunks]

    summary = [json.loads(l) for l in SUMMARY.read_text().splitlines() if l.strip()]
    summ_pages = sum(s["metrics"]["page_count"] for s in summary)

    result["corpus"] = {
        "n_docs": n_docs,
        "n_chunks": len(chunks),
        "n_corrupt_docs": n_corrupt,
        "n_clean_docs": n_clean,
        "summary_docs": len(summary),
        "summary_pages": summ_pages,
        "chunk_len_median": statistics.median(chunk_lens),
        "chunk_len_max": max(chunk_lens),
        "chunk_len_min": min(chunk_lens),
        "chunk_len_mean": round(statistics.mean(chunk_lens)),
    }

    # ---- Preeti-repair validity (token-level, vs. clean-doc vocabulary) -----
    clean_vocab = set()
    for d, ts in per_doc_text.items():
        if corruption[d] >= 0.90:
            for tok in re.findall(r"[ऀ-ॿ]+", "".join(ts)):
                if len(tok) >= 3:
                    clean_vocab.add(tok)
    rep_tot = rep_hit = 0
    for d, ts in per_doc_text.items():
        if corruption[d] < 0.10:
            conv = preeti_convert("".join(ts))
            for tok in re.findall(r"[ऀ-ॿ]+", conv):
                if len(tok) >= 3:
                    rep_tot += 1
                    rep_hit += int(tok in clean_vocab)
    repair_validity = (rep_hit / rep_tot) if rep_tot else 0.0
    result["repair_token_validity"] = repair_validity

    # ---- Retrieval configs (real numbers) ----------------------------------
    per_raw = rank_lists(queries, chunks, build_texts(chunks, 0))
    per_rep = rank_lists(queries, chunks, build_texts(chunks, 0, repair=True))
    per_ali = rank_lists(queries, chunks, build_texts(chunks, 20))

    raw_r3, raw_mrr, raw_doc3 = metrics(queries, per_raw, 3)
    rep_r3, rep_mrr, rep_doc3 = metrics(queries, per_rep, 3)
    ali_r3, ali_mrr, ali_doc3 = metrics(queries, per_ali, 3)
    result["retrieval"] = {
        "raw": {"recall3": raw_r3, "mrr3": raw_mrr, "doc_recall3": raw_doc3},
        "repaired": {"recall3": rep_r3, "mrr3": rep_mrr, "doc_recall3": rep_doc3},
        "aliased": {"recall3": ali_r3, "mrr3": ali_mrr, "doc_recall3": ali_doc3},
    }

    # ---- Recall@k curve k=1..10 --------------------------------------------
    curve = []
    for k in range(1, 11):
        curve.append((k, metrics(queries, per_raw, k)[0],
                      metrics(queries, per_rep, k)[0], metrics(queries, per_ali, k)[0]))
    result["recall_curve"] = curve

    # ---- Alias-weight sensitivity ------------------------------------------
    sens = []
    for wgt in (0, 1, 5, 10, 20, 50):
        per = rank_lists(queries, chunks, build_texts(chunks, wgt))
        r3, mrr3, _ = metrics(queries, per, 3)
        sens.append((wgt, r3, mrr3))
    result["alias_sensitivity"] = sens

    (GEN / "analysis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", (GEN / "analysis.json").relative_to(ROOT))

    # ---- Emit LaTeX fragments ----------------------------------------------
    w(GEN / "corpus_stats.tex", "".join(
        f"\\newcommand{{\\{name}}}{{{val}}}\n" for name, val in [
            ("corpusDocs", n_docs), ("corpusChunks", len(chunks)),
            ("corpusCorruptDocs", n_corrupt), ("corpusCleanDocs", n_clean),
            ("corpusSummaryDocs", len(summary)), ("corpusSummaryPages", summ_pages),
            ("chunkLenMedian", int(statistics.median(chunk_lens))),
            ("chunkLenMax", max(chunk_lens)), ("chunkLenMin", min(chunk_lens)),
            ("rawRecall", f"{raw_r3:.3f}"), ("rawMRR", f"{raw_mrr:.3f}"),
            ("rawDocRecall", f"{raw_doc3:.3f}"),
            ("repRecall", f"{rep_r3:.3f}"), ("repMRR", f"{rep_mrr:.3f}"),
            ("repDocRecall", f"{rep_doc3:.3f}"),
            ("aliRecall", f"{ali_r3:.3f}"), ("aliMRR", f"{ali_mrr:.3f}"),
            ("aliDocRecall", f"{ali_doc3:.3f}"),
            ("repairValidity", f"{100 * repair_validity:.1f}"),
        ]
    ))

    # Retrieval table (complete tabular; \input outside any alignment)
    rows = [
        ("Sparse TF-IDF, raw corrupted text (no aliases)", raw_r3, raw_mrr, raw_doc3, False),
        ("Sparse TF-IDF, deterministic Preeti repair (no aliases)", rep_r3, rep_mrr, rep_doc3, "mid"),
        ("Sparse TF-IDF + metadata aliasing (oracle)", ali_r3, ali_mrr, ali_doc3, True),
    ]
    body = ""
    for name, r3, mrr, doc3, bold in rows:
        if bold == "mid":
            body += f"\\textbf{{{name}}} & \\textbf{{{r3:.3f}}} & \\textbf{{{mrr:.3f}}} & \\textbf{{{doc3:.3f}}} \\\\\n"
        elif bold:
            body += f"{name} & \\textit{{{r3:.3f}}} & \\textit{{{mrr:.3f}}} & \\textit{{{doc3:.3f}}} \\\\\n"
        else:
            body += f"{name} & {r3:.3f} & {mrr:.3f} & {doc3:.3f} \\\\\n"
    w(GEN / "retrieval_table.tex",
      "\\begin{tabular}{p{4.6cm}ccc}\n\\toprule\n"
      "\\textbf{Configuration} & \\textbf{R@3} & \\textbf{MRR} & \\textbf{DocR@3} \\\\\n\\midrule\n"
      + body + "\\bottomrule\n\\end{tabular}\n")

    # Corruption evidence table (target docs + a couple clean for contrast)
    highlight = ["LMC_MUN_004", "BKT_MUN_001", "KTM_FIN_002", "KTM_NAT_001", "KTM_NAT_004"]
    ctab = ""
    for d in highlight:
        r = corruption.get(d, 0.0)
        label = "corrupted" if r < 0.10 else "clean"
        ctab += f"\\texttt{{{d.replace('_', chr(92) + '_')}}} & {100 * r:.1f}\\% & {label} \\\\\n"
    w(GEN / "corruption_table.tex",
      "\\begin{tabular}{lcc}\n\\toprule\n"
      "\\textbf{Document} & \\textbf{Devanagari \\%} & \\textbf{Status} \\\\\n\\midrule\n"
      + ctab + "\\bottomrule\n\\end{tabular}\n")

    # chunk-size table
    w(GEN / "chunksize_table.tex",
      "\\begin{tabular}{lr}\n\\toprule\n"
      "\\textbf{Statistic} & \\textbf{Characters} \\\\\n\\midrule\n"
      f"Minimum & {min(chunk_lens)} \\\\\n"
      f"Median & {int(statistics.median(chunk_lens))} \\\\\n"
      f"Mean & {round(statistics.mean(chunk_lens))} \\\\\n"
      f"Maximum & {max(chunk_lens)} \\\\\n"
      "\\bottomrule\n\\end{tabular}\n")

    # pgfplots data
    w(GEN / "recall_curve.dat",
      "k raw repaired aliased\n" + "".join(f"{k} {r:.4f} {p:.4f} {a:.4f}\n" for k, r, p, a in curve))
    w(GEN / "aliasweight.dat",
      "weight recall mrr\n" + "".join(f"{wt} {r:.4f} {m:.4f}\n" for wt, r, m in sens))

    # ---- Console summary ----------------------------------------------------
    print("\n=== SUMMARY ===")
    print(f"docs={n_docs} chunks={len(chunks)} corrupt(<10% dev)={n_corrupt} clean(>=90%)={n_clean}")
    print(f"chunk chars: min={min(chunk_lens)} median={int(statistics.median(chunk_lens))} max={max(chunk_lens)}")
    print(f"repair token validity vs clean vocab: {100*repair_validity:.1f}%")
    print(f"RAW     : recall@3={raw_r3:.3f} mrr@3={raw_mrr:.3f} docRecall@3={raw_doc3:.3f}")
    print(f"REPAIRED: recall@3={rep_r3:.3f} mrr@3={rep_mrr:.3f} docRecall@3={rep_doc3:.3f}")
    print(f"ALIASED : recall@3={ali_r3:.3f} mrr@3={ali_mrr:.3f} docRecall@3={ali_doc3:.3f}")
    print("alias sensitivity (weight, recall@3, mrr@3):")
    for wt, r3, mrr3 in sens:
        print(f"  x{wt:<3} recall@3={r3:.3f} mrr@3={mrr3:.3f}")


if __name__ == "__main__":
    main()
