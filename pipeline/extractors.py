from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .models import ExtractionMetrics, ExtractionResult

LOGGER = logging.getLogger(__name__)


@dataclass
class PyMuPDFExtractor:
    def extract(self, doc_id: str, path: Path) -> ExtractionResult:
        start = time.perf_counter()
        errors: list[str] = []
        text = ""
        page_count = None

        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover - environment issue
            raise RuntimeError("PyMuPDF is required for text-based extraction.") from exc

        try:
            with fitz.open(path) as doc:
                page_count = doc.page_count
                text = "\n".join(page.get_text("text") for page in doc)
        except Exception as exc:  # pragma: no cover - depends on input PDFs
            errors.append(str(exc))
            LOGGER.exception("PyMuPDF extraction failed for %s", doc_id)

        duration = time.perf_counter() - start
        metrics = ExtractionMetrics(duration_seconds=duration, page_count=page_count)
        return ExtractionResult(doc_id=doc_id, text=text, method="pymupdf", metrics=metrics, errors=errors)


class SuryaOCRExtractor:
    def __init__(self, ocr_callable: Callable[[Path, str], str], device: str = "mps") -> None:
        self.ocr_callable = ocr_callable
        self.device = device

    @staticmethod
    def from_entrypoint(entrypoint: str, device: str = "mps") -> "SuryaOCRExtractor":
        module_name, _, attr = entrypoint.partition(":")
        if not module_name or not attr:
            raise ValueError("Surya OCR entrypoint must be in the form 'module:function'.")
        module = importlib.import_module(module_name)
        target = getattr(module, attr, None)
        if target is None:
            raise AttributeError(f"Entrypoint {entrypoint} not found")
        if callable(target):
            return SuryaOCRExtractor(target, device=device)
        raise TypeError(f"Entrypoint {entrypoint} is not callable")

    def extract(self, doc_id: str, path: Path) -> ExtractionResult:
        start = time.perf_counter()
        errors: list[str] = []
        text = ""
        accuracy_score: Optional[float] = None
        accuracy_notes: Optional[str] = None
        page_count: Optional[int] = None

        try:
            text, accuracy_score, accuracy_notes, page_count = self._run_ocr(path)
        except Exception as exc:  # pragma: no cover - depends on OCR runtime
            error_msg = str(exc)
            errors.append(error_msg)
            if accuracy_notes is None:
                accuracy_notes = f"OCR failed: {error_msg}"
            LOGGER.exception("Surya OCR failed for %s", doc_id)

        duration = time.perf_counter() - start
        metrics = ExtractionMetrics(
            duration_seconds=duration,
            page_count=page_count,
            ocr_accuracy_score=accuracy_score,
            ocr_accuracy_notes=accuracy_notes,
        )
        return ExtractionResult(doc_id=doc_id, text=text, method="surya_ocr", metrics=metrics, errors=errors)

    def _run_ocr(self, path: Path) -> tuple[str, Optional[float], Optional[str], Optional[int]]:
        result = self.ocr_callable(path, self.device)
        if isinstance(result, tuple):
            text = result[0]
            accuracy = result[1] if len(result) > 1 else None
            notes = result[2] if len(result) > 2 else None
            page_count = result[3] if len(result) > 3 else None
            return text, accuracy, notes, page_count
        return str(result), None, "OCR accuracy not reported by Surya callable.", None


def resolve_surya_extractor(entrypoint: Optional[str], device: str) -> SuryaOCRExtractor:
    if not entrypoint:
        raise RuntimeError(
            "Surya OCR entrypoint not configured. Provide --surya-entrypoint 'module:function'."
        )
    LOGGER.info("Loading Surya OCR entrypoint %s on device %s", entrypoint, device)
    return SuryaOCRExtractor.from_entrypoint(entrypoint, device=device)
