"""Validate released Jev artifacts without an API key or network access."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


def validate(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name:
            raise ValueError("Artifact names must be plain filenames")
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    estimates = pd.read_csv(directory / "occupation_estimates.csv", dtype={"cno4": str, "jev_matched_occ_code": str})
    probabilities = pd.read_csv(directory / "occupation_probabilities.csv.gz", dtype={"cno4": str})
    direct_probabilities = pd.read_csv(directory / "direct_score_probabilities.csv", dtype={"cno4": str})
    spanish = pd.read_csv(directory / "spanish_inputs.csv", dtype={"CNO4": str})
    us = pd.read_csv(directory / "us_catalogue.csv", dtype={"occ_code": str})
    if any(frame[key].duplicated().any() for frame, key in
           ((estimates, "cno4"), (probabilities, "cno4"), (spanish, "CNO4"), (us, "occ_code"))):
        raise ValueError("Duplicate occupation codes")
    if set(estimates.cno4) != set(spanish.CNO4) or set(probabilities.cno4) != set(spanish.CNO4):
        raise ValueError("Spanish coverage mismatch")
    if direct_probabilities.cno4.duplicated().any() or set(direct_probabilities.cno4) != set(spanish.CNO4):
        raise ValueError("Direct Score coverage mismatch")
    if len(us) != manifest["category_count"] or len(estimates) != manifest["spanish_count"]:
        raise ValueError("Manifest counts differ from artifacts")
    if not manifest["partial_run"] and len(estimates) != manifest["full_cno_count"]:
        raise ValueError("Incomplete full run")
    codes = sorted(us.occ_code)
    if set(probabilities.columns) != {"cno4", *codes}:
        raise ValueError("US probability coverage mismatch")
    estimates = estimates.set_index("cno4").sort_index()
    probabilities = probabilities.set_index("cno4").sort_index()[codes]
    expected_levels = [f"level_{i}" for i in range(10)]
    if set(direct_probabilities.columns) != {"cno4", *expected_levels}:
        raise ValueError("Direct Score level coverage mismatch")
    direct_probabilities = direct_probabilities.set_index("cno4").sort_index()[expected_levels]
    direct_p = direct_probabilities.to_numpy(dtype=float)
    if not np.isfinite(direct_p).all() or (direct_p < 0).any() or (direct_p > 1).any():
        raise ValueError("Invalid direct Score probabilities")
    if not np.allclose(direct_p.sum(axis=1), 1, atol=1e-10, rtol=0):
        raise ValueError("Direct Score probability mass is not one")
    direct_estimate = direct_p @ (np.arange(10) / 9)
    if not np.allclose(estimates.observed_exposure_jev_direct, direct_estimate, atol=1e-12, rtol=0):
        raise ValueError("Direct exposure differs from Score expected level")
    if not estimates.observed_exposure_jev_direct.between(0, 1).all():
        raise ValueError("Direct exposure outside [0, 1]")
    if not estimates.jev_direct_rubric_version.eq(manifest["direct_rubric_version"]).all():
        raise ValueError("Direct rubric version mismatch")
    p = probabilities.to_numpy(dtype=float)
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("Invalid joint probabilities")
    if not np.allclose(p.sum(axis=1), 1, atol=1e-10, rtol=0):
        raise ValueError("Joint probability mass is not one")
    exposure = us.set_index("occ_code").loc[codes, "observed_exposure"].to_numpy(dtype=float)
    winner = p.argmax(axis=1)
    expected_codes = np.array(codes)[winner]
    if not np.array_equal(expected_codes, estimates.jev_matched_occ_code.to_numpy()):
        raise ValueError("Selected match differs from joint probability argmax")
    for name, expected in (
        ("observed_exposure_jev_nearest", exposure[winner]),
        ("observed_exposure_jev_weighted", p @ exposure),
        ("jev_match_probability", p.max(axis=1)),
    ):
        if not np.allclose(estimates[name], expected, atol=1e-12, rtol=0):
            raise ValueError(f"Calculation mismatch: {name}")
    tiers = estimates[[f"jev_tier_{tier}_probability" for tier in (1, 2, 3)]].to_numpy(dtype=float)
    if not np.isfinite(tiers).all() or (tiers < 0).any() or (tiers > 1).any() or not np.allclose(tiers.sum(axis=1), 1, atol=1e-10, rtol=0):
        raise ValueError("Invalid tier probabilities")
    if not np.array_equal(tiers.argmax(axis=1) + 1, estimates.jev_tier.to_numpy()):
        raise ValueError("Tier labels differ from probability argmax")
    if not estimates.jev_model.eq(manifest["model"]).all():
        raise ValueError("Model mismatch")
    questions = json.loads((directory / "questions.json").read_text(encoding="utf-8"))
    audit = json.loads((directory / "request_audit.json").read_text(encoding="utf-8"))
    observed = Counter((item["cno4"], question) for item in audit for question in item["question_ids"])
    expected = Counter((code, question) for code in estimates.index for question in questions)
    if observed != expected:
        raise ValueError("Audit does not cover every question exactly once per occupation")
    if len(audit) != manifest["requests"] or len({item["request_sha256"] for item in audit}) != len(audit):
        raise ValueError("Request audit count or uniqueness mismatch")
    all_hashes = {item["request_sha256"] for item in audit}
    if manifest.get("us_direct_benchmark") is not None:
        us_audit = json.loads((directory / "us_direct_request_audit.json").read_text(encoding="utf-8"))
        if len(us_audit) != manifest["us_direct_benchmark"]["requests"]:
            raise ValueError("US benchmark audit count mismatch")
        all_hashes.update(item["request_sha256"] for item in us_audit)
    with ZipFile(directory / "jev_response_cache.zip") as archive:
        if set(archive.namelist()) != {f"{key}.json" for key in all_hashes}:
            raise ValueError("Raw response archive differs from used requests")
    return {"spanish_occupations": len(estimates), "us_categories": len(us),
            "joint_probabilities_checked": int(p.size), "requests_checked": len(audit),
            "direct_scores_checked": len(direct_p),
            "max_probability_sum_error": float(np.abs(p.sum(axis=1) - 1).max()),
            "max_weighted_exposure_error": float(np.abs(estimates.observed_exposure_jev_weighted - p @ exposure).max()),
            "tier_counts": {str(key): int(value) for key, value in estimates.jev_tier.value_counts().sort_index().items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parents[1] / "data/processed/jev")
    print(json.dumps(validate(parser.parse_args().directory), indent=2))
