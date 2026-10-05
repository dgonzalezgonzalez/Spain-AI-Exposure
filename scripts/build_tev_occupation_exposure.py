"""Run the frozen occupation experiment through local TEV, or replay its cache."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from src.jev import archive_cache, restore_cache_archive, write_json, fingerprint
from src.tev import classify, runtime_provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-occupations", type=int)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/tev")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/cache/tev")
    args = parser.parse_args()
    if args.max_occupations and args.output_dir == ROOT / "data/processed/tev":
        raise ValueError("Pilot requires a separate output directory")
    inputs = ROOT / "data/processed/jev"
    source_manifest = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
    for name in ("spanish_inputs.csv", "us_catalogue.csv"):
        actual = hashlib.sha256((inputs / name).read_bytes()).hexdigest()
        if actual != source_manifest["artifacts"][name]:
            raise ValueError(f"Frozen Jev source snapshot changed: {name}")
    spanish = pd.read_csv(inputs / "spanish_inputs.csv", dtype={"CNO4": str})
    us = pd.read_csv(inputs / "us_catalogue.csv", dtype={"occ_code": str})
    if args.max_occupations:
        spanish = spanish.head(args.max_occupations)
    elif len(spanish) != 502 or len(us) != 756:
        raise ValueError("Production experiment requires all 502 CNO4 and 756 O*NET occupations")
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    provenance_path = out / "runtime.json"
    if args.offline:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    else:
        provenance = runtime_provenance()
        if provenance_path.exists() and json.loads(provenance_path.read_text(encoding="utf-8")) != provenance:
            raise ValueError("Runtime changed; use a separate experiment directory")
        write_json(provenance_path, provenance)
    restore_cache_archive(out / "tev_response_cache.zip", args.cache_dir)
    estimates, probabilities, scores, audit, questions, paths = classify(
        spanish, us, args.cache_dir, provenance, offline=args.offline,
        progress=lambda text: print(text, flush=True))
    spanish.to_csv(out / "spanish_inputs.csv", index=False)
    us.to_csv(out / "us_catalogue.csv", index=False)
    estimates.to_csv(out / "occupation_estimates.csv", index=False)
    probabilities.to_csv(out / "occupation_probabilities.csv.gz", index=False,
                         compression={"method": "gzip", "mtime": 0})
    scores.to_csv(out / "direct_score_probabilities.csv", index=False)
    write_json(out / "questions.json", questions)
    write_json(out / "hierarchy_paths.json", paths)
    write_json(out / "request_audit.json", audit)
    archive_cache(args.cache_dir, [item["request_sha256"] for item in audit], out / "tev_response_cache.zip")
    write_json(out / "manifest.json", {
        "model": provenance, "spanish_count": len(spanish), "category_count": len(us),
        "partial_run": bool(args.max_occupations),
        "method": "exhaustive_SOC_prefix_hierarchy_without_pruning",
        "joint_probability": "Product of conditional probabilities along each full SOC path",
        "nearest": "Exposure of highest joint-probability O*NET occupation",
        "weighted": "Probability-weighted observed exposure across all 756 O*NET occupations",
        "direct": "Expected Score level divided by 9",
        "questions_sha256": fingerprint(questions),
        "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())
                      if p.is_file() and p.name != "manifest.json"},
    })
    print(f"Done: {len(estimates)} TEV occupations", flush=True)


if __name__ == "__main__":
    main()
