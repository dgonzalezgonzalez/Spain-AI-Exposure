"""Independent within-estimator coefficient checks for the added robustness test."""
from pathlib import Path
from io import StringIO
import re

import numpy as np
import pandas as pd


def within_fit(frame: pd.DataFrame, outcome: str, dose: str, family_month: bool,
               no2021: bool = False, event: bool = False) -> tuple[np.ndarray, list[int], int]:
    frame = frame.loc[frame.event_time.between(-21, 40)].copy()
    if no2021:
        frame = frame.loc[frame.event_time >= -10]
    frame = frame.dropna(subset=[outcome, dose, 'cno4'])
    frame['time_group'] = frame['period'].astype(str)
    if family_month:
        frame['time_group'] = frame.cno4.str[0] + ':' + frame.time_group
    # Match reghdfe's recursive removal of singleton fixed-effect groups.
    while True:
        keep = (frame.groupby('cno4').cno4.transform('size') > 1) & (
            frame.groupby('time_group').time_group.transform('size') > 1)
        if keep.all():
            break
        frame = frame.loc[keep]
    events = sorted(int(k) for k in frame.event_time.unique() if k != -1) if event else []
    if event:
        x = np.column_stack([frame[dose].to_numpy() * frame.event_time.eq(k).to_numpy() for k in events])
    else:
        x = np.column_stack([frame[dose].to_numpy() * frame.event_time.between(a, b).to_numpy()
                             for a, b in [(0, 24), (25, 40)]])
    values = np.column_stack([frame[outcome].to_numpy(), x])
    groups = [pd.factorize(frame.cno4)[0], pd.factorize(frame.time_group)[0]]
    for _ in range(1000):
        previous = values.copy()
        for group in groups:
            values -= pd.DataFrame(values).groupby(group).transform('mean').to_numpy()
        if np.max(np.abs(values - previous)) < 1e-11:
            break
    else:
        raise ValueError('Independent fixed-effect absorption did not converge')
    beta = np.linalg.lstsq(values[:, 1:], values[:, 0], rcond=None)[0]
    return beta, events, len(frame)


def validate(work: Path) -> dict:
    work = Path(work)
    maximum = 0.0
    nchecks = 0
    for mapping in ['baseline', 'edgecases']:
        filename = 'est_total_cno4.csv' if mapping == 'baseline' else 'est_total_cno4_edgecases.csv'
        panel = pd.read_csv(work / 'data/prepared' / filename, dtype={'cno4': str})
        panel['event_time'] = panel.ym_stata - (2022 - 1960) * 12 - 10
        dose = 'exposure_10pp' if mapping == 'baseline' else 'exposure_edgecases_10pp'
        if mapping == 'edgecases' and (panel[dose].isna().any() or panel.cno4.nunique() != 502):
            raise ValueError('The alternative exposure does not cover all occupations')
        for outcome in ['ln_parados', 'ln_contratos']:
            for suffix in ['benchmark', 'cno1_month', 'cno1_month_no2021']:
                spec = f'edge_{mapping}_{suffix}'
                beta, _, nobs = within_fit(panel, outcome, dose, suffix != 'benchmark', suffix.endswith('no2021'))
                fitted = pd.read_csv(work / 'intermediate' / f'twfe_phase_{spec}_{outcome}.csv').set_index('phase')
                expected = fitted.loc[['adjustment', 'later'], 'estimate'].to_numpy()
                error = float(np.max(np.abs(beta - expected)))
                if error > 1e-7 or not fitted.observations.eq(nobs).all():
                    raise ValueError(f'Independent phase replication differs: {spec}/{outcome}, error={error}, N={nobs}')
                maximum = max(maximum, error); nchecks += 2
            if mapping == 'edgecases':
                beta, events, nobs = within_fit(panel, outcome, dose, True, event=True)
                fitted = pd.read_csv(work / 'intermediate' / f'twfe_event_edge_edgecases_cno1_month_{outcome}.csv').set_index('event_time')
                error = float(np.max(np.abs(beta - fitted.loc[events, 'estimate'].to_numpy())))
                if error > 1e-7 or not fitted.observations.eq(nobs).all():
                    raise ValueError('Independent event-study replication differs')
                maximum = max(maximum, error); nchecks += len(events)
    return {'independently_checked_coefficients': nchecks, 'maximum_absolute_coefficient_error': maximum,
            'complete_occupation_coverage': 502, 'standard_errors': 'Stata clustered by CNO4; baseline also compared with retained O.D.7'}


