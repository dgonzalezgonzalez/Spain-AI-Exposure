"""Prepare and render the Jev robustness and exposure-correlation outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "analysis" / "paper_replication"
RUNTIME = PACKAGE / "runtime"

if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from lib.jev_robustness import (  # noqa: E402
    build_exposure_correlation_matrix,
    build_jev_robustness_outputs,
    prepare_jev_panel,
)
from lib.job_tiers import build_job_tier_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-family", choices=("jev", "tev"), default="jev")
    parser.add_argument("action", choices=("prepare", "outputs", "tiers", "matrix"))
    parser.add_argument("--prepared-panel", type=Path, default=RUNTIME / "data" / "prepared" / "est_total_cno4.csv")
    parser.add_argument("--jev-estimates", type=Path, default=ROOT / "data" / "processed" / "jev" / "occupation_estimates.csv")
    parser.add_argument("--jev-panel", type=Path, default=RUNTIME / "data" / "prepared" / "est_total_cno4_jev.csv")
    parser.add_argument("--estimates-dir", type=Path, default=RUNTIME / "intermediate")
    parser.add_argument("--output-dir", type=Path, default=PACKAGE / "figuresNtables")
    parser.add_argument("--bls-workbook", type=Path, default=None)
    parser.add_argument("--frs-workbook", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.model_family == "tev":
        if args.jev_estimates == ROOT / "data" / "processed" / "jev" / "occupation_estimates.csv":
            args.jev_estimates = ROOT / "data" / "processed" / "tev" / "occupation_estimates.csv"
        if args.jev_panel == RUNTIME / "data" / "prepared" / "est_total_cno4_jev.csv":
            args.jev_panel = RUNTIME / "data" / "prepared" / "est_total_cno4_tev.csv"
        if args.output_dir == PACKAGE / "figuresNtables":
            args.output_dir = PACKAGE / "figuresNtables" / "tev"
    if args.action == "prepare":
        print(
            "Prepared Jev panel:",
            prepare_jev_panel(args.prepared_panel, args.jev_estimates, args.jev_panel, model_family=args.model_family),
        )
    if args.action == "outputs":
        outputs = build_jev_robustness_outputs(args.estimates_dir, args.output_dir, model_family=args.model_family)
        print("Jev robustness outputs:", outputs)
    if args.action == "tiers":
        outputs = build_job_tier_outputs(args.estimates_dir, args.output_dir,
                                         model_family=args.model_family)
        print("Joint tier DiD outputs:", outputs)
    if args.action == "matrix":
        summary = build_exposure_correlation_matrix(
            project_root=ROOT,
            prepared_panel=args.jev_panel,
            jev_estimates=args.jev_estimates,
            output_dir=args.output_dir,
            bls_workbook=args.bls_workbook,
            frs_workbook=args.frs_workbook,
            model_family=args.model_family,
        )
        print("Exposure matrix:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
