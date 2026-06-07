# Build thesis PDF and Beamer presentation
# Requires: pdflatex, bibtex

MAIN = main
SLIDES = presentation
LATEX = pdflatex
BIBTEX = bibtex

.PHONY: all thesis slides clean distclean

all: thesis slides

thesis: $(MAIN).pdf

slides: $(SLIDES).pdf

$(MAIN).pdf: $(MAIN).tex preamble.tex frontmatter.tex references.bib appendix.tex chapters/*.tex
	$(LATEX) -interaction=nonstopmode $(MAIN).tex
	$(BIBTEX) $(MAIN)
	$(LATEX) -interaction=nonstopmode $(MAIN).tex
	$(LATEX) -interaction=nonstopmode $(MAIN).tex

$(SLIDES).pdf: $(SLIDES).tex preamble-beamer.tex
	$(LATEX) -interaction=nonstopmode $(SLIDES).tex
	$(LATEX) -interaction=nonstopmode $(SLIDES).tex

clean:
	rm -f *.aux *.log *.out *.toc *.lof *.lot *.bbl *.blg *.nav *.snm *.vrb

distclean: clean
	rm -f $(MAIN).pdf $(SLIDES).pdf
