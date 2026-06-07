from __future__ import annotations

import logging
import re
from typing import Iterable, List, Sequence, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Chunk

LOGGER = logging.getLogger(__name__)

HEADING_PATTERNS = [
    re.compile(r"^\s*\d+(?:\.\d+)*\s+.+"),
    re.compile(r"^\s*[A-Z][A-Z\s]{4,}$"),
    re.compile(r"^\s*अध्याय\s+\d+.*"),
    re.compile(r"^\s*धारा\s+\d+.*"),
]


def _is_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in HEADING_PATTERNS)


def semantic_sections(text: str) -> List[tuple[str | None, str, int, int]]:
    lines = text.splitlines()
    sections: List[tuple[str | None, str, int, int]] = []
    current_heading: str | None = None
    buffer: List[str] = []
    start_char = 0
    cursor = 0

    def flush() -> None:
        nonlocal buffer, start_char
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        if body:
            end_char = start_char + len(body)
            sections.append((current_heading, body, start_char, end_char))
        buffer = []

    for line in lines:
        line_len = len(line) + 1
        if _is_heading(line):
            flush()
            current_heading = line.strip()
            start_char = cursor
        else:
            buffer.append(line)
        cursor += line_len

    flush()
    return sections


def _split_with_offsets(
    text: str,
    start_offset: int,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Tuple[str, int, int]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=lambda value: len(value.split()),
        separators=["\n\n", "\n", " ", ""],
    )
    pieces = splitter.split_text(text)
    offsets: List[Tuple[str, int, int]] = []
    cursor = 0
    for piece in pieces:
        start = text.find(piece, cursor)
        if start == -1:
            start = cursor
        end = start + len(piece)
        cursor = end
        offsets.append((piece, start_offset + start, start_offset + end))
    return offsets


def _build_chunks(
    doc_id: str,
    section_index: int | None,
    heading: str | None,
    pieces: Sequence[Tuple[str, int, int]],
    strategy: str,
) -> List[Chunk]:
    chunks: List[Chunk] = []
    for idx, (piece, start, end) in enumerate(pieces, start=1):
        if section_index is None:
            chunk_id = f"{doc_id}_chunk_{idx}"
        else:
            chunk_id = f"{doc_id}_sec{section_index}_chunk_{idx}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                text=piece,
                start_char=start,
                end_char=end,
                heading=heading,
                metadata={"strategy": strategy, "section_index": section_index},
            )
        )
    return chunks


def chunk_text(doc_id: str, text: str, chunk_size: int = 512, chunk_overlap: int = 128) -> List[Chunk]:
    if not text.strip():
        return []

    sections = semantic_sections(text)
    if len(sections) >= 2:
        LOGGER.debug("Semantic headings detected for %s (%s sections)", doc_id, len(sections))
        chunks: List[Chunk] = []
        for idx, (heading, body, start, _end) in enumerate(sections, start=1):
            body_word_count = len(body.split())
            if body_word_count <= chunk_size:
                pieces = [(body, start, start + len(body))]
                strategy = "semantic"
            else:
                pieces = _split_with_offsets(body, start, chunk_size, chunk_overlap)
                strategy = "semantic_subchunk"
            chunks.extend(_build_chunks(doc_id, idx, heading, pieces, strategy))
        return chunks

    pieces = _split_with_offsets(text, 0, chunk_size, chunk_overlap)
    return _build_chunks(doc_id, None, None, pieces, "fixed")
