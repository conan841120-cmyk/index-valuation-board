import json
import pandas as pd
import pytest
from update import load_data, make_snapshot, transactional_refresh, validate_source, complete_gdp_months, DATASETS
from src.indicators.leading_indicator import build, load_config


def test_failed_refresh_restores_all_processed_files(tmp_path):
    first = tmp_path / 'first.csv';second = tmp_path / 'second.csv'
    first.write_text('original')
    def broken():
        first.write_text('partial');second.write_text('new')
        raise ValueError('bad source')
    with pytest.raises(ValueError):
        transactional_refresh(broken, [first, second])
    assert first.read_text() == 'original'
    assert not second.exists()


def test_refresh_rejects_lost_observations_and_unit_changes():
    old = pd.DataFrame({'observation_period': ['2025-01', '2025-02'], 'value': [1., 2.], 'unit': ['percent'] * 2})
    with pytest.raises(ValueError):validate_source('retail', old.iloc[:1], old)
    wrong = old.copy();wrong['unit'] = 'CNY_100million'
    with pytest.raises(ValueError):validate_source('retail', wrong, old)


def test_web_snapshot_keeps_gaps_and_matches_confirmed_algorithm():
    data = load_data();config = load_config()
    frame = build(data, config['gdp_alignment_mode'], config['standardization_mode'], config)
    status = {n: {'state': 'snapshot', 'last_success_at': None, 'error': None} for n in DATASETS}
    snapshot = make_snapshot(data, frame, config, status, [])
    assert snapshot['series'][0]['date'] == '2012-07'
    rows = {r['date']: r for r in snapshot['series']}
    assert rows['2020-01']['leading_indicator'] is None
    assert rows['2020-01']['retail_yoy'] is None
    assert rows['2021-03']['leading_indicator'] == pytest.approx(frame.loc['2021-03', 'leading_indicator'])
    assert snapshot['config']['standardization_mode'] == 'explicit_unbiased'
    assert snapshot['vintage_certified'] is False
    financing = next(s for s in snapshot['sources'] if s['dataset'] == 'social_financing')
    assert financing['official_field'] == '社会融资规模增量（月度）'
    json.dumps(snapshot, allow_nan=False)


def test_unpublished_quarter_does_not_reuse_old_denominator_for_new_month():
    data = {'gdp': pd.DataFrame({'observation_period': ['2026-Q1', '2026-Q2', '2026-Q3'], 'value': [100., 110., None]})}
    frame = pd.DataFrame({'leading_indicator': [1., 2., 3., 4.]}, index=pd.period_range('2026-06', '2026-09', freq='M'))
    assert str(complete_gdp_months(data, frame).index[-1]) == '2026-08'
    data['gdp'].loc[2, 'value'] = 120.
    assert str(complete_gdp_months(data, frame).index[-1]) == '2026-09'
