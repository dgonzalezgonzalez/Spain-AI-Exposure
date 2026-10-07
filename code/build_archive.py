"""Build the complete portable release ZIP, excluding installed/runtime files."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def build() -> Path:
    names = ['README.md', 'AGENTS.md', 'LICENSE', '.gitignore', '.gitattributes', 'master.py',
             'requirements.txt', 'requirements-lock.txt', 'renv.lock',
             'output/tables/.gitkeep', 'output/figures/.gitkeep']
    files = [ROOT / name for name in names]
    for folder in ['code', 'data/input', 'docs', 'tests']:
        files.extend(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    target = ROOT / 'dist/latest_code.zip'
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(files):
            if not file.resolve().is_relative_to(ROOT): raise ValueError(f'File escapes package: {file}')
            name = file.relative_to(ROOT).as_posix()
            info = ZipInfo('latest_code/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, file.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    with target.open('rb') as stream: checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    target.with_suffix('.zip.sha256').write_text(checksum + '  latest_code.zip\n', encoding='ascii')
    print(f'{target}: {len(files)} files, {target.stat().st_size:,} bytes; SHA-256 {checksum}')
    return target


if __name__ == '__main__': build()
