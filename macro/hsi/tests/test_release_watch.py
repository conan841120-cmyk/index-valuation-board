from datetime import date
from unittest.mock import Mock, patch

import pytest

import release_watch as W


@pytest.fixture
def data():
    result = {name: [{'observation_period': f'2026-{m:02d}', 'value': '1'} for m in range(1, 7)]
        for name in ('retail', 'ppi', 'social_financing', 'hk_m2')}
    result['gdp'] = [{'observation_period': '2026-Q1', 'value': '100'}, {'observation_period': '2025-Q3', 'value': '100'}]
    return result


def previous():
    return {'monitoring_start_month': '2026-04'}


def drop(data, name, period):
    data[name] = [r for r in data[name] if r['observation_period'] != period]


def test_no_probe_on_quiet_days(data):
    assert W.evaluate(date(2026, 6, 2), data, previous())['due_sources'] == []
    probe = Mock()
    with patch.object(W, 'load_data', return_value=data), patch.object(W, 'write_state'):
        state = W.check(date(2026, 6, 2), previous(), probe=probe)
    probe.assert_not_called()
    assert state['refreshed_sources'] == []


def test_only_window_sources_are_checked(data):
    state = W.evaluate(date(2026, 6, 10), data, previous())
    assert set(state['due_sources']) == {'ppi', 'social_financing'}
    # Inside a window, check for new releases or revisions even if already acquired.
    assert state['alerts'] == []


def test_after_window_missing_period_is_checked_every_day(data):
    drop(data, 'ppi', '2026-05')
    for day in (15, 20, 25, 30):
        state = W.evaluate(date(2026, 6, day), data, previous())
        assert 'ppi' in state['due_sources']
        assert state['alerts'] == []
    assert 'ppi' in W.evaluate(date(2026, 7, 7), data, previous())['due_sources']


def test_next_round_alarms_and_newer_data_does_not_hide_missing_old_period(data):
    drop(data, 'ppi', '2026-05')
    state = W.evaluate(date(2026, 7, 8), data, previous())
    assert [r['observation_period'] for r in state['alerts']] == ['2026-05']
    assert len(state['new_alerts']) == 1
    again = W.evaluate(date(2026, 7, 9), data, state)
    assert again['new_alerts'] == []
    assert again['alerts'][0]['first_detected_date'] == '2026-07-08'
    data['ppi'].append({'observation_period': '2026-05', 'value': '0'})
    assert W.evaluate(date(2026, 7, 9), data, again)['alerts'] == []


def test_hkma_month_end_and_leap_year():
    rule = {'start_day': 26, 'end_day': 31}
    assert W.rounds('hk_m2', rule, '2026-02', '2026-02')[0]['window_end'] == '2026-02-28'
    assert W.rounds('hk_m2', rule, '2024-02', '2024-02')[0]['window_end'] == '2024-02-29'


def test_gdp_next_round_is_next_quarter(data):
    drop(data, 'gdp', '2025-Q3')
    p = {'monitoring_start_month': '2025-10'}
    # Populate other sources to isolate the GDP exception.
    for name in ('retail', 'ppi', 'social_financing', 'hk_m2'):
        data[name] += [{'observation_period': f'2025-{m:02d}', 'value': '1'} for m in range(9, 13)]
    before = W.evaluate(date(2026, 1, 15), data, p)
    assert 'gdp' in before['due_sources']
    assert not any(a['dataset'] == 'gdp' for a in before['alerts'])
    after = W.evaluate(date(2026, 1, 16), data, p)
    assert any(a['dataset'] == 'gdp' and a['observation_period'] == '2025-Q3' for a in after['alerts'])


def test_retail_january_february_seasonality(data):
    policy = W.evaluate(date(2026, 6, 2), data, previous())['policy']
    rounds = W.rounds('retail', policy['sources']['retail'], '2026-01', '2026-03')
    assert [r['release_month'] for r in rounds] == ['2026-01', '2026-03']
    assert rounds[0]['next_window_start'] == '2026-03-14'
    drop(data, 'retail', '2026-02')
    assert not W.acquired('retail', '2026-02', data)
    data['retail'].append({'observation_period': '2026-02', 'value': '',
        'release_date': '2026-03-16', 'release_title': '2026年1—2月份社会消费品零售总额增长2.8%'})
    assert W.acquired('retail', '2026-02', data)
    assert '2026-02' not in W.values(data['retail'])


