"""Run Nico's V1 paper replication package from the repository pipeline."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterator
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "analysis" / "paper_replication"
RUNTIME_ROOT = PACKAGE_ROOT / "runtime"
STEPS = ("prepare", "descriptives", "estimates", "contdid", "tuning")
SOURCE_FILES = (
    "01_Preparation_v1.ipynb",
    "02_Descriptives_v1.ipynb",
    "03_Estimates_TWFE_SDID_HonestDID_v1.do",
    "04_Estimates_contDID_v1.R",
    "05_Output_tuning_v1.ipynb",
    "descriptive.tex",
    "estimates_results_report_v1.tex",
)


class ReplicationError(RuntimeError):
    """Raised when the replication package cannot be staged or run."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Nico's V1 replication package from the shared repository inputs."
    )
    parser.add_argument(
        "--step",
        choices=[*STEPS, "all"],
        default="all",
        help="Production step to run; all follows the package's five-step order.",
    )
    parser.add_argument("--stata-exe", default=None, help="Path to StataMP for the TWFE/SDID step.")
    parser.add_argument("--rscript", default=None, help="Path to Rscript for the ContDID step.")
    parser.add_argument(
        "--sdid-reps",
        type=int,
        default=500,
        help="Synthetic-DiD placebo repetitions; use a small value only for a smoke test.",
    )
    parser.add_argument(
        "--contdid-reps",
        type=int,
        default=1000,
        help="ContDID multiplier-bootstrap repetitions; use a small value only for a smoke test.",
    )
    parser.add_argument(
        "--refresh-backcasts",
        action="store_true",
        help="Refresh the age and province backcast caches from SEPE June-over-May rates.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the staged inputs and commands without changing runtime outputs.",
    )
    return parser.parse_args()


def _find_first(label: str, candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _required_input(label: str, candidates: list[Path]) -> Path:
    source = _find_first(label, candidates)
    if source is None:
        locations = "\n".join(f"  - {path}" for path in candidates)
        raise ReplicationError(f"Missing {label}. Checked:\n{locations}")
    return source


def _materialize(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _copy_sources_to_runtime() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_FILES:
        shutil.copy2(PACKAGE_ROOT / name, RUNTIME_ROOT / name)
    shutil.copytree(PACKAGE_ROOT / "lib", RUNTIME_ROOT / "lib", dirs_exist_ok=True)


def _stage_inputs(step: str) -> dict[str, Path]:
    raw = RUNTIME_ROOT / "data" / "raw"
    assets = PACKAGE_ROOT / "data_sources"
    sources = {
        "sepe": _required_input(
            "SEPE CNO4 monthly output",
            [
                ROOT / "data" / "processed" / "sepe_cno4_monthly_ai_exposure.csv",
                ROOT / "data" / "raw" / "sepe_cno4_monthly_ai_exposure.csv",
            ],
        ),
        "epa_gender": _required_input(
            "INE EPA table 65134",
            [
                ROOT / "data" / "raw" / "ine" / "epa_65134_cno2_weights.csv",
                assets / "ine_epa_ocupados_65134.csv",
            ],
        ),
        "anthropic_exposure": _required_input(
            "Anthropic occupation exposure data",
            [ROOT / "data" / "raw" / "anthropic" / "job_exposure.csv", assets / "anthropic_job_exposure_onet.csv"],
        ),
        "cno_titles": _required_input(
            "English CNO4 title lookup",
            [assets / "cno4_english_titles.csv"],
        ),
    }
    _materialize(sources["sepe"], raw / "sepe_cno4_monthly_ai_exposure.csv")
    _materialize(sources["epa_gender"], raw / "ine_epa_ocupados_65134.csv")
    _materialize(sources["anthropic_exposure"], raw / "anthropic_job_exposure_onet.csv")
    _materialize(sources["cno_titles"], raw / "cno4_english_titles.csv")

    if step in {"descriptives", "all"}:
        sources["epa_unemployed"] = _required_input(
            "INE EPA unemployed table 65218",
            [assets / "ine_epa_parados_65218.csv", ROOT / "data" / "raw" / "ine_epa_parados_65218.csv"],
        )
        sources["cno_pdf"] = _required_input(
            "INE CNO explanatory PDF",
            [ROOT / "data" / "raw" / "ine" / "cno11_notas.pdf"],
        )
        release = _find_first(
            "Anthropic Economic Index release",
            [ROOT / "data" / "raw" / "anthropic" / "release-2026-06-26.zip"],
        )
        if release is None:
            raise ReplicationError(
                "Missing Anthropic Economic Index release ZIP. Run the existing country-usage figure step first "
                "or place release-2026-06-26.zip under data/raw/anthropic/."
            )
        sources["release"] = release
        _materialize(sources["epa_unemployed"], raw / "ine_epa_parados_65218.csv")
        _materialize(sources["cno_pdf"], raw / "cno11_notas.pdf")
        member = "aei_claude_ai_2026-06-26.csv"
        extracted = raw / member
        if not extracted.exists():
            with ZipFile(release) as archive:
                if member not in archive.namelist():
                    raise ReplicationError(f"Release ZIP does not contain {member}.")
                with archive.open(member) as source, extracted.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
        sources["aei_csv"] = extracted
    return sources


@contextmanager
def _in_runtime() -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(RUNTIME_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)


def _run_notebook(filename: str) -> None:
    path = RUNTIME_ROOT / filename
    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__", "__file__": str(path), "display": print}
    if str(RUNTIME_ROOT) not in sys.path:
        sys.path.insert(0, str(RUNTIME_ROOT))
    with _in_runtime():
        for index, cell in enumerate(notebook.get("cells", []), start=1):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            try:
                exec(compile(source, f"{path} [cell {index}]", "exec"), namespace, namespace)
            except Exception as error:
                raise ReplicationError(f"{filename} failed in cell {index}: {error}") from error


def _resolve_executable(explicit: str | None, env_name: str, names: list[str], defaults: list[Path]) -> Path:
    candidates = [Path(explicit)] if explicit else []
    if os.environ.get(env_name):
        candidates.append(Path(os.environ[env_name]))
    candidates.extend(Path(found) for name in names if (found := shutil.which(name)))
    candidates.extend(defaults)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise ReplicationError(f"Executable not found. Pass the relevant option or set {env_name}.")


def _run_stata(stata_exe: str | None, reps: int) -> None:
    stata = _resolve_executable(
        stata_exe,
        "STATA_EXE",
        ["StataMP-64.exe", "StataMP.exe", "StataSE-64.exe", "StataBE-64.exe"],
        [
            Path(r"C:\Program Files\StataNow19\StataMP-64.exe"),
            Path(r"C:\Program Files\Stata19\StataMP-64.exe"),
            Path(r"C:\Program Files\Stata18\StataMP-64.exe"),
        ],
    )
    env = os.environ.copy()
    env["PATH"] = f"{stata.parent}{os.pathsep}{env.get('PATH', '')}"
    env["V1_SDID_REPS"] = str(reps)
    command = [str(stata), "/e", "do", str(RUNTIME_ROOT / "03_Estimates_TWFE_SDID_HonestDID_v1.do")]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=RUNTIME_ROOT, env=env, check=True)


def _run_r(rscript: str | None, reps: int) -> None:
    executable = _resolve_executable(rscript, "R_SCRIPT", ["Rscript.exe", "Rscript"], [])
    env = os.environ.copy()
    env["CONTDID_BITERS"] = str(reps)
    command = [str(executable), str(RUNTIME_ROOT / "04_Estimates_contDID_v1.R")]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=RUNTIME_ROOT, env=env, check=True)


