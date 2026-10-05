"""Run exposure checks and joint job-tier DiD using frozen Jev or TEV classifications."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "analysis/paper_replication"
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT))
from lib.jev_robustness import prepare_jev_panel, build_jev_robustness_outputs, build_exposure_correlation_matrix
from lib.job_tiers import build_job_tier_outputs
from src.jev import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-family", choices=("jev", "tev"), default="jev")
    parser.add_argument("--stata-exe", type=Path, default=Path(r"C:\Program Files\StataNow19\StataMP-64.exe"))
    args = parser.parse_args()
    family = args.model_family
    data = ROOT / f"data/processed/{family}"
    if family == "tev":
        manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
        if manifest["partial_run"] or manifest["spanish_count"] != 502:
            raise ValueError("A complete TEV occupation run is required")
    run = PACKAGE / "runtime" / f"{family}_checks_{uuid.uuid4().hex[:12]}"
    prepared = run / "data/prepared"
    prepared.mkdir(parents=True)
    baseline = PACKAGE / "runtime/data/prepared/est_total_cno4.csv"
    shutil.copy2(baseline, prepared / baseline.name)
    model_panel = prepared / f"est_total_cno4_{family}.csv"
    prepare_jev_panel(baseline, data / "occupation_estimates.csv", model_panel, model_family=family)
    source = PACKAGE / "03_Estimates_TWFE_SDID_HonestDID_v1.do"
    dofile = run / source.name
    shutil.copy2(source, dofile)
    shutil.copytree(PACKAGE / "lib", run / "lib")
    env = os.environ.copy()
    env.update(V1_JEV_OD_ONLY="1", V1_OCCUPATION_MODEL=family)
    print(f"Running baseline, three exposure variants, and joint tier DiD in {run}", flush=True)
    subprocess.run([str(args.stata_exe), "/e", "do", str(dofile)], cwd=run, env=env, check=True)
    estimates = run / "intermediate"
    output = PACKAGE / "figuresNtables" if family == "jev" else PACKAGE / "figuresNtables/tev"
    build_jev_robustness_outputs(estimates, output, model_family=family)
    build_job_tier_outputs(estimates, output, model_family=family)
    build_exposure_correlation_matrix(ROOT, model_panel, data / "occupation_estimates.csv", output, model_family=family)
    # Freeze the exact estimator inputs used by the publication renderer.
    snapshot = data / "paper_joint_checks"
    if snapshot.exists():
        shutil.move(str(snapshot), str(run / "previous_snapshot"))
    snapshot.mkdir()
    for pattern in ("twfe_phase_*.csv", "twfe_pretrend_*.csv", "twfe_event_*.csv", "twfe_tier_*.csv"):
        for path in sorted(estimates.glob(pattern)):
            shutil.copy2(path, snapshot / path.name)
    shutil.copy2(source, snapshot / "source_occupation_checks.do")
    shutil.copy2(PACKAGE / "lib/job_tiers.do", snapshot / "source_job_tiers.do")
    write_json(snapshot / "manifest.json", {
        "model_family": family,
        "occupation_estimates_sha256": hashlib.sha256((data / "occupation_estimates.csv").read_bytes()).hexdigest(),
        "baseline_panel_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
        "stata_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "tier_source_sha256": hashlib.sha256((PACKAGE / "lib/job_tiers.do").read_bytes()).hexdigest(),
        "source_snapshots": ["source_occupation_checks.do", "source_job_tiers.do"],
        "tier_treatment": "joint tier 1 and tier 2 indicators; tier 3 omitted; preferred CNO1-by-month FE",
        "estimator_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(snapshot.glob("*.csv"))},
    })
    subprocess.run([sys.executable, str(ROOT / "scripts/build_model_appendices.py"),
                    "--model-family", family], cwd=ROOT, check=True)
    print(f"Completed {family} exposure and tier checks: {output}", flush=True)


if __name__ == "__main__":
    main()