def validate_preserved_tiers(root: Path, work: Path) -> dict:
    """Compare retained pooled-tier paths with the pre-edit Prism vector source."""
    text = (root / 'docs/reference/appendix_oh_prism_20261019.tex').read_text(encoding='utf-8')
    blocks = re.findall(r'\\pgfplotstableread\{(.*?)\}\\tierdata', text, re.S)
    if len(blocks) != 2:
        raise ValueError('Expected two independent Prism tier paths')
    maximum = 0.0
    for block, outcome in zip(blocks, ['ln_parados', 'ln_contratos']):
        target = pd.read_csv(StringIO(block.strip()), sep=r'\s+').set_index('event_time')
        actual = pd.read_csv(work / 'intermediate' / f'twfe_tier_event_jev_tiers_cno1_month_{outcome}.csv').set_index('event_time')
        if set(actual.control_group) != {'tiers_2_3'} or set(actual.tier) != {1}:
            raise ValueError('Pooled-tier comparison changed')
        columns = ['estimate', 'ci_low', 'ci_high']
        error = float(np.max(np.abs(actual.loc[target.index, columns].to_numpy() - target[columns].to_numpy())))
        if error > 1e-7:
            raise ValueError('Pooled-tier event path differs from the pre-edit manuscript')
        maximum = max(maximum, error)
    return {'source': 'Pre-edit Prism inline vector paths, exported 19 October 2026',
            'paths': 2, 'maximum_absolute_difference': maximum,
            'note': 'Legacy PNG targets use an earlier tier comparison and are not substituted for these source paths.'}


def validate_matrix(work: Path) -> dict:
    from scipy.stats import spearmanr
    frame = pd.read_csv(work / 'rendered/exposure_measure_matrix_inputs_v1.csv', dtype={'cno4': str}).set_index('cno4')
    verified = pd.read_csv(work / 'data/prepared/occupation_crosswalk_edgecases.csv', dtype={'cno4': str}).set_index('cno4')
    if frame.shape != (502, 8) or not np.allclose(frame.exposure_edgecases, verified.loc[frame.index, 'exposure_edgecases'], atol=0, rtol=0):
        raise ValueError('The matrix does not contain the complete verified-match measure')
    rows = pd.read_csv(work / 'rendered/exposure_measure_spearman_correlations_long_v1.csv')
    pairs = rows.loc[rows.measure_a.ne(rows.measure_b)]
    observed_pairs = {frozenset((r.measure_a, r.measure_b)) for r in pairs.itertuples()}
    expected_pairs = {frozenset((a, b)) for i, a in enumerate(frame.columns) for b in frame.columns[:i]}
    if len(pairs) != 28 or observed_pairs != expected_pairs:
        raise ValueError('The matrix must contain every distinct pair exactly once')
    maximum = 0.0
    for row in pairs.itertuples():
        if row.measure_a == row.measure_b:
            continue
        values = frame[[row.measure_a, row.measure_b]].dropna()
        rho = float(spearmanr(values.iloc[:, 0], values.iloc[:, 1]).statistic)
        error = abs(rho - row.spearman_rho)
        if error > 1e-12 or len(values) != row.occupations:
            raise ValueError('Independent Spearman calculation differs')
        maximum = max(maximum, error)
    return {'measures': 8, 'occupation_rows': 502, 'independent_pairs': 28,
            'maximum_absolute_correlation_error': maximum}
