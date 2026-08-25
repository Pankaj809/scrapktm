"""Colab GPU evaluation: dense retrieval + RAG generation eval (RAGAS + GPT-4 judge).

This script is meant to run TOP-TO-BOTTOM in a Google Colab GPU runtime. It is the
piece that CANNOT run on the offline Mac (BGE-M3 / LLM calls). It produces:

  1. Dense retrieval table  -> all-MiniLM-L6-v2 and BAAI/bge-m3 on the 50-query
     bank, on RAW and REPAIRED corpus text (Recall@3/5, MRR, Doc-Recall@3).
  2. Generation eval table   -> for 30-50 questions: retrieve -> generate (GPT-4o)
     -> score with RAGAS (Faithfulness, Answer Relevance, Context Recall) and a
     GPT-4 LLM-as-judge correctness score.

Both tables print as LaTeX-ready rows so they can be pasted straight into paper.tex.

------------------------------------------------------------------------------
SETUP (run these as the first Colab cell):

    !pip -q install sentence-transformers faiss-cpu ragas datasets openai langchain-openai
    !git clone https://github.com/<YOUR_USER>/scrapktm.git    # or upload the repo
    %cd scrapktm
    import os; os.environ["OPENAI_API_KEY"] = "sk-..."        # your key (GPT-4 judge)

Then run this file:  !python thesis/code/colab_gpu_eval.py --n-gen 40
------------------------------------------------------------------------------
"""

from __future__ import annotations
import argparse, json, re, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "thesis" / "code"))
from preeti_to_unicode import convert, devanagari_ratio   # deterministic repair

QUERY_BANK = ROOT / "thesis" / "data" / "research_query_bank_v2.md"
CHUNKS_DIR = ROOT / "extraction_output" / "chunks"
_QROW = re.compile(r"^\|\s*(Q\d+)\s*\|")


def load_queries():
    out = []
    for line in QUERY_BANK.read_text(encoding="utf-8").splitlines():
        if not _QROW.match(line):
            continue
        p = [x.strip() for x in line.strip("|").split("|")]
        if len(p) < 5:
            continue
        q = re.sub(r'["""`]', "", p[1])
        out.append({"qid": p[0], "query": q,
                    "doc": p[3].split(",")[0].strip(),
                    "chunk": p[4].split(" ")[0].strip("`")})
    return out


def load_chunks(repair: bool):
    chunks = []
    for fp in sorted(CHUNKS_DIR.glob("*_chunks.jsonl")):
        for l in fp.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            c = json.loads(l)
            if repair and devanagari_ratio(c["text"]) < 0.10:
                c = {**c, "text": convert(c["text"])}
            chunks.append(c)
    return chunks


# ============================================================================
# PART A — DENSE RETRIEVAL
# ============================================================================
def dense_eval(model_name, repair, queries, k_list=(3, 5)):
    import faiss
    from sentence_transformers import SentenceTransformer
    chunks = load_chunks(repair)
    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    dids = [c["doc_id"] for c in chunks]

    model = SentenceTransformer(model_name, device="cuda")
    emb = model.encode(texts, batch_size=64, convert_to_numpy=True,
                       normalize_embeddings=True, show_progress_bar=True).astype("float32")
    q_emb = model.encode([q["query"] for q in queries], convert_to_numpy=True,
                         normalize_embeddings=True).astype("float32")
    index = faiss.IndexFlatIP(emb.shape[1]); index.add(emb)
    _, I = index.search(q_emb, max(k_list))

    res = {}
    for k in k_list:
        hit = rr = doc = 0
        for qi, q in enumerate(queries):
            top = [ids[j] for j in I[qi][:k]]
            topd = [dids[j] for j in I[qi][:k]]
            rank = next((r + 1 for r, c in enumerate(top) if c == q["chunk"]), None)
            hit += int(rank is not None); rr += (1 / rank) if rank else 0
            doc += int(q["doc"] in topd)
        n = len(queries)
        res[k] = {"recall": hit / n, "mrr": rr / n, "doc_recall": doc / n}
    return res


