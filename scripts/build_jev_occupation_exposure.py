"""Build Jev CNO4 exposure and Messy Jobs tiers, optionally merging into SEPE."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.config import PipelineConfig, ANTHROPIC_JOB_EXPOSURE_URL
from src.download_anthropic import download_anthropic_job_exposure
from src.jev import (
    archive_cache, classify_direct_exposure, classify_direct_exposure_states, classify_occupations,
    direct_exposure_state,
    fingerprint, matching_questions, merge_sepe_file, restore_cache_archive,
    occupation_state, pack_questions, validate_catalogue, write_json,
)
from src.jev_questions import (
    ANTHROPIC_APPENDIX_URL, ANTHROPIC_PAPER_URL,
    DIRECT_EXPOSURE_RUBRIC_VERSION, MODEL, RUBRIC_VERSION,
    TALK_SUMMARY_URL, VIDEO_URL, direct_exposure_question,
)
from src.taxonomy import add_onet_descriptions, load_cno4_records, ONET_OCCUPATION_DATA_URL, CNO11_NOTES_URL


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--offline", action="store_true", help="Require local sources and cached Jev responses; never call API.")
    parser.add_argument("--from-snapshots", action="store_true",
                        help="With --offline, replay from versioned Spanish/US input snapshots and raw Jev cache.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and request budgets without API calls.")
    parser.add_argument("--max-occupations", type=int, help="Smoke test only; output must use a separate directory.")
    parser.add_argument("--cno4", nargs="+", help="Specific CNO4 codes for a pilot run.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/processed/jev")
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / "data/cache/jev")
    parser.add_argument("--merge-sepe", action="store_true")
    parser.add_argument("--benchmark-us-direct", action="store_true",
                        help="Score US O*NET descriptions without exposing known values to Jev; save comparison.")
    parser.add_argument("--sepe-path", type=Path, default=PROJECT_ROOT / "data/processed/sepe_cno4_monthly_ai_exposure.csv")
    parser.add_argument("--sepe-output", type=Path, default=PROJECT_ROOT / "data/processed/sepe_cno4_monthly_ai_exposure_jev.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.workers < 1 or (args.max_occupations is not None and args.max_occupations < 1):
        raise ValueError("Workers and occupation limits must be positive")
    if args.from_snapshots and not args.offline:
        raise ValueError("--from-snapshots requires --offline")
    partial = bool(args.max_occupations or args.cno4)
    if partial and args.output_dir.resolve() == (PROJECT_ROOT / "data/processed/jev").resolve():
        raise ValueError("Pilot runs require --output-dir to avoid overwriting full results")
    if partial and args.merge_sepe:
        raise ValueError("Cannot merge a pilot subset into SEPE")
    if partial and args.benchmark_us_direct:
        raise ValueError("US benchmark requires a full Spanish run")
    config = PipelineConfig()
    sources = {
        "anthropic": (config.raw_dir / "anthropic/job_exposure.csv", ANTHROPIC_JOB_EXPOSURE_URL),
        "onet": (config.raw_dir / "anthropic/Occupation_Data_30_3.xlsx", ONET_OCCUPATION_DATA_URL),
        "cno": (config.raw_dir / "ine/cno11_notas.pdf", CNO11_NOTES_URL),
    }
    if args.from_snapshots:
        previous = json.loads((args.output_dir / "manifest.json").read_text(encoding="utf-8"))
        for name in ("spanish_inputs.csv", "us_catalogue.csv"):
            if file_sha256(args.output_dir / name) != previous["artifacts"][name]:
                raise ValueError(f"Input snapshot hash mismatch: {name}")
        spanish = pd.read_csv(args.output_dir / "spanish_inputs.csv", dtype={"CNO4": str})
        us = validate_catalogue(pd.read_csv(args.output_dir / "us_catalogue.csv", dtype={"occ_code": str}))
        source_manifest = previous["source_files"]
    else:
        if args.offline and any(not path.exists() for path, _ in sources.values()):
            raise FileNotFoundError("Offline run requires cached Anthropic, O*NET and CNO source files")
        anthropic_path = download_anthropic_job_exposure(config)
        # Strict loading: never silently drop a category with missing exposure.
        raw_us = pd.read_csv(anthropic_path, dtype={"occ_code": "string", "title": "string"})
        us = validate_catalogue(add_onet_descriptions(raw_us, config))
        if len(us) != len(raw_us):
            raise ValueError("O*NET join changed Anthropic category count")
        spanish = load_cno4_records(config)
        source_manifest = {name: {"url": url, "sha256": file_sha256(path)} for name, (path, url) in sources.items()}
    total_spanish = len(spanish)
    if args.cno4:
        wanted = {str(code).zfill(4) for code in args.cno4}
        missing = wanted - set(spanish.CNO4)
        if missing:
            raise ValueError(f"Unknown requested CNO4: {sorted(missing)}")
        spanish = spanish[spanish.CNO4.isin(wanted)]
    if args.max_occupations:
        spanish = spanish.head(args.max_occupations)
    matching = matching_questions(us)
    questions = {**matching, "direct_exposure": direct_exposure_question()}
    matching_requests = sum(len(pack_questions(occupation_state(row), matching)) for row in spanish.to_dict("records"))
    for row in spanish.to_dict("records"):
        pack_questions(direct_exposure_state(row), {"direct_exposure": questions["direct_exposure"]})
    print(f"Inputs: {len(spanish)} CNO4, {len(us)} US occupations, {len(us.occ_code.str[:2].unique())} SOC groups; {matching_requests + len(spanish)} requests", flush=True)
    if args.dry_run:
        return
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    restored = restore_cache_archive(output / "jev_response_cache.zip", args.cache_dir)
    if restored:
        print(f"Restored {restored} raw Jev responses from tracked archive", flush=True)
    estimates, probabilities, audit = classify_occupations(
        spanish, us, args.cache_dir, workers=args.workers, offline=args.offline,
        progress=lambda message: print(message, flush=True),
    )
    direct, direct_probabilities, direct_audit = classify_direct_exposure(
        spanish, args.cache_dir, workers=args.workers, offline=args.offline,
        progress=lambda message: print(message, flush=True),
    )
    estimates = estimates.merge(direct, on="cno4", how="left", validate="one_to_one")
    if len(estimates) != len(direct) or estimates.observed_exposure_jev_direct.isna().any():
        raise ValueError("Missing direct exposure for a Spanish occupation")
    audit.extend(direct_audit)
    audit.sort(key=lambda item: (item["cno4"], item["request_sha256"]))
    # Do not overwrite a previous successful run's inputs when API inference fails.
    spanish[["CNO4", "occupation_title", "cno_structured_text_es"]].to_csv(output / "spanish_inputs.csv", index=False)
    us.to_csv(output / "us_catalogue.csv", index=False)
    write_json(output / "questions.json", questions)
    estimates["jev_model"] = MODEL
    estimates["jev_rubric_version"] = RUBRIC_VERSION
    estimates["jev_direct_rubric_version"] = DIRECT_EXPOSURE_RUBRIC_VERSION
    estimates.to_csv(output / "occupation_estimates.csv", index=False)
    probabilities.to_csv(output / "occupation_probabilities.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    direct_probabilities.to_csv(output / "direct_score_probabilities.csv", index=False)
    write_json(output / "request_audit.json", audit)
    us_benchmark = None
    if args.benchmark_us_direct:
        us_items = [
            (str(row.occ_code), {"occupation": {
                "country": "United States", "soc_code": str(row.occ_code),
                "title": str(row.title), "description_and_tasks": str(row.onet_description),
            }}) for row in us.itertuples(index=False)
        ]
        us_scores, us_score_probabilities, us_audit = classify_direct_exposure_states(
            us_items, args.cache_dir, workers=args.workers, offline=args.offline,
            progress=lambda message: print(message, flush=True),
        )
        us_validation = us[["occ_code", "title", "observed_exposure"]].merge(
            us_scores.rename(columns={"cno4": "occ_code"}), on="occ_code",
            how="left", validate="one_to_one",
        )
        if len(us_validation) != len(us) or us_validation.observed_exposure_jev_direct.isna().any():
            raise ValueError("Incomplete US direct Score benchmark")
        us_validation.to_csv(output / "us_direct_validation.csv", index=False)
        us_score_probabilities.rename(columns={"cno4": "occ_code"}).to_csv(
            output / "us_direct_score_probabilities.csv", index=False,
        )
        write_json(output / "us_direct_request_audit.json", us_audit)
        # Named paper benchmarks are context in the prompt: exclude them for
        # the main validity check to avoid testing examples the model saw.
        anchor_titles = {
            "Computer Programmers", "Data Entry Keyers", "Cooks", "Motorcycle Mechanics",
            "Lifeguards", "Bartenders", "Dishwashers", "Dressing Room Attendants",
        }
        holdout = us_validation[~us_validation.title.isin(anchor_titles)]
        residual = holdout.observed_exposure_jev_direct - holdout.observed_exposure
        us_benchmark = {
            "us_occupations": len(us_validation), "holdout_occupations": len(holdout),
            "excluded_prompt_anchor_titles": sorted(anchor_titles),
            "holdout_spearman": float(holdout.observed_exposure_jev_direct.corr(holdout.observed_exposure, method="spearman")),
            "holdout_mae": float(residual.abs().mean()),
            "holdout_mean_error": float(residual.mean()),
            "holdout_true_zero_count": int(holdout.observed_exposure.eq(0).sum()),
            "requests": len(us_audit),
            "new_input_tokens": sum(item["input_tokens"] for item in us_audit if not item["cached"]),
        }
        write_json(output / "us_direct_validation_summary.json", us_benchmark)
    all_audit = audit + (us_audit if args.benchmark_us_direct else [])
    archive_cache(args.cache_dir, [item["request_sha256"] for item in all_audit], output / "jev_response_cache.zip")
    merged = None
    if args.merge_sepe:
        print("Merging Jev classifications into SEPE...", flush=True)
        merged = merge_sepe_file(args.sepe_path, args.sepe_output, estimates)
        merged.update({"source": str(args.sepe_path.relative_to(PROJECT_ROOT)) if args.sepe_path.is_relative_to(PROJECT_ROOT) else args.sepe_path.name,
                       "source_sha256": file_sha256(args.sepe_path), "output_sha256": file_sha256(args.sepe_output)})
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL, "rubric_version": RUBRIC_VERSION,
        "method": "exhaustive_soc_major_group_conditional_choice",
        "joint_probability": "P(SOC group | CNO4) * P(US occupation | SOC group, CNO4)",
        "nearest": "Exposure of maximum joint-probability US occupation; lexicographic SOC tie break",
        "weighted": "Sum over ALL US occupations of joint probability times observed_exposure",
        "direct": "Jev Score expected level divided by 9; no US exposure or occupation match enters the prompt",
        "direct_rubric_version": DIRECT_EXPOSURE_RUBRIC_VERSION,
        "direct_sources": {"paper": ANTHROPIC_PAPER_URL, "appendix": ANTHROPIC_APPENDIX_URL},
        "category_count": len(us), "spanish_count": len(estimates), "full_cno_count": total_spanish,
        "partial_run": partial, "questions_sha256": fingerprint(questions),
        "source_files": source_manifest,
        "tier_sources": {"video": VIDEO_URL, "summary": TALK_SUMMARY_URL,
                         "sections_seconds": [768, 1071, 2791, 3396, 3658]},
        "input_language": "Spanish CNO descriptions, English O*NET descriptions and rubric",
        "requests": len(audit), "cached_requests": sum(item["cached"] for item in audit),
        "input_tokens": sum(item["input_tokens"] for item in audit),
        "output_tokens": sum(item["output_tokens"] for item in audit),
        "new_input_tokens": sum(item["input_tokens"] for item in audit if not item["cached"]),
        "tier_counts": {str(key): int(value) for key, value in estimates.jev_tier.value_counts().sort_index().items()},
        "review_counts": {name: int(estimates[name].sum()) for name in ("jev_match_review", "jev_tier_review", "jev_direct_review", "jev_no_military_category")},
        "sepe_merge": merged,
        "us_direct_benchmark": us_benchmark,
        "artifacts": {path.name: file_sha256(path) for path in sorted(output.iterdir()) if path.is_file() and path.name != "manifest.json"},
    }
    write_json(output / "manifest.json", manifest)
    print(f"Done: {len(estimates)} occupations; tiers {manifest['tier_counts']}; {manifest['input_tokens']:,} input tokens", flush=True)


if __name__ == "__main__":
    main()
