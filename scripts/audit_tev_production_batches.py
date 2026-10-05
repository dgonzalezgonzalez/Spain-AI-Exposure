"""Repeat actual Score, hierarchy, and tier batches from a clean model state."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.jev import direct_exposure_state, occupation_state, fingerprint, write_json
from src.jev_questions import direct_exposure_question, tier_question
from src.tev import build_hierarchy, pack_requests, string_question, TevClient, runtime_provenance


def main() -> None:
    inputs = ROOT / "data/processed/jev"
    spanish = pd.read_csv(inputs / "spanish_inputs.csv", dtype={"CNO4": str})
    catalogue = pd.read_csv(inputs / "us_catalogue.csv", dtype={"occ_code": str})
    row = spanish.iloc[0].to_dict()
    nodes, _ = build_hierarchy(catalogue)
    matching = pack_requests(occupation_state(row), {**nodes, "tier": string_question(tier_question())})
    cases = {
        "direct_score": pack_requests(direct_exposure_state(row), {"direct_exposure": direct_exposure_question()})[0],
        "soc_root_batch": matching[0],
        "tier_batch": matching[-1],
    }
    provenance = runtime_provenance()
    if not provenance["server"]["reset_before_uncached_request"]:
        raise ValueError("Production repeatability requires a model reset before every fresh request")
    client = TevClient(ROOT / "data/cache/tev_audit", provenance)
    audit = {"runtime": provenance, "cases": {},
             "scope": "Two uncached cold-start evaluations of each actual production batch on this pinned machine; finite verification, not a universal guarantee"}
    try:
        for name, payload in cases.items():
            runs = []
            for repeat in range(2):
                print(f"Production repeatability: {name}, fresh reset {repeat + 1}/2", flush=True)
                response, _, _ = client.evaluate(payload, fresh=True)
                runs.append({"answers": response["answers"], "usage": response["usage"],
                             "answers_sha256": fingerprint(response["answers"])})
            identical = runs[0]["answers_sha256"] == runs[1]["answers_sha256"]
            audit["cases"][name] = {"request": payload, "runs": runs, "bit_identical_answers": identical}
            write_json(ROOT / "data/processed/tev/repeatability_production_audit.json", audit)
            if not identical:
                raise RuntimeError(f"Production batch is not repeatable: {name}; stop production inference")
            print(f"Production repeatability: {name} bit-identical", flush=True)
    finally:
        client.session.close()


if __name__ == "__main__":
    main()
