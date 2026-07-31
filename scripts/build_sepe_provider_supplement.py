from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.sepe_supplement import parse_provider_workbook


DEFAULT_REPORTS = [("2220", "2022-09"), ("2230", "2022-09"), ("2323", "2022-09")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize supplementary annual data supplied directly by SEPE.")
    parser.add_argument("workbook", type=Path, help="SEPE annual occupation/province workbook.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "supplemental" / "sepe_provider_missing_breakdowns.csv",
    )
    args = parser.parse_args()
    supplement = parse_provider_workbook(args.workbook, DEFAULT_REPORTS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    supplement.to_csv(args.output, index=False)
    print(f"Wrote {len(supplement):,} rows for {len(DEFAULT_REPORTS)} reports to {args.output}")


if __name__ == "__main__":
    main()
