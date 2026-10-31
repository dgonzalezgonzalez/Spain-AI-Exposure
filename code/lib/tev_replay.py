"""Replay the branch's local decisions, keeping legacy estimator column names."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

from .jev import restore_cache_archive


def replay(inputs: Path, destination: Path, cache: Path) -> Path:
    # Helpers also execute from data/work/lib after the master's staging step.
    root = inputs.resolve().parents[2]
    sys.path.insert(0, str(root / 'code/acquisition'))
    import run_tev
    manifest = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['partial_run'] or manifest['occupations'] != 502:
        raise ValueError('A complete TEV acquisition is required before analysis.')
    for name, expected in manifest['artifacts'].items():
        if run_tev.digest(inputs / name) != expected:
            raise ValueError(f'Frozen TEV input differs: {name}')
    restore_cache_archive(inputs / 'tev_response_cache.zip', cache)
    run_tev.CACHE = cache
    staged = root / 'data/work/replayed_tev'
    run_tev.run(SimpleNamespace(offline=True, limit=None, audit=False, destination=staged),
                json.loads((inputs / 'runtime.json').read_text(encoding='utf-8')))
    computed = pd.read_csv(staged / 'occupation_estimates.csv', dtype={'cno4': str})
    expected = pd.read_csv(inputs / 'occupation_estimates.csv', dtype={'cno4': str})
    pd.testing.assert_frame_equal(computed, expected, check_exact=False, atol=1e-12, rtol=0)
    p = pd.read_csv(staged / 'occupation_probabilities.csv.gz')
    if not np.allclose(p.drop(columns='cno4').sum(axis=1), 1, rtol=0, atol=1e-10):
        raise ValueError('TEV leaf probabilities do not sum to one')
    destination.parent.mkdir(parents=True, exist_ok=True)
    computed.to_csv(destination, index=False)
    return destination


def replay_edgecases(inputs: Path, prepared_panel: Path, destination: Path):
    data = inputs / 'tev'
    crosswalk = pd.read_csv(data / 'occupation_crosswalk_automatic.csv', dtype={'cno4': str})
    review = json.loads((data / 'author_review.json').read_text(encoding='utf-8'))
    if set(review['reviewed_codes']) != set(crosswalk.cno4) or len(crosswalk) != 502:
        raise ValueError('TEV crosswalk needs a complete source review of all 502 occupations.')
    catalogue = pd.read_csv(inputs / 'jev/us_catalogue.csv', dtype={'occ_code': str}).set_index('occ_code')
    overrides = review['overrides']
    if not set(overrides) <= set(crosswalk.cno4):
        raise ValueError('Unknown review override')
    for code, correction in overrides.items():
        if correction['code'] not in catalogue.index or not correction['reason'].strip():
            raise ValueError('Overrides need an available category and a duty-based rationale.')
        mask = crosswalk.cno4.eq(code)
        crosswalk.loc[mask, 'final_code'] = correction['code']
        crosswalk.loc[mask, 'manual_override'] = True
    crosswalk['final_title'] = crosswalk.final_code.map(catalogue.title)
    crosswalk['exposure_edgecases'] = crosswalk.final_code.map(catalogue.observed_exposure)
    if crosswalk.exposure_edgecases.isna().any():
        raise ValueError('Incomplete reviewed TEV crosswalk')
    destination.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(destination / 'occupation_crosswalk_edgecases.csv', index=False)
    panel = pd.read_csv(prepared_panel, dtype={'cno4': str})
    panel = panel.merge(crosswalk[['cno4', 'exposure_edgecases']], on='cno4', how='left', validate='many_to_one')
    if panel.exposure_edgecases.isna().any() or panel.cno4.nunique() != 502:
        raise ValueError('Reviewed TEV exposure must cover the full panel')
    panel['exposure_edgecases_10pp'] = panel.exposure_edgecases / .10
    panel.to_csv(destination / 'est_total_cno4_edgecases.csv', index=False)
    return crosswalk
