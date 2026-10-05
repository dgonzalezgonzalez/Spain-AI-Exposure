"""Check fresh TEV probabilities across repeated requests and model reloads."""
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import requests
from src.jev import occupation_state, fingerprint, write_json
from src.jev_questions import tier_question
from src.tev import TevClient, runtime_provenance, MODEL, string_question, API


def main() -> None:
    provenance = runtime_provenance()
    row = pd.read_csv(ROOT / "data/processed/jev/spanish_inputs.csv", dtype={"CNO4": str}).iloc[100].to_dict()
    question = string_question(tier_question())
    client = TevClient(ROOT / "data/cache/tev_audit", provenance)
    payload = {"model": MODEL, "state": occupation_state(row),
               "questions": {"tier": question}, "keep_alive": "30m"}
    runs = []
    for index in range(4):
        if index == 3:
            requests.post(API + "/api/generate", json={"model": MODEL, "keep_alive": 0}, timeout=120).raise_for_status()
        started = time.monotonic()
        response, _, _ = client.evaluate(payload, fresh=True)
        runs.append({"kind": "reset_before_request",
                     "answers_sha256": fingerprint(response["answers"]),
                     "answers": response["answers"], "seconds": time.monotonic()-started})
        print(f"Repeat {index+1}/4: {runs[-1]['seconds']:.1f}s {runs[-1]['answers_sha256']}", flush=True)
    identical = len({run["answers_sha256"] for run in runs}) == 1
    write_json(ROOT / "data/processed/tev/repeatability_audit.json",
               {"runtime": provenance, "request": payload, "fresh_runs": runs,
                "bit_identical_answers": identical,
                "scope": "Repeated fresh inference on this pinned hardware/runtime; finite check, not a cross-platform guarantee"})
    if not identical:
        raise RuntimeError("Fresh TEV answers differ; do not claim deterministic inference")
    print("Fresh answers after model resets bit-identical", flush=True)


if __name__ == "__main__":
    main()
