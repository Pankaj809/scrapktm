# Code-Switched RAG for Nepali Municipal PDFs: Overcoming Legacy Font Encodings

**Author:** ADHIKARI PANKAJ (Student ID: 2120256037, Masters Student, Nankai University)

## 📌 Project Overview
This project builds a localized Retrieval-Augmented Generation (RAG) evaluation pipeline designed to parse, chunk, and retrieve local governance laws and financial schedules from the Kathmandu Valley (Kathmandu, Lalitpur, and Bhaktapur municipalities). 

A major focus of this research is solving the **Legacy Font-Encoding Crisis** inherent in South Asian municipal PDFs, where documents utilize non-Unicode fonts (e.g., Preeti, Kantipur), causing catastrophic failures in standard NLP and RAG pipelines.

---

## 🚀 Step-by-Step Pipeline

### Step 1: Web Scraping & Data Curation
*   **Process:** Built a custom web scraper to download municipal PDFs (Financial Acts, Building Regulations, Local Governance Acts).
*   **Result:** A curated corpus of **52 PDFs** cleanly organized and mapped via `curated_corpus_manifest.jsonl`.
*   **Tools:** Python, `requests`, `BeautifulSoup`.

### Step 2: PDF Extraction & The "Font-Encoding" Crisis
*   **Process:** Extracted text from the PDFs and chunked them for semantic search.
*   **The Problem:** Many legacy PDFs extract as font-encoded gibberish (e.g., `sf7df8f}F dxfgu/kflnsf` instead of `Kathmandu Metropolitan City`) due to the lack of native Unicode compliance.
*   **Tools:** Custom PDF chunking scripts, JSONL formatting.

### Step 3: Baseline Evaluation (The Encoding Revelation)
*   **Process:** Evaluated the raw chunks with sparse TF-IDF against a **50-query, leakage-free, code-switched Query Bank** (`thesis/data/research_query_bank_v2.md`, Q001–Q050) whose ground-truth chunks are authored independently of any alias dictionary.
*   **The Result:** Raw retrieval collapses to **Recall@3 = 0.060, MRR = 0.023, Doc-Recall@3 = 0.140**.
*   **The Revelation:** This is *not* a model failure. Character-ratio analysis shows 26 of 50 documents (including all three query targets) extracted as near-pure Latin gibberish because of legacy **Preeti** font-encoding.

### Step 4: Deterministic Preeti → Unicode Repair
*   **Process:** Built `thesis/code/preeti_to_unicode.py`, a deterministic glyph-substitution converter (with short-*i* matra and reph reordering) that reconstructs Devanagari from the corrupted ASCII **before** indexing.
*   **The Result:** **45.8%** token-level validity vs. an independent clean vocabulary; applied to retrieval on the 50-query bank it lifts **Recall@3 to 0.520** and **document-level Recall@3 to 0.800** — a near-ninefold gain with **no hand-authored knowledge**.

