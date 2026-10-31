"""Independent checks for changed-model results; retain the Jev targets unchanged."""
from pathlib import Path

import numpy as np
import pandas as pd

from .edgecase_validation import within_fit, validate as validate_edges, validate_matrix


def validate_mediation(work: Path, panel: pd.DataFrame) -> dict:
    fitted = pd.read_csv(work / 'intermediate/job_tier_mediation_estimates.csv')
    maximum = 0.
    for outcome in ['ln_parados', 'ln_contratos']:
        for specification in ['baseline', 'phase_controls', 'month_fe']:
            frame = panel.loc[panel.event_time.between(-21, 40)].dropna(subset=[outcome, 'exposure_10pp']).copy()
            frame['family_month'] = frame.cno4.str[0] + ':' + frame.period.astype(str)
            frame['tier_month'] = frame.jev_tier.astype(str) + ':' + frame.period.astype(str)
            labels = ['cno4', 'family_month'] + (['tier_month'] if specification == 'month_fe' else [])
            while True:
                keep = np.logical_and.reduce([frame.groupby(label).cno4.transform('size').gt(1) for label in labels])
                if keep.all():
                    break
                frame = frame.loc[keep]
            phases = [frame.event_time.between(0, 24), frame.event_time.between(25, 40)]
            columns = [frame.exposure_10pp.to_numpy() * phase.to_numpy() for phase in phases]
            if specification == 'phase_controls':
                columns += [(frame.jev_tier.eq(tier) & phase).astype(float).to_numpy()
                            for tier in [1, 2] for phase in phases]
            values = np.column_stack([frame[outcome].to_numpy(), *columns])
            groups = [pd.factorize(frame[label])[0] for label in labels]
            for _ in range(1000):
                previous = values.copy()
                for group in groups:
                    values -= pd.DataFrame(values).groupby(group).transform('mean').to_numpy()
                if np.max(np.abs(values - previous)) < 1e-11:
                    break
            else:
                raise ValueError('Independent mediation absorption did not converge')
            beta = np.linalg.lstsq(values[:, 1:], values[:, 0], rcond=None)[0][:2]
            target = fitted.loc[fitted.outcome.eq(outcome) & fitted.specification.eq(specification)].set_index('term')
            error = float(np.max(np.abs(beta - target.loc[['dose_adjustment', 'dose_later'], 'estimate'].to_numpy())))
            if error > 1e-7 or not target.observations.eq(len(frame)).all():
                raise ValueError(f'Independent mediation differs: {outcome}/{specification}: {error}')
            maximum = max(maximum, error)
    return {'count': 12, 'maximum_absolute_error': maximum}


def validate(work: Path) -> dict:
    checks = {'edgecases': validate_edges(work), 'matrix': validate_matrix(work)}
    panel = pd.read_csv(work / 'data/prepared/est_total_cno4_jev.csv', dtype={'cno4': str})
    if panel.cno4.nunique() != 502 or panel.jev_tier.isna().any() or not panel.jev_tier.isin([1, 2, 3]).all():
        raise ValueError('Incomplete TEV classifications in the estimation panel')
    panel['event_time'] = panel.ym_stata - (2022 - 1960) * 12 - 10
    maximum, coefficients = 0., 0
    for measure in ['nearest', 'weighted', 'direct', 'tiers']:
        frame = panel.copy()
        frame['dose_check'] = frame.jev_tier.eq(1).astype(float) if measure == 'tiers' else frame[f'exposure_jev_{measure}_10pp']
        for outcome in ['ln_parados', 'ln_contratos']:
            for suffix in ['benchmark', 'cno1_month', 'cno1_month_no2021']:
                beta, _, nobs = within_fit(frame, outcome, 'dose_check', suffix != 'benchmark', suffix.endswith('no2021'))
                prefix = 'twfe_tier_phase' if measure == 'tiers' else 'twfe_phase'
                fitted = pd.read_csv(work / 'intermediate' / f'{prefix}_jev_{measure}_{suffix}_{outcome}.csv').set_index('phase')
                error = float(np.max(np.abs(beta - fitted.loc[['adjustment', 'later'], 'estimate'].to_numpy())))
                if error > 1e-7 or not fitted.observations.eq(nobs).all():
                    raise ValueError(f'Independent TEV fit differs: {measure}/{outcome}/{suffix}: {error}')
                maximum = max(maximum, error)
                coefficients += 2
    checks['local_model_phase_coefficients'] = {'count': coefficients, 'maximum_absolute_error': maximum}
    checks['mediation_coefficients'] = validate_mediation(work, panel)
    return checks
