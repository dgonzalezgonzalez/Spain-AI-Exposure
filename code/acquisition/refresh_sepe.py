"""Optional retrieval of the public SEPE reports; not used by the frozen replication."""
import argparse
from pathlib import Path
import sys
import time
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.sepe import (make_sepe_session, discover_sepe_report_links,
                              fetch_cached_report, parse_sepe_report_html,
                              sepe_long_to_compact_wide)


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=root / 'data/work/acquisition')
    parser.add_argument('--cno4', nargs='+', help='Optional occupation subset for a retrieval check.')
    args = parser.parse_args()
    occupations = pd.read_csv(root / 'data/input/jev/spanish_inputs.csv', dtype={'CNO4': str})
    if args.cno4:
        wanted = {c.zfill(4) for c in args.cno4}
        if wanted - set(occupations.CNO4): parser.error('Unknown CNO4 code')
        occupations = occupations[occupations.CNO4.isin(wanted)]
    args.cache.mkdir(parents=True, exist_ok=True)
    with make_sepe_session() as session:
        links = discover_sepe_report_links(session, occupations)
        for link in links:
            if not '2021-01' <= link.period <= '2026-03': continue
            target = args.cache / 'parsed' / f'{link.cno4}_{link.period}.csv'
            if target.exists(): continue
            html = fetch_cached_report(session, args.cache, link)
            rows = parse_sepe_report_html(html, link.url)
            if not rows: raise ValueError(f'No observations: {link.url}')
            target.parent.mkdir(exist_ok=True)
            sepe_long_to_compact_wide(pd.DataFrame(rows)).to_csv(target, index=False)
            print(link.cno4, link.period, flush=True)
            time.sleep(0.25)
    print('Current provider reports cached. Compare against the frozen release before replacing inputs.')


if __name__ == '__main__': main()
