from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DocumentRecord:
    doc_id: str
    source: str
    category: str
    title: str
    file_path: Path
    format_type: str
    language: str
    page_count: Optional[int] = None
    relevance_notes: Optional[str] = None


@dataclass
class ExtractionMetrics:
    duration_seconds: float
    page_count: Optional[int] = None
    ocr_accuracy_score: Optional[float] = None
    ocr_accuracy_notes: Optional[str] = None


@dataclass
class ExtractionResult:
    doc_id: str
    text: str
    method: str
    metrics: ExtractionMetrics
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    start_char: int
    end_char: int
    heading: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
