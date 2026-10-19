"""Optional refresh of archived required-choice requests; never called by master.py."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Explicitly permit paid/live GPT-OSS inference.')
    parser.add_argument('--url', default='http://localhost:11434/api/chat')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/work/edgecase_refresh.zip')
    args = parser.parse_args()
    if not args.refresh:
        parser.error('Default replication is offline; use master.py --step edgecases. Live calls require --refresh.')
    source = ROOT / 'data/input/edgecases/frozen_requests.zip'
    if args.output.resolve() == source.resolve():
        parser.error('A refresh must not overwrite frozen publication inputs.')
    key = os.environ['OLLAMA_API_KEY']
    with ZipFile(source) as archive:
        detector = {name: archive.read(name) for name in archive.namelist() if name.startswith('jev/')}
        payloads = [(name, json.loads(archive.read(name))['payload'])
                    for name in archive.namelist() if name.startswith('gpt/')]
    cache = ROOT / 'data/work/edgecase_refresh_cache'
    cache.mkdir(parents=True, exist_ok=True)
    def obtain(item):
        name, payload = item
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        path = cache / (digest + '.json')
        if path.exists():
            return name, path.read_bytes()
        request = urllib.request.Request(args.url, json.dumps(payload).encode(),
                                         {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = json.load(response)
        answer = json.loads(raw['message']['content'])
        state = json.loads(payload['messages'][1]['content'].split('\nINPUT:\n', 1)[1])
        if answer['code'] not in {row['code'] for row in state['candidates']} or type(answer['approximate']) is not bool:
            raise ValueError(f'Invalid required-choice response: {name}')
        record = json.dumps({'provider': 'ollama', 'payload': payload, 'response': raw}, ensure_ascii=False).encode()
        path.write_bytes(record)
        return name, record
    with ThreadPoolExecutor(max_workers=2) as pool:
        refreshed = dict(pool.map(obtain, payloads))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, 'w', ZIP_DEFLATED) as archive:
        for name, value in sorted({**detector, **refreshed}.items()):
            archive.writestr(name, value)
    print(f'Saved {len(refreshed)} refreshed verifications; reused all {len(detector)} detector responses.')


if __name__ == '__main__':
    main()