### Step 5: Aliasing Baseline & Cross-Retriever Ablation
*   **Aliasing:** For contrast, code-switched keyword aliases were injected into a handful of high-value chunks. On the leakage-free 50-query bank this reaches only **Recall@3 = 0.260** — it helps *only* the chunks it was hand-authored for and is **beaten by deterministic repair** (0.520), confirming aliasing is a brittle, non-scaling patch relative to encoding repair.
*   **Dense retrieval (identical chunk IDs, CPU-only via `dense_eval_local.py`):** Repair is **necessary but not sufficient** for dense retrieval — it quadruples a multilingual encoder (`paraphrase-multilingual-MiniLM-L12-v2`, Recall@3 0.040 → 0.160, Doc-Recall@3 0.260 → 0.620) but barely moves an English-centric one (`all-MiniLM-L6-v2`, 0.060), and no repaired dense encoder overtakes sparse-plus-repair under the edge memory budget. The 2.2 GB `bge-m3` encoder exceeds that budget and is left to GPU future work (`colab_gpu_eval.py`).
*   **LLM Grounding:** Illustratively, direct LLMs hallucinate localized municipal rates whereas grounded retrieval returns citable clauses from the source PDFs (qualitative; a controlled generation study — named model, N≥50, three-level rubric, two annotators + Cohen's κ — is precommitted as future work).

---

## 📊 Key Results

All numbers below are generated on the **50-query leakage-free bank** by `thesis/code/paper_analysis.py` (sparse) and `thesis/code/dense_eval_local.py` (dense) over the real corpus — deterministic, CPU-only, no fabrication. Every row is scored on identical chunk IDs.

| System Configuration | Recall@3 | MRR | Doc-Recall@3 |
| :--- | :---: | :---: | :---: |
| Dense MiniLM-L6 (EN), raw corrupted | 0.000 | 0.000 | 0.380 |
| Dense MiniLM-L6 (EN), Preeti-repaired | 0.060 | 0.050 | 0.300 |
| Dense mMiniLM-L12 (multilingual), raw corrupted | 0.040 | 0.027 | 0.260 |
| Dense mMiniLM-L12 (multilingual), Preeti-repaired | 0.160 | 0.137 | 0.620 |
| Sparse TF-IDF, raw corrupted text (no aliases) | 0.060 | 0.023 | 0.140 |
| **Sparse TF-IDF, deterministic Preeti repair (no aliases)** | **0.520** | **0.380** | **0.800** |
| Sparse TF-IDF + metadata aliasing (pilot subset) | 0.260 | 0.237 | 0.480 |

> **Understanding the Metrics:**
> *   **Recall@K:** Whether the exact required paragraph is retrieved in the Top K results.
> *   **MRR:** How high up the list the correct answer is (Rank 1 = 1.0, Rank 2 = 0.5).
> *   **Doc-Recall@K:** Relaxed metric — a hit when any retrieved chunk belongs to the target document.
> *   **N = 50** grounded, code-switched, leakage-free queries — the aliasing row is a hand-authored baseline that only covers its pilot chunks, not an oracle.

---

## 🛠️ Tools & Technologies Used
*   **Data Processing:** Python, JSON Lines (`.jsonl`), Regex.
*   **Retrieval & Evaluation:** Scikit-Learn (TF-IDF), Sentence-Transformers (CPU-only dense encoders), custom Recall@K / MRR / Doc-Recall@K scoring.
*   **Font Repair:** Deterministic Preeti → Unicode glyph-substitution converter (`preeti_to_unicode.py`).
*   **Paper & Slides:** LaTeX / XeLaTeX (self-contained IEEE paper + deck), Markdown.

---

## 📁 Repository Structure

```text
├── thesis/
│   ├── code/                  # Pipeline + reproducible eval scripts
│   │   ├── preeti_to_unicode.py   # Deterministic font repair (glyph map)
│   │   ├── paper_analysis.py      # Sparse TF-IDF eval (50-query, RAM-safe)
│   │   ├── dense_eval_local.py    # Dense eval, CPU-only, identical chunk IDs
│   │   └── colab_gpu_eval.py      # GPU scaffold: bge-m3 + generation study
│   ├── data/                  # 50-query bank (research_query_bank_v2.md), manifest, ground truth
│   ├── ieee_paper/generated/  # Machine-generated tables/figures (no hand-transcribed numbers)
│   ├── paper.tex / paper.pdf  # Self-contained IEEE paper
│   └── presentation.*         # Slide deck
├── extraction_output/         # Extracted text + JSONL chunk databases (446 chunks)
├── curated_corpus/            # Source municipal/federal legal PDFs
├── README.md                  # This master documentation
└── requirements.txt           # Python dependencies
```

---

## 🏁 Conclusion
The broken baseline (Recall@3 = 0.060) was diagnosed as a **font-encoding** constraint, not an AI limitation. On the 50-query leakage-free bank, a **deterministic Preeti → Unicode repair** step recovers most of the retrievable signal (Recall@3 0.060 → 0.520, doc-level → 0.800) with no hand-authored knowledge, and **outperforms** retrieval-side metadata aliasing (0.260), which only helps its hand-picked chunks. A cross-retriever ablation on identical chunk IDs shows the same repair is **necessary but not sufficient** for dense retrieval — it quadruples a multilingual encoder yet leaves an English-centric one near-broken, and no repaired dense encoder overtakes sparse-plus-repair under the edge budget. Remaining conjunct-level lossiness motivates learned transliteration repair and GPU-scale multilingual baselines as future work.
