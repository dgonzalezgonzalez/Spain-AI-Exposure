"""Standalone sample facts and aggregate calibration stated in manuscript prose."""
from pathlib import Path
import json
import numpy as np
import pandas as pd


def build(work: Path, destination: Path) -> dict:
    panel = pd.read_csv(work / 'data/prepared/est_total_cno4.csv', dtype={'cno4': str})
    phases = pd.read_csv(work / 'intermediate/twfe_phase_preferred_cno1_month_ln_parados.csv').set_index('phase')
    event = panel['event_time_nov2022']
    post = panel.loc[event.between(0, 40)].copy()
    post['phase'] = np.where(post.event_time_nov2022 <= 24, 'adjustment', 'later')
    post['beta'] = post.phase.map(phases.estimate)
    post['counterfactual'] = post.parados * np.exp(-post.beta * post.exposure_10pp)
    post['gap'] = post.parados - post.counterfactual
    stats = {'occupations': int(panel.cno4.nunique()), 'months': int(panel.period.nunique()),
             'occupation_months': len(panel), 'zero_unemployment_cells': int(panel.parados.eq(0).sum()),
             'zero_contract_cells': int(panel.contratos.eq(0).sum()),
             'zero_unemployment_percent': 100*panel.parados.eq(0).mean(),
             'zero_contract_percent': 100*panel.contratos.eq(0).mean()}
    for phase in ('adjustment', 'later', 'full_post'):
        frame = post if phase == 'full_post' else post[post.phase == phase]
        stats[f'calibration_{phase}_percent'] = 100*frame.gap.sum()/frame.parados.sum()
    for phase in ('adjustment', 'later'):
        beta = float(phases.loc[phase, 'estimate'])
        stats[f'unemployment_{phase}_coefficient'] = beta
        stats[f'unemployment_{phase}_exact_percent'] = 100*np.expm1(beta)
    tiers = pd.read_csv(work / 'data/prepared/jev_occupation_estimates.csv')
    for tier, count in tiers.jev_tier.value_counts().items(): stats[f'tier_{int(tier)}_occupations'] = int(count)
    expected = {'occupations': (502,0), 'months': (63,0), 'occupation_months': (31626,0),
                'zero_unemployment_cells': (2,0), 'zero_contract_cells': (342,0),
                'calibration_adjustment_percent': (1.42,2), 'calibration_later_percent': (2.01,2),
                'calibration_full_post_percent': (1.64,2), 'tier_1_occupations': (232,0),
                'tier_2_occupations': (207,0), 'tier_3_occupations': (63,0)}
    checks = {key: {'paper': value, 'generated': stats[key], 'matches_printed_precision': bool(round(stats[key],digits)==value)}
              for key,(value,digits) in expected.items()}
    report = {'statistics':stats,'paper_checks':checks,
              'source': 'Main manuscript panel construction and aggregate-calibration appendix; frozen Jev tier assignment.',
              'interpretation': 'Calibration removes the estimated occupational exposure gradient; it does not identify an aggregate causal effect.'}
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not all(item['matches_printed_precision'] for item in checks.values()):
        raise ValueError('An in-text statistic differs from the manuscript; inspect logs/intext_statistics.json.')
    return report
