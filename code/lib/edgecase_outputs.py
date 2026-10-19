"""Two-panel robustness table and two event-study panels for complete matching."""
from pathlib import Path

import numpy as np
import pandas as pd

from .jev_robustness import _star, _event_y_limits, _render_event_file


def build_outputs(estimates_dir: Path, output_dir: Path) -> dict[str, Path]:
    estimates, output = Path(estimates_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    latex = [r'\begin{table}[H]', r'\centering',
             r'\caption{Robustness checks: verified occupational matches}',
             r'\label{tab:v1_edgecase_robustness}', r'\begin{threeparttable}',
             r'\scriptsize', r'\renewcommand{\arraystretch}{0.78}',
             r'\setlength{\tabcolsep}{3.0pt}', r'\resizebox{0.92\textwidth}{!}{%',
             r'\begin{tabular}{lcccccc}', r'\toprule',
             r'& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\',
             r'\cmidrule(lr){2-4}\cmidrule(lr){5-7}',
             r'& (1) & (2) & (3) & (4) & (5) & (6) \\', r'\midrule']
    records = []
    def p_format(value):
        return r'$<0.001$' if value < .001 else f'{value:.3f}'
    for mapping, label in [('baseline', 'Panel A. Baseline specification'),
                           ('edgecases', 'Panel B. Verified-match observed exposure')]:
        if mapping != 'baseline':
            latex.append(r'\addlinespace[5pt]')
        latex.append(r'\multicolumn{7}{l}{\textbf{' + label + r'}} \\')
        columns = []
        for outcome in ['ln_parados', 'ln_contratos']:
            for suffix in ['benchmark', 'cno1_month', 'cno1_month_no2021']:
                spec = f'edge_{mapping}_{suffix}'
                phase = pd.read_csv(estimates / f'twfe_phase_{spec}_{outcome}.csv').set_index('phase')
                pretrend = pd.read_csv(estimates / f'twfe_pretrend_{spec}_{outcome}.csv')
                p = pretrend.loc[pretrend.window.str.startswith('full_') & pretrend.test.eq('joint_equal_zero'), 'p_value']
                if set(phase.index) != {'adjustment', 'later'} or len(p) != 1:
                    raise ValueError('Incomplete phase or pre-treatment statistics')
                if not np.isfinite(phase[['estimate', 'se', 'equality_p']].to_numpy()).all():
                    raise ValueError('Nonfinite regression results')
                a, b = phase.loc['adjustment'], phase.loc['later']
                row = dict(mapping=mapping, specification=spec, outcome=outcome,
                           adjustment_estimate=a.estimate, adjustment_se=a.se,
                           later_estimate=b.estimate, later_se=b.se, pretrend_p=float(p.iloc[0]),
                           equality_p=a.equality_p, observations=int(a.observations), clusters=int(a.clusters))
                records.append(row); columns.append(row)
        for phase in ['adjustment', 'later']:
            latex.append(r'AI exposure $\times$ ' + phase + ' period & ' + ' & '.join(
                f'{r[phase+"_estimate"]:.3f}' + _star(r[phase+'_estimate'], r[phase+'_se'], r['clusters'])
                for r in columns) + r' \\')
            latex.append(' & ' + ' & '.join(f'({r[phase+"_se"]:.3f})' for r in columns) + r' \\')
        latex += [r'\addlinespace[2pt]', r'Pre-treatment joint-null $p$-value & ' +
                  ' & '.join(p_format(r['pretrend_p']) for r in columns) + r' \\',
                  r'$p$-value: equal phase effects & ' + ' & '.join(p_format(r['equality_p']) for r in columns) + r' \\',
                  'Observations & ' + ' & '.join(f'{r["observations"]:,}' for r in columns) + r' \\']
    latex += [r'\midrule', r'CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\',
              r'2021 included & Yes & Yes & No & Yes & Yes & No \\', r'\bottomrule', r'\end{tabular}', r'}',
              r'\begin{minipage}{0.92\textwidth}', r'\footnotesize',
              r'\emph{Notes:} Entries are marginal effects for the adjustment period (event times 0--24) and the later period (25--40), relative to all pre-treatment months. Panel A reproduces the baseline specification. Panel B uses the complete occupational crosswalk obtained from Jev screening, required-choice GPT-OSS 120B verification, and author corrections of clear residual mismatches. Each matched U.S. occupation retains its published Anthropic exposure value. Both panels cover all 502 CNO4 occupations. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Exposure is divided by 0.10. Standard errors are clustered by CNO4. The pre-treatment row tests the joint null that all available pre-treatment event-study coefficients equal zero: event times $-21$ through $-2$ when 2021 is included and $-10$ through $-2$ otherwise. Equality rows test whether the adjustment- and later-period effects are equal. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.',
              r'\end{minipage}', r'\end{threeparttable}', r'\end{table}']
    table = output / 'robustness_checks_edgecases_v1.tex'
    table.write_text('\n'.join(latex)+'\n', encoding='utf-8')
    pd.DataFrame(records).to_csv(output / 'robustness_checks_edgecases_v1.csv', index=False)
    paths = {'table': table}
    for name, outcome, step in [('unemployed', 'ln_parados', .025), ('contracts', 'ln_contratos', .05)]:
        source = estimates / f'twfe_event_edge_edgecases_cno1_month_{outcome}.csv'
        target = output / f'Robustness_{name}_edgecases.png'
        _render_event_file(source, target, _event_y_limits(source, step), step)
        paths[name] = target
    return paths
