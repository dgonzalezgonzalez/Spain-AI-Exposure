"""Reproduce the manuscript from frozen inputs; run from any working directory."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'output/work'
STEPS = ('prepare', 'descriptives', 'estimates', 'sdid', 'jev', 'mediation', 'contdid', 'tuning', 'statistics', 'validate')


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_destination(root: Path, name: str) -> Path:
    destination = (root / name).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ValueError(f'Unsafe archive member: {name}')
    return destination


def atomic_copy(source: Path, target: Path) -> None:
    if target.exists() and sha256(source) == sha256(target):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.staging')
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def stage_inputs() -> None:
    for item in json.loads((ROOT / 'docs/stata_manifest.json').read_text(encoding='utf-8')):
        if sha256(ROOT / item['file']) != item['sha256']:
            raise ValueError(f'Vendored software checksum mismatch: {item["file"]}')
    raw = WORK / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'docs/input_manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        source = ROOT / item['file']
        if sha256(source) != item['sha256']:
            raise ValueError(f'Input checksum mismatch: {item["file"]}')
        target = raw / item['staged_name']
        if target.exists() and sha256(target) == item['uncompressed_sha256']:
            continue
        if source.suffix == '.gz':
            with gzip.open(source, 'rb') as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(source, target)
        if sha256(target) != item['uncompressed_sha256']:
            raise ValueError(f'Decompressed checksum mismatch: {target.name}')
    with ZipFile(raw / 'release-2026-06-26.zip') as archive:
        member = 'aei_claude_ai_2026-06-26.csv'
        target = raw / ('anthropic_' + member)
        expected_member = json.loads((ROOT / 'docs/archive_members.json').read_text())[member]
        if not target.exists() or sha256(target) != expected_member:
            with archive.open(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
    for source in (ROOT / 'code').iterdir():
        if source.is_file():
            atomic_copy(source, WORK / source.name)
    for source in (ROOT / 'code/lib').rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts:
            target = WORK / 'lib' / source.relative_to(ROOT / 'code/lib')
            atomic_copy(source, target)
    adoption = ROOT / 'data/input/spain_ai_adoption_timing_sources.csv'
    if adoption.exists():
        shutil.copy2(adoption, raw / adoption.name)
    for folder in ['logs', 'intermediate', 'uploads/figuresNtables', 'data/prepared']:
        (WORK / folder).mkdir(parents=True, exist_ok=True)


@contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path.remove(str(path))
        os.chdir(previous)


def run_python(name: str) -> None:
    # Plain Python exports of the original numbered notebooks need no kernel.
    import matplotlib
    matplotlib.use('Agg')
    path = WORK / name
    with working_directory(WORK):
        exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'),
             {'__name__': '__main__', '__file__': str(path)})


def executable(explicit: str | None, env_name: str, names: list[str]) -> str:
    requested = explicit or os.environ.get(env_name)
    if requested:
        found = shutil.which(requested) or (requested if Path(requested).is_file() else None)
        if found:
            return str(Path(found).resolve())
        raise FileNotFoundError(f'{env_name} executable does not exist: {requested}')
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    if os.name == 'nt':
        if env_name == 'STATA_EXE':
            for version in ['StataNow19', 'Stata19', 'Stata18', 'Stata17']:
                for name in ['StataMP-64.exe', 'StataSE-64.exe', 'StataBE-64.exe']:
                    candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / version / name
                    if candidate.is_file():
                        return str(candidate)
        else:
            programs = Path(os.environ['LOCALAPPDATA']) / 'Programs/R'
            candidates = sorted(programs.glob('R-*/bin/Rscript.exe'), reverse=True)
            if candidates:
                return str(candidates[0])
    raise FileNotFoundError(f'Cannot find executable; set {env_name} or pass its command-line option.')


def run_process(command: list[str], log_name: str, env: dict[str, str]) -> None:
    options = {}
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        options['startupinfo'] = startup
    with (WORK / 'logs' / log_name).open('w', encoding='utf-8') as log:
        subprocess.run(command, cwd=WORK, env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=True, **options)


def run_stata(args, jev: bool = False, mediation: bool = False, sdid: bool = False) -> None:
    stata = executable(args.stata_exe, 'STATA_EXE', ['stata-mp', 'stata-se', 'stata', 'StataMP-64.exe'])
    env = os.environ.copy()
    # Development switches cannot silently shorten a production replication.
    for name in list(env):
        if name.startswith('V1_'):
            del env[name]
    env['V1_SDID_REPS'] = str(args.sdid_reps)
    if jev:
        env['V1_JEV_OD_ONLY'] = '1'
    label = 'mediation' if mediation else 'jev' if jev else 'sdid' if sdid else 'estimates'
    script = WORK / {'mediation': 'job_tier_mediation.do', 'jev': '03_Jev.do',
                     'sdid': '03_SDID.do', 'estimates': '03_Estimates.do'}[label]
    wrapper = WORK / f'run_{label}.do'
    vendor = (ROOT / 'code/vendor/stata').as_posix()
    panel = (WORK / 'data/prepared/est_total_cno4_jev.csv').as_posix()
    intermediate = (WORK / 'intermediate').as_posix()
    invocation = f'do "{script.as_posix()}"'
    if mediation:
        invocation += f' "{panel}" "{intermediate}" "{vendor}"'
    marker = WORK / 'logs' / f'{label}.success'
    marker.unlink(missing_ok=True)
    wrapper.write_text(f'clear all\nset more off\nsysdir set PLUS "{vendor}"\n'
                       f'{invocation}\nfile open completed using "{marker.as_posix()}", write replace\n'
                       'file write completed "success"\nfile close completed\nexit, clear\n', encoding='utf-8')
    command = [stata, '/e', 'do', str(wrapper)] if os.name == 'nt' else [stata, '-b', 'do', str(wrapper)]
    run_process(command, marker.stem + '_process.log', env)
    if not marker.exists():
        raise RuntimeError(f'Stata stopped before completing {marker.stem}; inspect output/work/logs/.')


def run_r(args) -> None:
    rscript = executable(args.rscript, 'R_SCRIPT', ['Rscript', 'Rscript.exe'])
    env = os.environ.copy()
    env['CONTDID_BITERS'] = str(args.contdid_reps)
    if not env.get('REPLICATION_R_LIB'):
        env['REPLICATION_R_LIB'] = str(ROOT / '.r_libs')
    for locale_name in ['LC_ALL', 'LC_CTYPE', 'LANG']:
        env.pop(locale_name, None)
    for name in ['V1_CONTDID_SMOKE', 'V1_CONTDID_NO2021_ONLY']:
        env.pop(name, None)
    run_process([rscript, '--vanilla', str(WORK / '04_Estimates_contDID_v1.R')], 'contdid_process.log', env)


def prepare_jev() -> None:
    with working_directory(WORK):
        from lib.jev_replay import replay
        from lib.cosine_replay import replay as replay_cosine
        from lib.jev_robustness import prepare_jev_panel
        replay_cosine(ROOT / 'data/input', WORK / 'data/prepared/est_total_cno4.csv',
                      WORK / 'data/prepared/cosine_occupation_exposure.csv')
        estimates = replay(ROOT / 'data/input/jev', WORK / 'data/prepared/jev_occupation_estimates.csv',
                           WORK / 'cache/jev')
        prepare_jev_panel(WORK / 'data/prepared/est_total_cno4.csv',
                          estimates,
                          WORK / 'data/prepared/est_total_cno4_jev.csv')


def finish_outputs() -> None:
    import matplotlib
    import matplotlib.pyplot as plt
    with working_directory(WORK):
        from lib.jev_robustness import build_jev_robustness_outputs, build_exposure_correlation_matrix
        from lib.job_tiers import build_job_tier_outputs
        from lib.job_tier_mediation import render_table
        from lib.terminology import normalize_latex_terminology
        final = WORK / 'uploads/figuresNtables'
        tables = WORK / 'intermediate'
        # These appendix figures were authored in a separate Python process.
        # Isolate their original defaults from the numbered notebook's style.
        with plt.rc_context(matplotlib.rcParamsDefault):
            build_jev_robustness_outputs(tables, final)
            build_exposure_correlation_matrix(WORK, WORK / 'data/prepared/est_total_cno4.csv',
                                             WORK / 'data/prepared/jev_occupation_estimates.csv', final)
            build_job_tier_outputs(tables, final)
        (final / 'job_tier_mediation_v1.tex').write_text(
            render_table(tables / 'job_tier_mediation_estimates.csv', tables / 'job_tier_mediation_pretrends.csv'),
            encoding='utf-8')
        for source in tables.glob('*.tex'):
            shutil.copy2(source, final / source.name)
        generated = ROOT / 'output/generated'
        generated.mkdir(parents=True, exist_ok=True)
        items = json.loads((ROOT / 'docs/paper_outputs.json').read_text(encoding='utf-8'))
        for item in items:
            source = final / item['file']
            if not source.exists():
                raise FileNotFoundError(f'Missing manuscript output: {item["file"]}')
            destination = generated / source.name
            if source.suffix == '.tex':
                destination.write_text(normalize_latex_terminology(source.read_text(encoding='utf-8')), encoding='utf-8')
            else:
                shutil.copy2(source, destination)
        allowed = {item['file'] for item in items}
        unexpected = {p.name for p in generated.iterdir()} - allowed
        if unexpected:
            raise ValueError(f'Unexpected publication outputs: {sorted(unexpected)}')


def validate_outputs() -> None:
    from PIL import Image, ImageChops, ImageStat
    targets = json.loads((ROOT / 'docs/reference_manifest.json').read_text(encoding='utf-8'))
    for target in targets:
        path = ROOT / 'output/reference' / target['file']
        if sha256(path) != target['sha256']:
            raise ValueError(f'Independent paper reference checksum differs: {target["file"]}')
    results = []
    items = json.loads((ROOT / 'docs/paper_outputs.json').read_text(encoding='utf-8'))
    for item in items:
        generated, reference = ROOT / 'output/generated' / item['file'], ROOT / 'output/reference' / item['file']
        if not generated.exists() or not reference.exists():
            results.append({**item, 'status': 'missing', 'detail': 'generated or paper reference missing'})
            continue
        if sha256(generated) == sha256(reference):
            results.append({**item, 'status': 'exact', 'detail': 'identical SHA-256'})
        elif generated.suffix == '.tex':
            observed, expected = table_cells(generated), table_cells(reference)
            same = observed == expected
            results.append({**item, 'status': 'numbers_match' if same else 'numbers_differ',
                            'detail': 'printed numeric cells and significance stars compared',
                            **({} if same else {'generated_cells': observed, 'reference_cells': expected})})
        else:
            with Image.open(generated) as a, Image.open(reference) as b:
                a, b = a.convert('RGB'), b.convert('RGB')
                size_same = a.size == b.size
                delta = ImageChops.difference(a, b) if size_same else None
                difference = ImageStat.Stat(delta) if delta else None
                error = sum(difference.mean) / 3 / 255 if difference else None
                maximum = max(value[1] for value in difference.extrema) if difference else None
                # Floating-point estimates can move a few antialiased pixels by
                # one RGB level. This bound cannot admit shifted lines or labels.
                rounding_only = error is not None and error <= 1e-8 and maximum <= 1
            status = 'pixels_match' if error == 0 else 'pixels_match_with_rounding' if rounding_only else 'visual_review'
            results.append({**item, 'status': status,
                            'detail': f'mean pixel error={error}; maximum channel difference={maximum}; same dimensions={size_same}'})
    destination = ROOT / 'output/validation.json'
    destination.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    failures = [r for r in results if r['status'] in {'missing', 'numbers_differ', 'visual_review'}]
    print(f'{len(items)} manuscript assets checked; {len(failures)} unresolved discrepancies.', flush=True)
    if failures:
        raise ValueError('Paper comparison failed: ' + ', '.join(r['file'] for r in failures))


def table_cells(path: Path) -> list[str]:
    """Compare published cells, excluding comments and layout command arguments."""
    source = re.sub(r'(?<!\\)%[^\n]*', '', path.read_text(encoding='utf-8'))
    blocks = re.findall(r'\\begin\{(?:tabular\*?|longtable)\}.*?\\end\{(?:tabular\*?|longtable)\}', source, re.S)
    text = '\n'.join(blocks)
    text = re.sub(r'\\(?:cmidrule|cline)(?:\([^)]*\))?\{[^}]*\}', '', text)
    text = re.sub(r'\\(?:multicolumn|multirow)\{[^}]*\}\{[^}]*\}', '', text)
    text = re.sub(r'\\(?:hspace|vspace|addlinespace)(?:\[[^]]*\]|\{[^}]*\})', '', text)
    cells = []
    for row in re.split(r'\\\\', text):
        if '&' not in row:
            continue
        parts = row.split('&')
        if re.fullmatch(r'\s*\d{4}\s*', parts[0]):
            cells.append(str(float(parts[0])))
        for cell in parts[1:]:
            # Thousands separators in tables are commas or thin spaces.
            cell = cell.replace(r'\,', '').replace(r'\!', '')
            for token in re.findall(r'(?<![A-Za-z])[-−]?\d+(?:,\d{3})*(?:\.\d+)?|\*+', cell):
                cells.append(token if '*' in token else str(float(token.replace(',', '').replace('−', '-')) or 0.0))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step', choices=['all', *STEPS], default='all')
    parser.add_argument('--stata-exe')
    parser.add_argument('--rscript')
    parser.add_argument('--sdid-reps', type=int, default=500)
    parser.add_argument('--contdid-reps', type=int, default=1000)
    parser.add_argument('--check-inputs', action='store_true')
    args = parser.parse_args()
    if min(args.sdid_reps, args.contdid_reps) < 2:
        parser.error('At least two repetitions are required to estimate a variance.')
    stage_inputs()
    if args.check_inputs:
        print('All frozen input checksums verified.')
        return 0
    selected = STEPS if args.step == 'all' else (args.step,)
    timing_file = ROOT / 'output' / ('run_environment.json' if args.step == 'all' else f'run_{args.step}.json')
    timing = {'platform': platform.platform(), 'python': sys.version, 'sdid_reps': args.sdid_reps,
              'contdid_reps': args.contdid_reps, 'steps': []}
    for step in selected:
        print(f'Starting {step}', flush=True)
        start = time.monotonic()
        try:
            if step == 'prepare':
                run_python('01_Preparation_v1.py'); prepare_jev()
            elif step == 'descriptives':
                run_python('02_Descriptives_v1.py')
            elif step == 'estimates':
                run_stata(args)
            elif step == 'sdid':
                run_stata(args, sdid=True)
            elif step == 'jev':
                run_stata(args, jev=True)
            elif step == 'mediation':
                run_stata(args, mediation=True)
            elif step == 'contdid':
                run_r(args)
            elif step == 'tuning':
                run_python('05_Output_tuning_v1.py'); finish_outputs()
            elif step == 'statistics':
                with working_directory(WORK):
                    from lib.intext_statistics import build
                    build(WORK, ROOT / 'output/intext_statistics.json')
            elif step == 'validate':
                validate_outputs()
        except Exception as error:
            timing['steps'].append({'step': step, 'seconds': time.monotonic()-start, 'status': 'failed', 'error': str(error)})
            timing_file.write_text(json.dumps(timing, indent=2)+'\n', encoding='utf-8')
            raise
        timing['steps'].append({'step': step, 'seconds': time.monotonic()-start, 'status': 'completed'})
        timing_file.write_text(json.dumps(timing, indent=2)+'\n', encoding='utf-8')
        print(f'Completed {step} in {time.monotonic()-start:.1f}s', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
