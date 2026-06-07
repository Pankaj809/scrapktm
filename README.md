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

### Step 3: Baseline Evaluation (The 0.000 Revelation)
*   **Process:** Evaluated the raw chunks using state-of-the-art dense embeddings (`BAAI/bge-m3` and `all-MiniLM-L6-v2`) against a custom **Code-Switched Query Bank** (`research_query_bank_v1.md`).
*   **The Result:** The system achieved a **0.000 Recall@5 and MRR**. 
*   **The Revelation:** This was *not* a model failure, but a fundamental data pipeline failure. The AI could not perform semantic matching on corrupted transliteration text.

### Step 4: The Local LangChain Hybrid RAG Solution
*   **Process:** Instead of waiting for perfect native Nepali OCR models, we built a **Local LangChain Hybrid Retriever**.
*   **Technique (Metadata Aliasing):** We augmented the corrupted text chunks by injecting normalized, code-switched semantic aliases (Romanized English + Unicode Nepali) into the LangChain `Document` metadata.
*   **Tools:** `langchain-core`, Scikit-Learn (TF-IDF/BM25 sparse character-level n-gram vectors).

### Step 5: Final Evaluation & LLM Comparison
*   **Process:** Re-ran the retrieval benchmarks using the alias-augmented Hybrid RAG system.
*   **The Result:** Performance jumped from **0% to 91.7% Recall@3**.
*   **LLM Grounding:** Demonstrated that direct LLMs (ChatGPT/Claude) hallucinate localized municipal tax rates, whereas our RAG pipeline retrieves the mathematically exact clauses directly from the PDFs.

---

## 📊 Key Results

| System Configuration | Recall@3 | Mean Reciprocal Rank (MRR) |
| :--- | :---: | :---: |
| **Dense Baseline** (BGE-M3 on raw text) | 0.000 | 0.000 |
| **Raw Sparse** (TF-IDF on raw text) | 0.180 | 0.150 |
| **Local RAG** (LangChain + Metadata Aliasing) | **0.917** | **0.917** |

> **Understanding the Metrics:**
> *   **Recall@K:** Measures whether the exact required paragraph is retrieved in the Top K results. Crucial for RAG contexts.
> *   **MRR (Mean Reciprocal Rank):** Measures how high up the list the correct answer is (Rank 1 = 1.0, Rank 2 = 0.5).

---

## 🛠️ Tools & Technologies Used
*   **Data Processing:** Python, JSON Lines (`.jsonl`), Regex.
*   **Information Retrieval (IR):** LangChain Core, Scikit-Learn (TF-IDF), FAISS, Hugging Face `bge-m3`.
*   **Evaluation:** Custom benchmarking scripts calculating Recall@K and MRR metrics.
*   **Presentation & Documentation:** LaTeX (Beamer) for high-quality academic slides, Markdown for tracking.

---

## 📁 Repository Structure
Following academic standards, the project is structured as follows:

```text
├── thesis/
│   ├── code/                  # All Python scripts (scraping, chunking, RAG evaluation)
│   ├── data/                  # CSV results, JSONL chunk databases, Query banks
│   ├── presentation/          # LaTeX Beamer slides (.tex and .pdf)
│   ├── chapters/              # LaTeX source files for thesis chapters (01-08)
│   ├── reports/               # Markdown pipeline summaries
│   └── logs/                  # System run logs
├── README.md                  # This master documentation
└── requirements.txt           # Python dependencies
```

---

## 🏁 Conclusion
The initial `0.000` baseline metric was successfully diagnosed as an extraction pipeline constraint rather than an AI limitation. By leveraging **LangChain** and **Metadata Aliasing**, this project successfully transformed previously inaccessible, legacy font-encoded municipal PDFs into a high-performing, queryable RAG corpus capable of supporting code-switched (Nepali + English) citizen queries.
