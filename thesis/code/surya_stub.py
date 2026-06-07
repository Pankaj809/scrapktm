from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple


def ocr_callable(pdf_path: Path, device: str = "mps") -> Tuple[str, Optional[float], str]:
    """Fallback OCR callable for routing tests.

    This stub returns empty text with a note so the pipeline can run without
    Surya OCR installed. Replace with a real Surya OCR entrypoint in production.
    """
    note = (
        "Stub OCR used; no OCR engine configured. "
        "Provide a Surya OCR entrypoint for real extraction."
    )
    return "", None, note
