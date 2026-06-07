from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Optional, Tuple

from bs4 import BeautifulSoup
from surya.inference import SuryaInferenceManager
from surya.inference.parsers import clean_block_html
from surya.recognition import RecognitionPredictor
from surya.scripts.config import CLILoader
from surya.settings import settings


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)


def _resolve_page_range() -> str | None:
    page_range = os.getenv("SURYA_PAGE_RANGE")
    max_pages = os.getenv("SURYA_MAX_PAGES")
    if page_range:
        return page_range
    if max_pages:
        count = max(0, int(max_pages))
        return f"0-{count - 1}" if count else None
    return None


def ocr_callable(pdf_path: Path, device: str = "mps") -> Tuple[str, Optional[float], str, int]:
    """Run Surya OCR on a PDF and return text plus accuracy notes.

    Returns:
        text, accuracy_score, accuracy_notes, page_count
    """
    settings.TORCH_DEVICE = device

    page_range = _resolve_page_range()

    with tempfile.TemporaryDirectory(prefix="surya_results_") as tmp_dir:
        loader = CLILoader(
            str(pdf_path),
            {
                "output_dir": tmp_dir,
                "debug": False,
                "page_range": page_range,
                "images": False,
            },
            highres=True,
        )
        manager = SuryaInferenceManager()
        recognizer = RecognitionPredictor(manager)
        page_results = recognizer(loader.highres_images, full_page=True)

    page_texts = []
    for page in page_results:
        blocks = sorted(page.blocks, key=lambda blk: blk.reading_order)
        block_texts = []
        for block in blocks:
            cleaned = clean_block_html(block.html)
            text = _html_to_text(cleaned)
            if text:
                block_texts.append(text)
        page_texts.append("\n".join(block_texts))

    joined = "\n\n".join(page_texts)
    notes = "Surya OCR executed; accuracy scoring not provided by API." \
        + f" Device={device}."
    return joined, None, notes, len(page_results)
