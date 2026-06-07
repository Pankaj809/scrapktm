# Thesis LaTeX Package (scrapktm)

This folder contains a complete LaTeX thesis and Beamer presentation for the **scrapktm** project.

## Files

| File | Description |
|------|-------------|
| `main.tex` | Full thesis (report class, ~80 pages when compiled) |
| `presentation.tex` | Beamer slides (16:9) |
| `preamble.tex` | Shared packages, colors, listings style |
| `frontmatter.tex` | Title page, abstract, TOC |
| `chapters/01-introduction.tex` … `08-conclusion.tex` | Thesis chapters |
| `appendix.tex` | Repository structure, CLI reference |
| `references.bib` | Bibliography |
| `Makefile` | Build automation |

## Prerequisites

Install a TeX distribution:

- **macOS**: `brew install --cask mactex-no-gui` (or full MacTeX)
- **Linux**: `sudo apt install texlive-full`
- **Windows**: MiKTeX or TeX Live

## Build PDFs

```bash
cd thesis

# Build thesis only
make thesis
# Output: main.pdf

# Build Beamer slides only
make slides
# Output: presentation.pdf

# Build both
make all
```

Manual build:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex

pdflatex presentation.tex
pdflatex presentation.tex
```

## Customize Before Submission

Edit these placeholders in `frontmatter.tex` and `presentation.tex`:

- **Author Name**
- **Roll No.**
- **Supervisor Name**
- **University / Department** (default: Tribhuvan University)

## Content Sources

The thesis content is derived from:

- `curated_corpus_summary.md` — corpus statistics
- `pipeline.md` — extraction architecture
- `research_query_bank_v1.md` — evaluation queries
- `retrieval_benchmark_results.csv` — baseline results
- `ground_truth_mapping.json` — chunk ID alignment
- `embedding_benchmark.py`, `extract_corpus.py` — methodology

## Notes

- Projected BGE-M3 results in Chapter 6 are placeholders; replace with actual benchmark output after running the full evaluation.
- For Nepali Devanagari text in the thesis body, consider compiling with XeLaTeX and `fontspec` + Noto Sans Devanagari.
