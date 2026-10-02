from datetime import date
import hashlib
import json

import pytest

import release_probe as P


def test_nbs_probe_checks_only_recent_values_and_converts_official_ppi_index(tmp_path, monkeypatch):
    response = {'success': True, 'data': [{'code': '202608', 'values': [{'value': '103.8', '_id': P.NBS_IDS['ppi']}]},
        {'code': '202609', 'values': [{'value': '', '_id': P.NBS_IDS['ppi']}]}]}
    path = tmp_path / 'response.json';path.write_text(json.dumps(response))
    requests = []
    monkeypatch.setattr(P, 'fetch', lambda *a, **k: (requests.append(k) or path))
    data = {'ppi': [{'observation_period': '2026-08', 'value': '3.8'}]}
    assert not P.nbs('ppi', date(2026, 10, 9), data, ['2026-09'])
    assert requests[0]['json_body']['dts'] == ['202607MM-202609MM']
    response['data'][1]['values'][0]['value'] = '104.0';path.write_text(json.dumps(response))
    assert P.nbs('ppi', date(2026, 10, 9), data, ['2026-09'])


def test_probe_invalid_schema_is_error_not_no_change(tmp_path, monkeypatch):
    path = tmp_path / 'bad.json';path.write_text('{"success":false,"data":[]}')
    monkeypatch.setattr(P, 'fetch', lambda *a, **k: path)
    with pytest.raises(ValueError, match='为空或结构变化'):
        P.nbs('retail', date(2026, 10, 15), {'retail': []}, ['2026-09'])


def test_combined_retail_bulletin_can_trigger_refresh_without_monthly_value(tmp_path, monkeypatch):
    data = tmp_path / 'nbs.json';data.write_text(json.dumps({'success': True, 'data': [
        {'code': '202602', 'values': [{'_id': P.NBS_IDS['retail'], 'value': ''}]}]}))
    bulletin = tmp_path / 'press.html';bulletin.write_text('<a class="fl pc_1600" title="2026年1—2月份社会消费品零售总额增长2.8%">公告</a>')
    monkeypatch.setattr(P, 'fetch', lambda url, name, *a, **k: data if name.endswith('.json') else bulletin)
    assert P.nbs('retail', date(2026, 3, 16), {'retail': []}, ['2026-02'])


def test_pboc_unchanged_annex_skips_history_and_changed_annex_refreshes(tmp_path, monkeypatch):
    index = tmp_path / 'index.html';index.write_text('<a href="/year">社会融资规模</a>')
    annual = tmp_path / 'annual.html';annual.write_text('<a href="/flow.htm">htm</a>')
    flow = tmp_path / 'flow.html';flow.write_text('official flow values')
    digest = hashlib.sha256(flow.read_bytes()).hexdigest()
    (tmp_path / 'pboc_2026_flow.html.meta.json').write_text(json.dumps({'sha256': digest}))
    monkeypatch.setattr(P, 'RAW', tmp_path)
    files = {'probe_pboc_index.html': index, 'probe_pboc_current_year.html': annual, 'probe_pboc_current_flow.html': flow}
    monkeypatch.setattr(P, 'fetch', lambda url, name, *a, **k: files[name])
    data = {'social_financing': [{'observation_period': '2026-08', 'value': '10', 'source_url': P.PBOC_BASE + '/flow.htm'}]}
    assert not P.pboc(date(2026, 10, 12), data, ['2026-09'])
    # A later cached month must not conceal a missing earlier observation.
    assert P.pboc(date(2026, 10, 12), data, ['2026-07'])
    flow.write_text('revised official flow values')
    assert P.pboc(date(2026, 10, 12), data, [])


def test_hkma_only_reads_release_directory_and_no_pdf_when_unchanged(tmp_path, monkeypatch):
    landing = tmp_path / 'landing.html';landing.write_text('<meta name="csrf_token" content="public-nonce">')
    directory = tmp_path / 'archive.json';directory.write_text(json.dumps({'data': [
        {'title': 'Monetary Statistics for August 2026', 'url': '/press/aug', 'publish_date': '2026-09-30'}]}))
    called = []
    def fetch(url, name, *args, **kwargs):
        called.append(url)
        return directory if name.endswith('.json') else landing
    monkeypatch.setattr(P, 'fetch', fetch)
    data = {'hk_m2': [{'observation_period': '2026-08', 'value': '11', 'source_url': P.HKMA_BASE + '/press/aug', 'release_date': '2026-09-30'}]}
    assert not P.hkma(date(2026, 9, 30), data, [])
    assert called == [P.HKMA_INDEX, P.HKMA_INDEX + 'api']
    data['hk_m2'] = []
    assert P.hkma(date(2026, 9, 30), data, ['2026-08'])
