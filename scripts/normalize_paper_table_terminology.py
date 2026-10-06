"""Rerender frozen LaTeX tables through the production terminology formatter."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.paper_replication.lib.terminology import normalize_latex_terminology


def render_table(source: Path, destination: Path) -> None:
    original = source.read_text(encoding="utf-8")
    updated = normalize_latex_terminology(original)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for source in args.sources:
        render_table(source, args.output_dir / source.name)


if __name__ == "__main__":
    main()
