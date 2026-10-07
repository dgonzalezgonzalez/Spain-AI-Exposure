"""Reconstruct nearest and assignment-weighted exposures from frozen embeddings."""
from pathlib import Path
import numpy as np
import pandas as pd


def replay(inputs: Path, panel: Path, destination: Path) -> Path:
    with np.load(inputs / 'cosine_embeddings.npz', allow_pickle=False) as archive:
        us, spanish = archive['us'], archive['spanish']
        us_codes, cno4 = archive['us_codes'], archive['cno4']
    exposure = pd.read_csv(inputs / 'anthropic_job_exposure_onet.csv', dtype={'occ_code': str})
    values = exposure.set_index('occ_code').loc[us_codes, 'observed_exposure'].to_numpy()
    denominator = np.outer(np.linalg.norm(spanish, axis=1), np.linalg.norm(us, axis=1))
    similarities = np.divide(spanish @ us.T, denominator,
                             out=np.zeros_like(denominator), where=denominator != 0)
    nearest = np.argmax(similarities, axis=1)
    assigned = np.argmax(similarities, axis=0)
    weighted = values[nearest].copy()
    for index in range(len(cno4)):
        members = assigned == index
        if members.any() and similarities[index, members].sum() > 0:
            weighted[index] = np.average(values[members], weights=similarities[index, members])
    # Audited correction: Spanish military officers have no US military category;
    # the embedding's clerical match was a false friend from "Oficiales".
    nearest[cno4 == '0011'] = int(np.flatnonzero(us_codes == '33-1012')[0])
    weighted[cno4 == '0011'] = values[nearest[cno4 == '0011']]
    result = pd.DataFrame({'cno4': cno4, 'exposure_nearest': values[nearest],
                           'exposure_weighted': weighted, 'matched_soc': us_codes[nearest]})
    expected = pd.read_csv(panel, dtype={'cno4': str}).drop_duplicates('cno4').set_index('cno4')
    ordered = result.set_index('cno4').loc[expected.index]
    for name in ('exposure_nearest', 'exposure_weighted'):
        if not np.allclose(ordered[name], expected[name], atol=1e-12, rtol=0):
            error = np.max(np.abs(ordered[name] - expected[name]))
            raise ValueError(f'Frozen cosine replay differs in {name}: maximum error {error}')
    result.to_csv(destination, index=False)
    print(f'Replayed {len(result)} cosine occupation measures.', flush=True)
    return destination
