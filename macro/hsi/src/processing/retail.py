"""Explicit historical hypothesis; aggregate rates remain labelled as aggregates."""
from math import isfinite
import pandas as pd


def repeat_janfeb_combined(retail, combined):
    if retail.observation_period.duplicated().any() or combined.period_start.duplicated().any():
        raise ValueError('Duplicate retail or aggregate periods')
    if not retail.unit.eq('percent').all() or not combined.unit.eq('percent').all():
        raise ValueError('Retail and aggregate rates must both be percent')
    result = retail.copy(deep=True)
    result['value_kind'] = result.value.map(lambda v: 'missing' if pd.isna(v) else 'official_monthly_yoy')
    result['information_period_end'] = result.observation_period
    changes = []
    for row in combined.itertuples():
        start, end = pd.Period(row.period_start, 'M'), pd.Period(row.period_end, 'M')
        if start.month != 1 or end != start + 1 or not isfinite(row.retail_janfeb_combined_yoy):
            raise ValueError('A finite Jan-Feb combined rate is required')
        for month in [start, end]:
            mask = result.observation_period.eq(str(month)) & result.value.isna()
            if not mask.any():
                continue
            result.loc[mask, 'value'] = row.retail_janfeb_combined_yoy
            result.loc[mask, 'value_kind'] = 'janfeb_combined_repeated_hypothesis'
            result.loc[mask, 'information_period_end'] = str(end)
            for field in ['official_field', 'source_url', 'release_date', 'release_source_url', 'vintage_status']:
                result.loc[mask, field] = getattr(row, field)
            result.loc[mask, 'missing_reason'] = 'Historical hypothesis: aggregate repeated; not a standalone monthly rate'
            release = pd.to_datetime(row.release_date, errors='coerce')
            changes.append(dict(date=str(month), original_value=None,
                assumed_retail_yoy=row.retail_janfeb_combined_yoy,
                source_observation_period=row.observation_period, information_period_end=str(end),
                uses_later_observation_period=month < end, release_date=row.release_date,
                eligible_at_month_end=bool(release <= month.end_time) if pd.notna(release) else None,
                source_url=row.source_url, release_source_url=row.release_source_url))
    return result, pd.DataFrame(changes)
