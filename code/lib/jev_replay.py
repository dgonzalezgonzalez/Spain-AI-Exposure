"""Reconstruct the paper's Jev measures from archived responses, without API calls."""
from pathlib import Path
import numpy as np
import pandas as pd

from .jev import (restore_cache_archive, classify_occupations,
                  classify_direct_exposure, validate_catalogue)
from .jev_questions import MODEL, RUBRIC_VERSION, DIRECT_EXPOSURE_RUBRIC_VERSION


def replay(inputs: Path, destination: Path, cache: Path) -> Path:
    restore_cache_archive(inputs / 'jev_response_cache.zip', cache)
    spanish = pd.read_csv(inputs / 'spanish_inputs.csv', dtype={'CNO4': str})
    catalogue = validate_catalogue(pd.read_csv(inputs / 'us_catalogue.csv', dtype={'occ_code': str}))
    estimates, probabilities, _ = classify_occupations(
        spanish, catalogue, cache, offline=True, progress=lambda _: None)
    direct, score_probabilities, _ = classify_direct_exposure(
        spanish, cache, offline=True, progress=lambda _: None)
    estimates = estimates.merge(direct, on='cno4', validate='one_to_one')
    estimates['jev_model'] = MODEL
    estimates['jev_rubric_version'] = RUBRIC_VERSION
    estimates['jev_direct_rubric_version'] = DIRECT_EXPOSURE_RUBRIC_VERSION
    expected = pd.read_csv(inputs / 'occupation_estimates.csv', dtype={'cno4': str})
    expected = expected.sort_values('cno4').reset_index(drop=True)
    estimates = estimates.sort_values('cno4').reset_index(drop=True)[expected.columns]
    for column in expected:
        if pd.api.types.is_numeric_dtype(expected[column]):
            if not np.allclose(estimates[column], expected[column], rtol=0, atol=1e-12, equal_nan=True):
                raise ValueError(f'Archived Jev replay differs in {column}')
        elif not estimates[column].fillna('').equals(expected[column].fillna('')):
            raise ValueError(f'Archived Jev replay differs in {column}')
    if not np.allclose(probabilities.drop(columns='cno4').sum(axis=1), 1, atol=1e-10):
        raise ValueError('Jev occupation probabilities do not sum to one')
    destination.parent.mkdir(parents=True, exist_ok=True)
    estimates.to_csv(destination, index=False)
    probabilities.to_csv(destination.with_name('jev_occupation_probabilities.csv.gz'), index=False,
                         compression={'method': 'gzip', 'mtime': 0})
    score_probabilities.to_csv(destination.with_name('jev_direct_score_probabilities.csv'), index=False)
    print(f'Replayed {len(estimates)} Jev occupations from archived responses.', flush=True)
    return destination
