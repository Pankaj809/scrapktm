"""Merge dense_analysis.json + dense_bge_m3.json into the resource table.

Turns the peak-RSS / index-time numbers measured by dense_eval_local.py and
dense_eval_bge_m3.py into the LaTeX rows for Table (encoder, params, peak
memory, index time on 446 chunks) cited in the paper's Reproducibility
section.

Run from the repository root, after both eval scripts:

    ./.venv/bin/python thesis/code/dense_resource_table.py

Emits:
  thesis/ieee_paper/generated/dense_resource_table.tex
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "thesis" / "ieee_paper" / "generated"


def main():
    local = json.loads((GEN / "dense_analysis.json").read_text(encoding="utf-8"))
    bge = json.loads((GEN / "dense_bge_m3.json").read_text(encoding="utf-8"))

    rows = [(m["label"], m["params"], m["peak_rss_mb"], m["index_time_s"])
            for m in local["models"].values()]
    rows.append((bge["label"], bge["params"], bge["peak_rss_mb"], bge["index_time_s"]))

    lines = []
    for label, params, rss_mb, t_s in rows:
        params_disp = f"{params / 1e6:.1f}M"
        rss_gb = rss_mb / 1024
        t_disp = f"{t_s:.1f}\\,s" if t_s < 60 else f"{t_s / 60:.1f}\\,min"
        lines.append(f"{label} & {params_disp} & {rss_gb:.2f}\\,GB & {t_disp} \\\\")

    out_path = GEN / "dense_resource_table.tex"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out_path.relative_to(ROOT))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