def run_replication(args: argparse.Namespace) -> None:
    selected = STEPS if args.step == "all" else (args.step,)
    if args.sdid_reps < 1 or args.contdid_reps < 1:
        raise ReplicationError("Bootstrap repetition counts must be positive.")
    sources = {
        "SEPE output": ROOT / "data" / "processed" / "sepe_cno4_monthly_ai_exposure.csv",
        "EPA 65134": ROOT / "data" / "raw" / "ine" / "epa_65134_cno2_weights.csv",
        "paper source": PACKAGE_ROOT,
    }
    if args.dry_run:
        for label, path in sources.items():
            print(f"{label}: {path} ({'present' if path.exists() else 'missing'})")
        print(f"Steps: {' -> '.join(selected)}")
        print(f"Runtime: {RUNTIME_ROOT}")
        return

    _copy_sources_to_runtime()
    _stage_inputs(args.step)
    if args.refresh_backcasts:
        os.environ["REFRESH_SEPE_MAY2024_AGE"] = "1"
        os.environ["REFRESH_SEPE_MAY2024_PROVINCE"] = "1"

    for step in selected:
        if step == "prepare":
            _run_notebook("01_Preparation_v1.ipynb")
        elif step == "descriptives":
            _run_notebook("02_Descriptives_v1.ipynb")
        elif step == "estimates":
            _run_stata(args.stata_exe, args.sdid_reps)
        elif step == "contdid":
            _run_r(args.rscript, args.contdid_reps)
        elif step == "tuning":
            _run_notebook("05_Output_tuning_v1.ipynb")
    print(f"Replication outputs written to {RUNTIME_ROOT}")


def main() -> int:
    try:
        run_replication(parse_args())
    except ReplicationError as error:
        print(f"Replication package error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