def test_refresh_only_changed_sources_and_hsi(data):
    probe = Mock(side_effect=lambda name, *_: name == 'ppi')
    refresh = Mock()
    with patch.object(W, 'load_data', return_value=data), patch.object(W, 'write_state'):
        W.check(date(2026, 6, 10), previous(), probe=probe, refresh=refresh)
    assert [call.args[0] for call in probe.call_args_list] == ['ppi', 'social_financing']
    refresh.assert_called_once_with(refresh=True, selected=['ppi', 'hsi'])


def test_probe_failure_keeps_daily_catch_up_without_early_alarm(data):
    drop(data, 'ppi', '2026-05')
    probe = Mock(side_effect=ValueError('HTTP 503'))
    with patch.object(W, 'load_data', return_value=data), patch.object(W, 'write_state'):
        state = W.check(date(2026, 6, 22), previous(), probe=probe)
    row = next(r for r in state['sources'] if r['dataset'] == 'ppi')
    assert row['phase'] == 'catch_up'
    assert row['last_probe_error'] == 'HTTP 503'
    assert state['alerts'] == []


def test_refresh_then_recheck_before_raising_alarm(data):
    drop(data, 'ppi', '2026-05')
    def recovered(**kwargs):
        data['ppi'].append({'observation_period': '2026-05', 'value': '1'})
    with patch.object(W, 'load_data', return_value=data), patch.object(W, 'write_state'):
        state = W.check(date(2026, 7, 8), previous(), probe=lambda name, *_: name == 'ppi', refresh=recovered)
    assert state['alerts'] == []
    assert state['new_alerts'] == []


def source(state, name):
    return next(r for r in state['sources'] if r['dataset'] == name)


def test_round_switches_on_window_start_not_on_success(data):
    before = source(W.evaluate(date(2026, 6, 7), data, previous()), 'ppi')
    assert before['current_round']['window_start'] == '2026-05-08'
    assert before['next_round']['window_start'] == '2026-06-08'
    for day in (8, 14, 15, 30):
        row = source(W.evaluate(date(2026, 6, day), data, previous()), 'ppi')
        assert row['current_round']['window_start'] == '2026-06-08'
        assert row['current_round']['observation_period'] == '2026-05'
        assert row['current_round']['status'] == 'acquired'
        assert row['next_round']['window_start'] == '2026-07-08'
    assert source(W.evaluate(date(2026, 7, 7), data, previous()), 'ppi')['current_round']['window_start'] == '2026-06-08'


def test_current_round_status_uses_exact_target_and_preserves_old_hole(data):
    drop(data, 'ppi', '2026-05')
    during = source(W.evaluate(date(2026, 6, 10), data, previous()), 'ppi')
    assert during['current_round']['status'] == 'awaiting'
    after = source(W.evaluate(date(2026, 6, 15), data, previous()), 'ppi')
    assert after['current_round']['status'] == 'catch_up'
    next_ = source(W.evaluate(date(2026, 7, 8), data, previous()), 'ppi')
    assert next_['current_round']['observation_period'] == '2026-06'
    assert next_['current_round']['status'] == 'acquired'
    assert next_['backlog_rounds'][0]['observation_period'] == '2026-05'
    assert next_['backlog_rounds'][0]['window_start'] == '2026-06-08'
    assert next_['phase'] == 'alarm'
    data['ppi'].append({'observation_period': '2026-05', 'value': '1'})
    assert source(W.evaluate(date(2026, 7, 9), data, previous()), 'ppi')['backlog_rounds'] == []


def test_display_gdp_and_retail_follow_special_cycles(data):
    gdp = source(W.evaluate(date(2026, 7, 15), data, previous()), 'gdp')
    assert gdp['current_round']['observation_period'] == '2026-Q1'
    assert gdp['next_round']['window_start'] == '2026-07-16'
    gdp = source(W.evaluate(date(2026, 7, 16), data, previous()), 'gdp')
    assert gdp['current_round']['observation_period'] == '2026-Q2'
    assert gdp['next_round']['window_start'] == '2026-10-16'
    retail = source(W.evaluate(date(2026, 2, 20), data, {'monitoring_start_month': '2026-01'}), 'retail')
    assert retail['current_round']['window_start'] == '2026-01-14'
    assert retail['next_round']['window_start'] == '2026-03-14'


def test_display_next_window_handles_year_end_and_leap_month(data):
    row = source(W.evaluate(date(2026, 12, 31), data, previous()), 'ppi')
    assert row['next_round']['window_start'] == '2027-01-08'
    row = source(W.evaluate(date(2024, 1, 31), data, {'monitoring_start_month': '2023-10'}), 'hk_m2')
    assert row['next_round']['window_end'] == '2024-02-29'
