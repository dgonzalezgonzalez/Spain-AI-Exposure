"""Re-extract the frozen EPA weights from checksum-identified public archives."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import gzip
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def extract(archive_dir: Path, destination: Path) -> None:
    sources = json.loads((ROOT / 'docs/epa_microdata_sources.json').read_text(encoding='utf-8'))
    frames = []
    for source in sources:
        name = source['url'].rsplit('/', 1)[1]
        archive_path = archive_dir / source['quarter'] / name
        with archive_path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != source['archive_sha256']:
            raise ValueError(f'Archive vintage differs: {archive_path}')
        with ZipFile(archive_path) as archive, archive.open(source['member']) as stream:
            frame = pd.read_csv(stream, sep='\t', usecols=['AOI', 'FACTOREL'], dtype='string')
        frame = frame.loc[frame['AOI'].str.zfill(2).isin(['05', '06'])].copy()
        if len(frame) != source['retained_records']:
            raise ValueError(f'Unemployment record count differs: {source["quarter"]}')
        frame.insert(0, 'quarter', source['quarter'])
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
        compressed.write(combined.to_csv(index=False).encode('utf-8'))
    frozen = ROOT / 'data/input/epa_unemployment_microdata_weights.csv.gz'
    with frozen.open('rb') as stream: expected = hashlib.file_digest(stream, 'sha256').hexdigest()
    with destination.open('rb') as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError('Extracted EPA weights differ from the frozen paper vintage.')
    print(f'Reproduced {len(combined):,} public survey weights; SHA-256 {actual}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-dir', type=Path, required=True,
                        help='Archives organized as QUARTER/filename.zip; URLs are in docs/epa_microdata_sources.json.')
    args = parser.parse_args()
    extract(args.archive_dir, ROOT / 'data/work/source_checks/epa_unemployment_microdata_weights.csv.gz')
