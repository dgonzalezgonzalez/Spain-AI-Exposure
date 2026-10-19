"""Replay frozen Jev screening and required-choice GPT-OSS verification offline."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


# Reviewed residual mismatches only; codes must exist in the exposure catalogue.
MANUAL_OVERRIDES: dict[str, str] = {
    '0020': '33-9099',  # All enlisted armed forces: broad protective-service proxy, not merchant seamen.
    '2427': '19-1012',  # Enologists direct food-production science and research, rather than assisting it.
    '2473': '17-2072',  # Telecommunications engineering is not civil engineering.
    '2824': '21-1021',  # Independent social assessment/intervention, explicitly distinct from support assistants.
    '3125': '17-3023',  # Electromedical engineering technicians, rather than professional electrical engineers.
    '3135': '51-4051',  # Metal production/refining control, rather than chemical production.
    '5823': '39-9032',  # Tour-group leadership: recreation-activity proxy, rather than aircraft cabin service.
    '5825': '39-9032',  # Guided visitor activities: recreation-activity proxy, rather than seating/ticket duties.
    '5895': '39-3091',  # No exact exposed category: leisure-service proxy, rather than actuarial science.
    '6430': '33-9011',  # Capturing animals: animal-control proxy, rather than enforcing game-protection laws.
    '7705': '51-3092',  # Preparing/preserving food; the source explicitly excludes canning-machine operators.
    '7707': '51-3092',  # Food/beverage batch production, rather than industrial chemical processing.
    '9310': '35-2021',  # Kitchen food preparation, rather than industrial production assistance.
}


def parse_answer(response: dict) -> dict:
    text = response['message']['content'].strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    return json.loads(text)


def resolve_matches(baseline: pd.DataFrame, detector: dict, verifier: dict,
                    catalogue: pd.DataFrame, overrides: dict[str, str]) -> pd.DataFrame:
    """Apply the fixed gate, mandatory selections and explicit author corrections."""
    if not baseline.index.is_unique or not catalogue.index.is_unique:
        raise ValueError('Occupation codes must be unique')
    if set(detector) != set(baseline.index):
        raise ValueError('Detector must cover every Spanish occupation exactly once')
    flagged = {code for code, value in detector.items() if value >= 0.5}
    if set(verifier) != flagged:
        raise ValueError('Verifier coverage must equal the cached Jev gate')
    if not set(overrides) <= set(baseline.index):
        raise ValueError('Unknown Spanish override code')
    rows = []
    for code, source in baseline.sort_index().iterrows():
        answer = verifier.get(code)
        automatic = answer['code'] if answer else source['anthropic_occ_code']
        final = overrides.get(code, automatic)
        if automatic not in catalogue.index or final not in catalogue.index:
            raise ValueError(f'Missing or unknown selected O*NET code for {code}')
        value = float(catalogue.loc[final, 'observed_exposure'])
        if not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'Invalid exposure for {code}')
        rows.append({
            'cno4': code, 'spanish_title': source['spanish_title'],
            'baseline_code': source['anthropic_occ_code'],
            'jev_wrong_match_probability': detector[code],
            'flagged': code in flagged, 'automatic_code': automatic,
            'automatic_title': catalogue.loc[automatic, 'title'],
            'approximate': bool(answer['approximate']) if answer else False,
            'reason': answer['reason'] if answer else 'Cached Jev screen below 0.5; baseline retained.',
            'manual_override': code in overrides, 'final_code': final,
            'final_title': catalogue.loc[final, 'title'],
            'exposure_edgecases': value,
        })
    return pd.DataFrame(rows)


def replay(inputs: Path, prepared_panel: Path, destination: Path) -> pd.DataFrame:
    baseline = pd.read_csv(inputs / 'spanish_occupation_matches_cosine_nearest.csv',
                           dtype={'CNO4': str}).set_index('CNO4')
    spanish = pd.read_csv(inputs / 'jev/spanish_inputs.csv', dtype=str).set_index('CNO4')
    catalogue = pd.read_csv(inputs / 'jev/us_catalogue.csv', dtype={'occ_code': str}).set_index('occ_code')
    exposure = pd.read_csv(inputs / 'anthropic_job_exposure_onet.csv', dtype={'occ_code': str}).set_index('occ_code')
    if not np.allclose(catalogue.observed_exposure, exposure.loc[catalogue.index, 'observed_exposure'], atol=0, rtol=0):
        raise ValueError('Exposure catalogues differ')
    detector, verifier = {}, {}
    with ZipFile(inputs / 'edgecases/frozen_requests.zip') as archive:
        if archive.testzip() is not None:
            raise ValueError('Corrupt model-response archive')
        for name in archive.namelist():
            raw = json.loads(archive.read(name))
            payload, response = raw['payload'], raw['response']
            if name.startswith('jev/'):
                state = payload['state']
                code = state['occupation']['cno4']
                if code in detector:
                    raise ValueError('Duplicate detector response')
                if payload['model'] != 'jev-1.13.0':
                    raise ValueError('Unexpected detector model')
                detector[code] = float(response['answers']['wrong_match']['noul'])
                if not 0 <= detector[code] <= 1:
                    raise ValueError('Invalid detector probability')
                if state['proposed_us_match']['code'] != baseline.loc[code, 'anthropic_occ_code']:
                    raise ValueError('Detector baseline differs from the paper crosswalk')
            elif name.startswith('gpt/'):
                state = json.loads(payload['messages'][1]['content'].split('\nINPUT:\n', 1)[1])
                code = state['occupation']['cno4']
                answer = parse_answer(response)
                if code in verifier or answer['code'] not in {x['code'] for x in state['candidates']}:
                    raise ValueError('Duplicate verifier or selection outside supplied candidates')
                if type(answer['approximate']) is not bool:
                    raise ValueError('Malformed verifier proxy indicator')
                verifier[code] = answer
            else:
                raise ValueError('Unknown archive member')
            if state['occupation']['definition_tasks_examples_exclusions'] != spanish.loc[code, 'cno_structured_text_es']:
                raise ValueError('Archived occupation differs from frozen Spanish source')
    if len(detector) != 502 or len(verifier) != 216:
        raise ValueError('Expected the frozen 502-occupation screen and 216 reviews')
    crosswalk = resolve_matches(baseline, detector, verifier, catalogue, MANUAL_OVERRIDES)
    destination.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(destination / 'occupation_crosswalk_edgecases.csv', index=False)
    panel = pd.read_csv(prepared_panel, dtype={'cno4': str})
    panel = panel.merge(crosswalk[['cno4', 'exposure_edgecases']], on='cno4', how='left', validate='many_to_one')
    if panel.exposure_edgecases.isna().any() or panel.cno4.nunique() != 502:
        raise ValueError('Edge-case exposure must cover all 502 occupations without missing values')
    panel['exposure_edgecases_10pp'] = panel.exposure_edgecases / 0.10
    panel.to_csv(destination / 'est_total_cno4_edgecases.csv', index=False)
    print(f'Replayed {len(crosswalk)} complete edge-case exposures; {len(MANUAL_OVERRIDES)} author overrides.', flush=True)
    return crosswalk
