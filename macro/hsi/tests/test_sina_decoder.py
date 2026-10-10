import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pandas as pd
import pytest
import update
from src.data import download_hsi

WRAPPER = Path(download_hsi.__file__).with_name('decode_sina.js')


def normal_input(path):
    # One ordinary close-only record in Sina's little-endian six-bit format.
    fields = [(200, 12), (63, 6), (17000, 18), (2, 3), (1, 3),
              (2500000, 30), (1, 6), (0, 1), (0, 1), (1, 3)]
    bits = [value >> bit & 1 for value, width in fields for bit in range(width)]
    bits += [0] * (-len(bits) % 6)
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    encoded = ''.join(alphabet[sum(bits[start + bit] << bit for bit in range(6))]
                      for start in range(0, len(bits), 6))
    path.write_text('var normal="' + encoded + '";')
    return path


def test_normal_decoder_and_old_cli_rejected(tmp_path):
    source = normal_input(tmp_path / 'normal.js'); out = tmp_path / 'decoded.json'
    subprocess.run(['node', str(WRAPPER), str(source), str(out)], check=True)
    rows = json.loads(out.read_text())
    assert len(rows) == 1
    assert rows[0]['close'] == pytest.approx(25000.01)
    assert rows[0]['prevclose'] == 25000
    before = out.read_bytes()
    result = subprocess.run(['node', str(WRAPPER), str(source), str(WRAPPER), str(out)], capture_output=True, text=True)
    assert result.returncode != 0 and 'Usage:' in result.stderr
    assert out.read_bytes() == before


def test_digest_failure_preserves_cache_and_source_status(tmp_path, monkeypatch):
    local = tmp_path / 'src/data';local.mkdir(parents=True)
    shutil.copyfile(WRAPPER, local / WRAPPER.name)
    shutil.copytree(WRAPPER.parent / 'vendor', local / 'vendor')
    decoder = local / 'vendor/sina_hk_decode.js'
    decoder.write_bytes(decoder.read_bytes() + b'\n')  # Benign byte drift.
    source = normal_input(tmp_path / 'normal.js')
    interim = tmp_path / 'data/interim';interim.mkdir(parents=True)
    out = interim / 'sina_hsi_daily.json';out.write_text('previous decoded data')
    processed = tmp_path / 'data/processed';processed.mkdir()
    frame = pd.DataFrame({'observation_period': ['2026-09'], 'value': [25000.], 'unit': ['index_points']})
    cache = processed / 'hsi.csv';frame.to_csv(cache, index=False);before = cache.read_bytes()
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps({'sources': [{'dataset': 'hsi', 'state': 'fresh', 'last_success_at': 'previous success'}]}))
    monkeypatch.setattr(download_hsi, 'ROOT', tmp_path)
    fetch = Mock(return_value=source);monkeypatch.setattr(download_hsi, 'fetch', fetch)
    monkeypatch.setattr(update, 'ROOT', tmp_path);monkeypatch.setattr(update, 'DESTINATION', snapshot)
    status, _ = update.refresh_sources(['hsi'])
    fetch.assert_called_once_with(download_hsi.URL, 'sina_hsi_encoded.js', True)
    assert status['hsi']['state'] == 'cached'
    assert status['hsi']['last_success_at'] == 'previous success'
    assert status['hsi']['error']
    assert cache.read_bytes() == before
    assert out.read_text() == 'previous decoded data'
    result = subprocess.run(['node', str(local / WRAPPER.name), str(source), str(out)], capture_output=True, text=True)
    assert result.returncode != 0 and 'SHA-256 mismatch' in result.stderr
