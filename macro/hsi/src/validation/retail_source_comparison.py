"""Compare published YoY values; matching known months cannot certify unknown ones."""
import numpy as np
import pandas as pd


def compare_retail_source(nbs, candidate, source_id):
    for frame in (nbs, candidate):
        if frame.observation_period.duplicated().any():
            raise ValueError('Duplicate observation periods must be resolved at the source')
        if not frame.unit.eq('percent').all():
            raise ValueError('Only directly published nominal YoY percentages are comparable')
        values = frame.value.dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError('Non-finite observations')
    joined = nbs[['observation_period', 'value']].merge(
        candidate[['observation_period', 'value']], how='outer', on='observation_period',
        suffixes=('_nbs', '_source')).sort_values('observation_period')
    joined.insert(0, 'source_id', source_id)
    joined['difference_pp'] = joined.value_source - joined.value_nbs
    both = joined.value_nbs.notna() & joined.value_source.notna()
    exact = both & joined.difference_pp.abs().le(1e-8)
    joined['comparison_status'] = np.select(
        [exact, both, joined.value_nbs.notna(), joined.value_source.notna()],
        ['match', 'mismatch', 'nbs_only', 'source_only'], default='both_missing')
    window = joined.observation_period.between('2012-07', nbs.observation_period.max())
    source_valid = candidate.loc[candidate.value.notna(), 'observation_period']
    summary = dict(source_id=source_id, unit='percent', source_rows=len(candidate),
        source_valid_rows=len(source_valid), source_missing_values=int(candidate.value.isna().sum()),
        source_duplicates=0, first_date=source_valid.min(), last_date=source_valid.max(),
        nbs_valid_rows=int(nbs.value.notna().sum()), paired_months=int(both.sum()),
        exact_matches=int(exact.sum()), mismatches=int((both & ~exact).sum()),
        max_abs_difference_pp=joined.loc[both, 'difference_pp'].abs().max(),
        nbs_known_months_uncovered=int((joined.comparison_status == 'nbs_only').sum()),
        known_window_months_covered=int((both & window).sum()),
        fills_missing_window_months=int(((joined.comparison_status == 'source_only') & window).sum()),
        all_overlap_matched=bool(both.any() and exact.sum() == both.sum()),
        all_nbs_known_months_matched=bool(exact.sum() == nbs.value.notna().sum() and both.any()))
    return joined, summary
