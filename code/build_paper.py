"""Compile root main.tex and publish paper/main.pdf after successful checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(pdflatex: str = 'pdflatex', bibtex: str = 'bibtex') -> Path:
    engines = [shutil.which(pdflatex), shutil.which(bibtex)]
    if not all(engines):
        raise RuntimeError('Install a TeX distribution with pdflatex and bibtex, or supply their paths.')
    directory = ROOT / 'logs/paper_build'
    directory.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['BIBINPUTS'] = str(ROOT) + os.pathsep + env.get('BIBINPUTS', '')
    command = [engines[0], '-interaction=nonstopmode', '-halt-on-error',
               '-no-shell-escape', '-output-directory', str(directory), 'main.tex']
    log_path = ROOT / 'logs/paper_compile.log'
    with log_path.open('w', encoding='utf-8') as log:
        def run(args: list[str], cwd: Path) -> None:
            completed = subprocess.run(args, cwd=cwd, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, timeout=600)
            if completed.returncode:
                raise RuntimeError(f'Paper compilation failed; inspect {log_path}.')

        run(command, ROOT)
        run([engines[1], 'main'], directory)
        previous = None
        for _ in range(6):
            run(command, ROOT)
            current = hashlib.sha256((directory / 'main.aux').read_bytes()).hexdigest()
            if current == previous:
                break
            previous = current
        else:
            raise RuntimeError('Paper cross-references did not stabilize within six passes.')
    tex_log = (directory / 'main.log').read_text(encoding='utf-8', errors='replace')
    if any(message in tex_log for message in ['There were undefined',
                                             'There were multiply-defined labels',
                                             'Label(s) may have changed']):
        raise RuntimeError(f'Unresolved references or labels; inspect {directory / "main.log"}.')
    source = directory / 'main.pdf'
    if not source.is_file():
        raise RuntimeError('Compiler did not produce a PDF.')
    destination = ROOT / 'paper/main.pdf'
    shutil.copy2(source, destination)
    (ROOT / 'logs/paper_build.json').write_text(json.dumps({
        'entry_point': 'main.tex', 'pdf': 'paper/main.pdf', 'engines': engines,
        'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        'references_resolved': True,
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Compiled {destination}', flush=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdflatex', default='pdflatex')
    parser.add_argument('--bibtex', default='bibtex')
    args = parser.parse_args()
    build(args.pdflatex, args.bibtex)
