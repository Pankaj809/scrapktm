from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Iterable

from pipeline.chunking import chunk_text
from pipeline.extractors import PyMuPDFExtractor, resolve_surya_extractor
from pipeline.logging_utils import configure_logging
from pipeline.models import Chunk, DocumentRecord
from pipeline.router import DocumentRouter

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid extraction pipeline for curated corpus PDFs.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("curated_corpus_manifest.jsonl"),
        help="Path to curated corpus manifest JSONL.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("extraction_output"),
        help="Output directory for extracted text and chunks.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("logs/extraction_pipeline.log"),
        help="Log file path.",
    )
    parser.add_argument(
        "--surya-entrypoint",
        type=str,
        default="surya_entrypoint:ocr_callable",
        help="Python entrypoint for Surya OCR (module:function).",
    )
    parser.add_argument(
        "--disable-ocr",
        action="store_true",
        help="Disable OCR and route scanned PDFs through PyMuPDF.",
    )
    parser.add_argument(
        "--surya-device",
        type=str,
        default="mps",
        help="Device name for Surya OCR (default: mps).",
    )
    parser.add_argument(
        "--ocr-page-range",
        type=str,
        default=None,
        help="Optional page range for OCR (e.g. '0-2,5').",
    )
    parser.add_argument(
        "--ocr-max-pages",
        type=int,
        default=None,
        help="Limit OCR to the first N pages to speed up runs.",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Limit processing to the first N documents (for quick runs).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser.parse_args()


def load_manifest(path: Path) -> list[DocumentRecord]:
    records: list[DocumentRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            records.append(
                DocumentRecord(
                    doc_id=payload["doc_id"],
                    source=payload["source"],
                    category=payload["category"],
                    title=payload["title"],
                    file_path=Path(payload["file_path"]),
                    format_type=payload["format_type"],
                    language=payload.get("language", "ne"),
                    page_count=payload.get("page_count"),
                    relevance_notes=payload.get("relevance_notes"),
                )
            )
    return records


def write_chunks(chunks: Iterable[Chunk], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "text": chunk.text,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                        "heading": chunk.heading,
                        "metadata": chunk.metadata,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def main() -> None:
    args = parse_args()
    configure_logging(args.log_path, verbose=args.verbose)

    LOGGER.info("Step 1/4: Configure OCR limits")

    if args.ocr_page_range:
        os.environ["SURYA_PAGE_RANGE"] = args.ocr_page_range
    if args.ocr_max_pages:
        os.environ["SURYA_MAX_PAGES"] = str(args.ocr_max_pages)

    LOGGER.info("Step 2/4: Load manifest")
    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    records = load_manifest(args.manifest)
    if not records:
        raise SystemExit("No records found in manifest.")
    if args.max_docs:
        records = records[: args.max_docs]
        LOGGER.info("Limiting run to first %s documents", args.max_docs)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    text_dir = args.output_dir / "text"
    chunk_dir = args.output_dir / "chunks"
    text_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Step 3/4: Initialize extractors")
    text_extractor = PyMuPDFExtractor()
    ocr_extractor = None
    if not args.disable_ocr:
        ocr_extractor = resolve_surya_extractor(args.surya_entrypoint, args.surya_device)
    else:
        LOGGER.warning("OCR disabled; scanned PDFs will use PyMuPDF.")
    router = DocumentRouter(text_extractor, ocr_extractor)

    LOGGER.info("Step 4/4: Extract text + chunk")
    summary_path = args.output_dir / "extraction_summary.jsonl"
    with summary_path.open("w", encoding="utf-8") as summary_handle:
        for record in records:
            LOGGER.info("Processing %s (%s)", record.doc_id, record.format_type)
            result = router.route(record)
            LOGGER.info(
                "Completed %s via %s in %.2fs (accuracy=%s)",
                record.doc_id,
                result.method,
                result.metrics.duration_seconds,
                result.metrics.ocr_accuracy_score,
            )
            chunked = chunk_text(record.doc_id, result.text)

            text_path = text_dir / f"{record.doc_id}.txt"
            text_path.write_text(result.text, encoding="utf-8")

            chunk_path = chunk_dir / f"{record.doc_id}_chunks.jsonl"
            write_chunks(chunked, chunk_path)

            summary_handle.write(
                json.dumps(
                    {
                        "doc_id": record.doc_id,
                        "source": record.source,
                        "category": record.category,
                        "title": record.title,
                        "format_type": record.format_type,
                        "method": result.method,
                        "errors": result.errors,
                        "metrics": {
                            "duration_seconds": result.metrics.duration_seconds,
                            "page_count": result.metrics.page_count,
                            "ocr_accuracy_score": result.metrics.ocr_accuracy_score,
                            "ocr_accuracy_notes": result.metrics.ocr_accuracy_notes,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    LOGGER.info("Extraction complete. Summary written to %s", summary_path)


if __name__ == "__main__":
    main()
