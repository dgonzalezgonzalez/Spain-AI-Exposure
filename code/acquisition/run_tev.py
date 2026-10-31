"""Acquire all local TEV decisions once per occupation; resume or replay exact caches."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'code'))
from lib.jev import (archive_cache, restore_cache_archive, choice_probabilities, direct_exposure_record,
                     direct_exposure_state, validate_catalogue, write_json)
from lib.jev_questions import direct_exposure_question, tier_question, MATCH_INSTRUCTIONS
from lib.tev import (API, MODEL, TevClient, pack_requests, runtime_provenance, string_question)

PIN = ROOT / 'code/acquisition/tev-runtime.json'
OUT = ROOT / 'data/input/tev'
CACHE = ROOT / 'data/work/cache/tev'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def server(pin):
    executable = Path(shutil.which('ollama') or '')
    if not executable.is_file() or digest(executable) != pin['ollama_sha256']:
        raise RuntimeError('Install the pinned Ollama binary; re-audit any update.')
    for name, expected in pin['runner_binary_sha256'].items():
        if digest(executable.parent / 'lib/ollama' / name) != expected:
            raise RuntimeError(f'Inference binary changed: {name}')
    try:
        requests.get(API + '/api/version', timeout=1)
    except requests.RequestException:
        pass
    else:
        raise RuntimeError('Isolated inference port occupied; leave that process untouched.')
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / 'server.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), 'serve'], env={**os.environ, **pin['environment']},
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Isolated Ollama failed; inspect data/work/cache/tev/server.log')
                try:
                    requests.get(API + '/api/version', timeout=1).raise_for_status()
                    break
                except requests.RequestException:
                    time.sleep(.2)
            else:
                raise RuntimeError('Ollama startup timed out')
            tags = requests.get(API + '/api/tags', timeout=15).json()['models']
            models = {m['name']: m['digest'] for m in tags}
            if any(models.get(pin[k]) != pin[k.replace('model', 'digest')] for k in ['base_model']):
                raise RuntimeError('Pinned TEV base weights missing or changed')
            if models.get(MODEL) != pin['model_digest']:
                raise RuntimeError('Create the exact pinned alias with code/acquisition/tev.Modelfile')
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def sources():
    inputs = ROOT / 'data/input'
    spanish = pd.read_csv(inputs / 'jev/spanish_inputs.csv', dtype={'CNO4': str})
    catalogue = pd.read_csv(inputs / 'jev/us_catalogue.csv', dtype={'occ_code': str})
    validate_catalogue(catalogue)
    baseline = pd.read_csv(inputs / 'spanish_occupation_matches_cosine_nearest.csv', dtype={'CNO4': str}).set_index('CNO4')
    screens = {}
    with ZipFile(inputs / 'edgecases/frozen_requests.zip') as archive:
        for name in archive.namelist():
            if name.startswith('jev/'):
                payload = json.loads(archive.read(name))['payload']
                screens[payload['state']['occupation']['cno4']] = payload
    with np.load(inputs / 'cosine_embeddings.npz', allow_pickle=False) as a:
        vectors, us = a['spanish'], a['us']
        similarities = (vectors @ us.T) / np.outer(np.linalg.norm(vectors, axis=1), np.linalg.norm(us, axis=1))
        # Stable rank and frozen US order preserve deterministic ties.
        candidates = {str(code): [str(x) for x in a['us_codes'][np.argsort(-similarities[i], kind='stable')[:24]]]
                      for i, code in enumerate(a['cno4'])}
    if len(spanish) != 502 or len(catalogue) != 756 or set(screens) != set(spanish.CNO4):
        raise ValueError('Expected all 502 Spanish and 756 US occupations and original screen states')
    evidence = spanish.set_index('CNO4').cno_structured_text_es
    for code, screen in screens.items():
        if (screen['state']['occupation']['definition_tasks_examples_exclusions'] != evidence.loc[code] or
                screen['state']['proposed_us_match']['code'] != baseline.loc[code, 'anthropic_occ_code']):
            raise ValueError(f'Screen evidence or baseline differs from the frozen inputs: {code}')
    return spanish, catalogue, baseline, screens, candidates


def payloads_for(row, screens, catalogue, candidates):
    code = str(row['CNO4'])
    # Direct score sees no proposed match, candidate schema or earlier answer.
    semantic = pack_requests(direct_exposure_state(row), {
        'direct_exposure': direct_exposure_question(), 'tier': string_question(tier_question())})
    screen = screens[code]
    subset = catalogue.set_index('occ_code').loc[candidates[code]]
    criteria = {code: json.dumps({'title': item.title, 'description': item.onet_description}, ensure_ascii=False)
                for code, item in subset.iterrows()}
    questions = {'match': {'type': 'choice', 'instructions': MATCH_INSTRUCTIONS +
                 ' Select the best available substantive equivalent or closest occupational proxy from this fixed cosine shortlist.',
                 'criteria': criteria}, **screen['questions']}
    matching = pack_requests(screen['state'], questions)
    return semantic + matching



def run(args, provenance):
    spanish, catalogue, baseline, screens, candidates = sources()
    if args.offline:
        candidates = json.loads((OUT / 'shortlists.json').read_text(encoding='utf-8'))
        if set(candidates) != set(spanish.CNO4) or any(len(v) != 24 or len(set(v)) != 24 for v in candidates.values()):
            raise ValueError('Frozen shortlists must contain 24 unique candidates for each occupation')
    selected = spanish.sort_values('CNO4')
    if args.audit:
        # Largest real shortlist request in the frozen 502-occupation design.
        selected = selected.loc[selected.CNO4.eq('6110')]
    if args.limit:
        selected = selected.head(args.limit)
    client = TevClient(CACHE, provenance, offline=args.offline)
    all_audit, records, probabilities, scores, crosswalk = [], [], [], [], []
    us = catalogue.set_index('occ_code')
    started = time.monotonic()
    for row in selected.to_dict('records'):
        code = str(row['CNO4'])
        payloads = payloads_for(row, screens, catalogue, candidates)
        if args.audit:
            # Exercise each question type plus the largest real matching schema.
            probes = payloads
            previous_path = OUT / 'repeatability_audit.json'
            previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
            result = []
            for number, payload in enumerate(probes):
                recorded = next((p for p in previous.get('probes', []) if p['request'] == payload and
                                 p['exact_answers'] and previous.get('runtime') == provenance), None)
                if recorded:
                    result.append(recorded)
                    print(f'Cold repeatability {number+1}/{len(probes)}: recorded exact pair', flush=True)
                    continue
                a, _, _ = client.evaluate(payload, fresh=True)
                b, _, _ = client.evaluate(payload, fresh=True)
                result.append({'probe': number, 'question_ids': list(payload['questions']),
                               'exact_answers': a['answers'] == b['answers'], 'first': a, 'second': b,
                               'request': payload})
                write_json(OUT / 'repeatability_audit.json', {'runtime': provenance, 'probes': result})
                print(f'Cold repeatability {number+1}/{len(probes)}: {result[-1]["exact_answers"]}', flush=True)
                if not result[-1]['exact_answers']:
                    raise RuntimeError('Production-shape fresh probabilities differ; stop inference.')
            client.session.close()
            return
        answers = {}
        def obtain(payload, label):
            response, key, cached = client.evaluate(payload)
            answers.update(response['answers'])
            all_audit.append({'cno4': code, 'question_ids': list(payload['questions']),
                              'request_sha256': key, 'cached': cached, **response['usage']})
            print(f'{code} {label}: {len(payload["questions"])} questions ({"cache" if cached else "fresh"})', flush=True)
        for i, payload in enumerate(payloads, 1):
            obtain(payload, f'{i}/{len(payloads)}')
        flagged = float(answers['wrong_match']['noul']) >= .5
        match = choice_probabilities(answers['match'], candidates[code])
        winner = min(match, key=lambda k: (-match[k], k))
        automatic = winner if flagged else str(baseline.loc[code, 'anthropic_occ_code'])
        # Conditional shortlist probabilities; excluded categories are outside support.
        p = {str(k): match.get(str(k), 0.) for k in us.index}
        tier = choice_probabilities(answers['tier'], ('1', '2', '3'))
        direct, score = direct_exposure_record(code, answers['direct_exposure'])
        record = {'cno4': code, 'occupation_title': row['occupation_title'],
                  'jev_matched_occ_code': winner, 'jev_matched_title': us.at[winner, 'title'],
                  'observed_exposure_jev_nearest': float(us.at[winner, 'observed_exposure']),
                  'observed_exposure_jev_weighted': sum(p[k] * float(us.at[k, 'observed_exposure']) for k in sorted(p)),
                  'jev_match_probability': p[winner], 'jev_tier': int(min(tier, key=lambda k: (-tier[k], k))),
                  **{f'jev_tier_{k}_probability': v for k, v in tier.items()}, **direct,
                  'decision_model': MODEL, 'compatibility_columns': 'jev_* names retained for unchanged estimator interfaces'}
        edge = {'cno4': code, 'spanish_title': row['occupation_title'],
                'baseline_code': str(baseline.loc[code, 'anthropic_occ_code']),
                'tev_wrong_match_probability': float(answers['wrong_match']['noul']),
                'tev_heterogeneous_probability': float(answers['heterogeneous']['noul']),
                'flagged': flagged, 'automatic_code': automatic, 'automatic_title': us.at[automatic, 'title'],
                'final_code': automatic, 'final_title': us.at[automatic, 'title'],
                'exposure_edgecases': float(us.at[automatic, 'observed_exposure']), 'manual_override': False}
        records.append(record); probabilities.append({'cno4': code, **p}); scores.append(score); crosswalk.append(edge)
        write_json(CACHE / 'completed' / (code + '.json'), {'estimate': record, 'crosswalk': edge})
        print(f'COMPLETE {len(records)}/{len(selected)}: {code}; {time.monotonic()-started:.0f}s', flush=True)
    client.session.close()
    destination = getattr(args, 'destination', None) or (OUT if not args.limit else ROOT / 'data/work/tev_pilot')
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in [('occupation_estimates.csv', records), ('direct_score_probabilities.csv', scores),
                       ('occupation_crosswalk_automatic.csv', crosswalk)]:
        pd.DataFrame(data).to_csv(destination / name, index=False)
    pd.DataFrame(probabilities).to_csv(destination / 'occupation_probabilities.csv.gz', index=False,
                                     compression={'method': 'gzip', 'mtime': 0})
    write_json(destination / 'request_audit.json', all_audit)
    write_json(destination / 'shortlists.json', {str(r['cno4']): candidates[str(r['cno4'])] for r in records})
    write_json(destination / 'runtime.json', provenance)
    archive_cache(CACHE, [r['request_sha256'] for r in all_audit], destination / 'tev_response_cache.zip')
    write_json(destination / 'manifest.json', {'model': MODEL, 'partial_run': bool(args.limit),
               'occupations': len(records), 'categories': len(us), 'elapsed_seconds': time.monotonic()-started,
               'shortlist_size': 24, 'probabilities': 'conditional on cosine shortlist; excluded categories outside support',
               'method': 'fixed cosine top-24 shortlist; conditional probabilities; shared TEV match for flagged corrections',
               'artifacts': {p.name: digest(p) for p in destination.iterdir() if p.is_file() and p.name != 'manifest.json'}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    reference = OUT / 'runtime.json'
    if args.offline:
        restore_cache_archive(OUT / 'tev_response_cache.zip', CACHE)
        run(args, json.loads(reference.read_text(encoding='utf-8')))
    else:
        pin = json.loads(PIN.read_text(encoding='utf-8'))
        with server(pin):
            provenance = {**runtime_provenance(), 'pinned_binaries': pin, 'question_design': 'cosine_top24_v1',
                          'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in [
                              ROOT/'data/input/jev/spanish_inputs.csv', ROOT/'data/input/jev/us_catalogue.csv',
                              ROOT/'data/input/cosine_embeddings.npz', ROOT/'data/input/edgecases/frozen_requests.zip']}}
            if reference.exists() and json.loads(reference.read_text(encoding='utf-8')) != provenance:
                write_json(ROOT / 'data/work/runtime_mismatch.json', provenance)
                raise RuntimeError('Runtime differs from saved inference; use a new experimental branch.')
            write_json(reference, provenance)
            if not args.audit:
                audit = json.loads((OUT / 'repeatability_audit.json').read_text(encoding='utf-8'))
                if audit['runtime'] != provenance or len(audit['probes']) != 2 or not all(p['exact_answers'] for p in audit['probes']):
                    raise RuntimeError('Run the production-shape cold repeatability audit first.')
            run(args, provenance)


if __name__ == '__main__':
    main()
