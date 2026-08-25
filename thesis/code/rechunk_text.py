from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.chunking import chunk_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rechunk extracted text into smaller paragraph-level chunks.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("extraction_output/text"),
        help="Directory containing extracted .txt files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("extraction_output/chunks_v2"),
        help="Directory to write rechunked JSONL files.",
    )
    parser.add_argument(
        "--doc-ids",
        type=str,
        default="",
        help="Comma-separated doc IDs to process (e.g., KTM_FIN_002,LMC_MUN_004).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=220,
        help="Target chunk size in words for subchunks.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=40,
        help="Word overlap between subchunks.",
    )
    return parser.parse_args()


def load_doc_ids(input_dir: Path, doc_ids_arg: str) -> list[str]:
    if doc_ids_arg.strip():
        return [doc_id.strip() for doc_id in doc_ids_arg.split(",") if doc_id.strip()]

    return [path.stem for path in input_dir.glob("*.txt")]


def write_chunks(output_path: Path, chunks) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            record = {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "text": chunk.text,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "heading": chunk.heading,
                "metadata": chunk.metadata,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    doc_ids = load_doc_ids(input_dir, args.doc_ids)
    for doc_id in doc_ids:
        source_path = input_dir / f"{doc_id}.txt"
        if not source_path.exists():
            print(f"Skipping missing file: {source_path}")
            continue

        text = source_path.read_text(encoding="utf-8")
        chunks = chunk_text(doc_id, text, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
        output_path = output_dir / f"{doc_id}_chunks.jsonl"
        write_chunks(output_path, chunks)
        print(f"Wrote {len(chunks)} chunks to {output_path}")


if __name__ == "__main__":
    main()