def run_dense(queries):
    models = ["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-m3"]
    print("\n% ==== DENSE RETRIEVAL TABLE (paste into paper.tex) ====")
    for m in models:
        short = m.split("/")[-1]
        for repair in (False, True):
            r = dense_eval(m, repair, queries)
            tag = "repaired" if repair else "raw"
            print(f"{short} ({tag}) & {r[3]['recall']:.3f} & {r[5]['recall']:.3f} "
                  f"& {r[3]['mrr']:.3f} & {r[3]['doc_recall']:.3f} \\\\")


# ============================================================================
# PART B — RAG GENERATION EVAL (RAGAS + GPT-4 judge)
# ============================================================================
def run_generation(queries, n_gen, gen_model="gpt-4o", judge_model="gpt-4o"):
    import faiss
    from sentence_transformers import SentenceTransformer
    from openai import OpenAI
    client = OpenAI()

    chunks = load_chunks(repair=True)          # generation runs on repaired corpus
    by_id = {c["chunk_id"]: c["text"] for c in chunks}
    texts = [c["text"] for c in chunks]
    retr = SentenceTransformer("BAAI/bge-m3", device="cuda")
    emb = retr.encode(texts, batch_size=64, convert_to_numpy=True,
                      normalize_embeddings=True, show_progress_bar=True).astype("float32")
    index = faiss.IndexFlatIP(emb.shape[1]); index.add(emb)

    sample = queries[:n_gen]
    rows = []   # {question, answer, contexts, ground_truth}
    for q in sample:
        qe = retr.encode([q["query"]], convert_to_numpy=True, normalize_embeddings=True).astype("float32")
        _, I = index.search(qe, 3)
        ctx = [texts[j] for j in I[0]]
        prompt = ("You are a Nepali municipal-law assistant. Answer the question ONLY "
                  "from the provided context. If absent, say you cannot find it.\n\n"
                  f"Context:\n{chr(10).join(ctx)}\n\nQuestion: {q['query']}\nAnswer:")
        ans = client.chat.completions.create(
            model=gen_model, messages=[{"role": "user", "content": prompt}],
            temperature=0).choices[0].message.content.strip()
        rows.append({"question": q["query"], "answer": ans, "contexts": ctx,
                     "ground_truth": by_id.get(q["chunk"], "")})

    # ---- RAGAS ----
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_recall
    from datasets import Dataset
    ds = Dataset.from_list(rows)
    ragas_res = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_recall])
    print("\n% ==== RAGAS ====")
    print(ragas_res)

    # ---- GPT-4 LLM-as-judge (3-level correctness) ----
    scores = []
    for r in rows:
        j = client.chat.completions.create(
            model=judge_model, temperature=0,
            messages=[{"role": "user", "content":
                "Rate the ANSWER against the REFERENCE for a Nepali municipal-law question. "
                "Reply with ONLY one integer: 2=correct-with-support, 1=partial, 0=wrong/refused.\n\n"
                f"Question: {r['question']}\nReference: {r['ground_truth'][:800]}\nAnswer: {r['answer']}"}]
        ).choices[0].message.content.strip()
        scores.append(int(re.search(r"[012]", j).group()))
    judge_acc = sum(s == 2 for s in scores) / len(scores)
    partial = sum(s == 1 for s in scores) / len(scores)

    print("\n% ==== GENERATION EVAL TABLE (paste into paper.tex) ====")
    print("% Metric & Score \\\\")
    print(f"Faithfulness (RAGAS) & {ragas_res['faithfulness']:.3f} \\\\")
    print(f"Answer Relevance (RAGAS) & {ragas_res['answer_relevancy']:.3f} \\\\")
    print(f"Context Recall (RAGAS) & {ragas_res['context_recall']:.3f} \\\\")
    print(f"GPT-4 judge, correct-with-support & {judge_acc:.3f} \\\\")
    print(f"GPT-4 judge, partial & {partial:.3f} \\\\")
    print(f"\\% N = {len(rows)} questions, generator={gen_model}, judge={judge_model}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-gen", type=int, default=40, help="questions for generation eval (30-50)")
    ap.add_argument("--skip-dense", action="store_true")
    ap.add_argument("--skip-gen", action="store_true")
    args = ap.parse_args()
    qs = load_queries()
    print(f"Loaded {len(qs)} queries.")
    if not args.skip_dense:
        run_dense(qs)
    if not args.skip_gen:
        assert os.environ.get("OPENAI_API_KEY"), "set OPENAI_API_KEY for generation eval"
        run_generation(qs, args.n_gen)
