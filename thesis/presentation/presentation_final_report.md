# Final Presentation Report

## Title

**Semantic Search for Nepali Municipal Legal Documents**

## Purpose

This project prepares Nepali municipal legal PDFs for semantic retrieval. It focuses on a practical pipeline: scraping legal PDFs, curating a reliable corpus, extracting text, chunking the text, and evaluating retrieval with query-level ground truth.

## Background and Motivation

Kathmandu Valley municipalities publish important laws, bylaws, procedures, and financial acts as PDFs across different websites. These documents are difficult to search because they are written in Nepali, often use Devanagari text, and sometimes appear as scanned PDFs. Citizens, students, and researchers need a way to retrieve the correct legal section for procedural questions.

## Aim and Objectives

The aim is to build and evaluate a retrieval-ready corpus for Nepali municipal legal documents.

Objectives:

1. Scrape and curate a focused set of legal PDFs.
2. Separate text-based PDFs from scanned PDFs.
3. Extract text using PyMuPDF and OCR where needed.
4. Split documents into useful semantic chunks.
5. Evaluate retrieval using FAISS, embedding models, Recall@5, and MRR.
6. Identify limitations that affect retrieval quality.

## Methods

The project uses a hybrid pipeline:

1. Web scraping collects legal PDFs from Kathmandu, Lalitpur, Bhaktapur, and federal sources.
2. Corpus curation selects 50 relevant legal documents.
3. The extraction router sends text-based PDFs to PyMuPDF and scanned PDFs to OCR.
4. Chunking converts extracted text into JSONL chunk files.
5. The benchmark embeds chunks and queries, builds a FAISS index, and measures whether the correct chunk appears in the top results.

## Literature Review Summary

Legal retrieval requires accurate document-level and section-level search because legal answers depend on exact wording and citation. Retrieval-augmented generation systems depend heavily on preprocessing quality. For Nepali documents, multilingual embeddings and OCR quality are important because English-only models and noisy scanned text can reduce retrieval accuracy.

## Current Project Status

The project is functional and presentation-ready:

- Python files compile successfully.
- Main command-line tools run.
- Curated corpus contains 50 PDFs.
- Current chunk output contains 50 chunk files and 446 total chunks.
- Extraction smoke test completed successfully.
- Curation, rechunking, combining text, and ground-truth mapping completed successfully in test runs.
- Beamer presentation has been revised for a six-minute delivery.

Known limitations:

- The existing extraction summary file is partial, although chunk files exist for all 50 documents.
- Some scanned PDFs produce sparse chunks, so OCR validation remains important.
- MiniLM baseline retrieval currently reports Recall@5 = 0.000 and MRR = 0.000.
- BGE-M3 multilingual benchmark should be run after model availability is confirmed.

## Results

The current baseline result is:

| Model | Queries | Recall@5 | MRR |
|---|---:|---:|---:|
| all-MiniLM-L6-v2 | 11 | 0.000 | 0.000 |

This result shows that an English-oriented baseline is weak for Nepali legal retrieval and that ground-truth chunk alignment must be handled carefully before judging the retrieval system.

## Paper Outline

1. Introduction: problem, motivation, and objectives.
2. Related Work: legal information retrieval, RAG preprocessing, multilingual embeddings, and OCR.
3. Methodology: scraping, curation, extraction routing, chunking, and benchmarking.
4. Corpus: source websites, categories, document types, and limitations.
5. Evaluation: query bank, ground truth, Recall@5, and MRR.
6. Results and Discussion: baseline results, observed errors, and improvements.
7. Conclusion: contributions and future work.

## Six-Minute Delivery Plan

| Time | Slides | Focus |
|---:|---|---|
| 0:00-0:30 | Title, Outline | Introduce topic and structure. |
| 0:30-1:20 | Background | Explain why Nepali municipal legal PDFs are hard to search. |
| 1:20-2:00 | Aim | State aim and objectives clearly. |
| 2:00-2:40 | Literature | Connect project to legal retrieval, RAG, embeddings, and OCR. |
| 2:40-3:45 | Methods | Explain the pipeline from scraping to benchmark. |
| 3:45-4:30 | Corpus | Present corpus size, sources, and chunk outputs. |
| 4:30-5:20 | Evaluation and Results | Explain metrics and baseline result. |
| 5:20-6:00 | Outline and Conclusion | Summarize contributions and next steps. |

## Short Speaking Script

Good morning. My presentation is titled **Semantic Search for Nepali Municipal Legal Documents**. The main problem is that municipal laws are available online, but mostly as scattered PDF files. For a normal user, finding the exact legal section for a question is difficult.

The aim of this project is to prepare these legal PDFs for semantic retrieval. I curated 50 documents, separated text-based and scanned PDFs, extracted text, created semantic chunks, and evaluated retrieval using query-level ground truth.

The method is an end-to-end pipeline. First, PDFs are scraped from municipal and federal sources. Then the curated corpus is passed through an extraction router. Text-based PDFs use PyMuPDF, while scanned PDFs require OCR. After extraction, documents are chunked and indexed for retrieval using FAISS.

The literature behind this work comes from legal information retrieval, retrieval-augmented generation, multilingual embeddings, and OCR. The key idea is that retrieval quality depends not only on the model, but also on extraction quality, chunk boundaries, and correct evaluation.

The current corpus has 50 PDFs, 830 pages, 50 chunk files, and 446 chunks. The query bank contains 11 evaluation questions. The MiniLM baseline currently gives Recall@5 and MRR of 0.000. This is useful because it shows the weakness of an English-oriented baseline and highlights the need for better multilingual models and cleaner ground-truth alignment.

In conclusion, this project creates a working pipeline from municipal legal PDFs to retrieval evaluation. The next steps are to validate OCR quality, run the BGE-M3 multilingual benchmark, expand the human-labeled query bank, and test hybrid retrieval methods.

## Rubric Alignment

- **Participation and Preparation:** Project files, report, and slides are organized for presentation.
- **Beamer Slides:** The revised presentation is in `thesis/presentation.tex`.
- **Contents:** Slides include title, background, motivation, aim/objectives, methods, literature review, paper outline, evaluation, results, and conclusion.
- **Delivery:** The speaking script is concise and structured for clear articulation.
- **Time Management:** The delivery plan is designed for a six-minute presentation.
