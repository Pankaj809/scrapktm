from __future__ import annotations

import logging

from .extractors import PyMuPDFExtractor, SuryaOCRExtractor
from .models import DocumentRecord, ExtractionResult

LOGGER = logging.getLogger(__name__)


class DocumentRouter:
    def __init__(
        self,
        text_extractor: PyMuPDFExtractor,
        ocr_extractor: SuryaOCRExtractor | None = None,
    ) -> None:
        self.text_extractor = text_extractor
        self.ocr_extractor = ocr_extractor

    def route(self, record: DocumentRecord) -> ExtractionResult:
        format_type = (record.format_type or "").lower()
        if format_type == "text_based":
            LOGGER.info("Routing %s to PyMuPDF extractor", record.doc_id)
            return self.text_extractor.extract(record.doc_id, record.file_path)
        if format_type == "scanned":
            if self.ocr_extractor is None:
                LOGGER.warning("OCR disabled; routing %s to PyMuPDF", record.doc_id)
                return self.text_extractor.extract(record.doc_id, record.file_path)
            LOGGER.info("Routing %s to Surya OCR", record.doc_id)
            return self.ocr_extractor.extract(record.doc_id, record.file_path)
        LOGGER.warning("Unknown format_type '%s' for %s; defaulting to PyMuPDF", format_type, record.doc_id)
        return self.text_extractor.extract(record.doc_id, record.file_path)
