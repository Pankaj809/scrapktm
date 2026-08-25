"""Combine all .txt files in extraction_output/text into a single .txt.

- Leaves source files unchanged.
- Inserts the source filename before each file's content.
- Uses UTF-8 read/write with graceful error replacement.

Usage:
  python combine_texts.py \
    --input-dir extraction_output/text \
    --output-file extraction_output/text/all_combined.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path


def combine_texts(input_dir: Path, output_file: Path) -> int:
    txt_files = sorted(p for p in input_dir.glob("*.txt") if p.is_file())

    if not txt_files:
        raise SystemExit(f"No .txt files found in: {input_dir}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Stream write to avoid holding everything in memory.
    with output_file.open("w", encoding="utf-8", errors="replace", newline="\n") as out:
        for i, path in enumerate(txt_files):
            if i:
                out.write("\n\n")

            header = f"===== {path.name} ====="
            out.write(header)
            out.write("\n")

            content = path.read_text(encoding="utf-8", errors="replace")
            # Normalize line endings a bit for downstream indexing.
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            out.write(content.rstrip("\n"))
            out.write("\n")

    return len(txt_files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("extraction_output/text"),
        help="Directory containing .txt files (default: extraction_output/text)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("extraction_output/text/all_combined.txt"),
        help="Combined output file path (default: extraction_output/text/all_combined.txt)",
    )

    args = parser.parse_args()

    count = combine_texts(args.input_dir, args.output_file)
    print(f"Wrote {args.output_file} from {count} input files.")


if __name__ == "__main__":
    main()
