"""Local cache/provenance regressions; receipts are synthetic, never paid calls."""
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch

import pytest

from research import trading_protocol as c, trading_study as s
from zenith.providers import digest as provider_digest


@pytest.fixture
def episode(tmp_path):
    study = tmp_path / 'study'
    packet = {'schema': 'zenith_trading_packet_v1', 'issue_date': '2026-01-05',
        'issue_at': '2026-01-05T21:15:00Z', 'entry_at': '2026-01-06T14:30:00Z',
        'exit_at': '2026-01-06T21:00:00Z', 'assets': [{
            'asset_id': 'asset_1', 'evidence_refs': ['asset_1:history', 'asset_1:state', 'asset_1:anchor'],
            'history20': [{'Open': 10, 'High': 12, 'Low': 9, 'Close': 11, 'Volume': 100}] * 20,
            'preceding_close': 11, 'features': {'momentum': .01},
            'anchor_mean_return': .001, 'info_status': 'available'}]}
    packet['packet_sha256'] = s.sha(packet)
    value = {'schema': 'zenith_trading_forecast_v1', 'packet_sha256': packet['packet_sha256'],
        'interpretation_sha256': c.interpretation_sha256(None), 'forecasts': [{
            'asset_id': 'asset_1', 'mean_expected_return': .002, 'evidence_refs': ['asset_1:anchor'],
            'reasoning': 'Synthetic anchor estimate.', 'abstain': False}]}
    return {'study': study, 'packet': packet, 'raw': json.dumps(value), 'value': value,
            'stamp': '2026-01-05', 'skill': 'Use the supplied numerical anchor.',
            'spec': {'budget': {}, 'authorization': {'synthetic': True}}}


def forecast(ep):
    return s.forecast(ep['study'], ep['stamp'], ep['packet'], None, ep['skill'], 'baseline', ep['spec'])


def cache_path(ep):
    return ep['study'] / 'forecasts/baseline' / (ep['stamp'] + '.json')


def paid_fixture(ep, *, failed=False):
    """Mimic the existing adapter's settled artifact layout without invoking it."""
    budget = ep['study'] / 'budget'
    ep['spec'] = {'authorization': {'synthetic': True}, 'budget': {
        'model': 'synthetic/model', 'provider_slug': 'deepinfra/fp8', 'max_cost_usd': '4',
        'max_calls': 600, 'max_output_tokens': 1024, 'budget_dir': str(budget)}}
    key = 'baseline_' + ep['stamp']
    prompt = c.forecast_prompt(ep['packet'], None, ep['skill'])
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    identity = {'run_id': key, 'node_id': 'reasoning', 'prompt_sha256': prompt_hash,
                'provider': 'openrouter_budgeted', 'requested_model': 'synthetic/model',
                'provider_slug': 'deepinfra/fp8'}
    call_id = provider_digest(identity)
    directory = ep['study'] / 'calls' / key
    s.write_json(directory / 'request.json', {'prompt': prompt, 'prompt_sha256': prompt_hash})
    call = {k: v for k, v in identity.items() if k != 'provider_slug'}
    call.update(schema='zenith_api_call_v1', call_id=call_id, execution_kind='openrouter_budgeted',
                requested_provider_slug='deepinfra/fp8', verified_provider_name='DeepInfra',
                budget_dir=str(budget), max_output_tokens=1024,
                status='failed' if failed else 'response_supplied', cost=None if failed else '0.0001',
                reserved_cost_usd='0.01', synthetic_fixture=True)
    if failed:
        call['error'] = 'Synthetic HTTP 429; actual cost unknown'
    else:
        call.update(provider_receipt={'response_text': ep['raw'], 'actual_provider': 'DeepInfra',
                                     'model': 'synthetic/model', 'cost': '0.0001'},
                    response_sha256=hashlib.sha256(ep['raw'].encode()).hexdigest())
    path = directory / 'handoff/api_calls/openrouter_budgeted' / (call_id + '.json')
    ledger_path = budget / 'budget.json'
    ledger = {'schema': 'zenith_shared_budget_v1', 'entries': {call_id: call}, 'halted': failed,
              'total_reserved_usd': '0.01', 'total_reported_cost_usd': '0' if failed else '0.0001'}
    s.write_json(path, call); s.write_json(ledger_path, ledger)
    return path, ledger_path, call_id


def test_parsed_mean_tamper_fails_even_after_record_checksum_is_rewritten(episode):
    ep = episode
    with patch.object(s, 'ask', return_value=ep['raw']) as ask:
        first = forecast(ep)
        assert forecast(ep) == first
        assert ask.call_count == 1
    record = s.read_json(cache_path(ep))
    record['value']['forecasts'][0]['mean_expected_return'] = .8
    s.write_json(cache_path(ep), s._seal_record(record))
    with patch.object(s, 'ask') as ask, pytest.raises(ValueError, match='semantic reparse'):
        forecast(ep)
    ask.assert_not_called()


def test_transport_failure_stops_then_exact_resume_never_resends_or_releases_reservation(episode):
    ep = episode
    _, ledger_path, _ = paid_fixture(ep, failed=True)
    before = ledger_path.read_bytes()
    with patch.object(s, 'ask', side_effect=RuntimeError('Synthetic HTTP 429')) as ask:
        with pytest.raises(RuntimeError, match='HTTP 429'):
            forecast(ep)
        stored = s.read_json(cache_path(ep))
        assert stored['status'] == 'transport_failed' and stored['value'] is None
        assert stored['raw_response'] is None and stored['raw_response_sha256'] is None
        assert forecast(ep) == stored
        assert ask.call_count == 1
    assert ledger_path.read_bytes() == before  # Unknown charge and halt remain untouched.


def test_recorded_failed_interpretation_stays_none_and_never_fabricates_upstream(episode):
    ep = episode
    with patch.object(s, 'ask', side_effect=RuntimeError('Synthetic upstream failure')) as ask:
        with pytest.raises(RuntimeError):
            s.interpreted(ep['study'], ep['stamp'], ep['packet'], ep['spec'])
        record = s.interpreted(ep['study'], ep['stamp'], ep['packet'], ep['spec'])
        assert record['status'] == 'transport_failed' and record['value'] is None
        assert ask.call_count == 1


@pytest.mark.parametrize('drift', ['ledger_only', 'raw_receipt', 'wrong_model', 'wrong_pin', 'wrong_actual_provider'])
def test_cached_paid_response_rejects_receipt_or_shared_ledger_binding_drift(episode, drift):
    ep = episode
    call_path, ledger_path, call_id = paid_fixture(ep)
    with patch.object(s, 'ask', return_value=ep['raw']):
        forecast(ep)
    call, ledger = s.read_json(call_path), s.read_json(ledger_path)
    if drift == 'ledger_only':
        ledger['entries'][call_id]['cost'] = '0.001'
    else:
        if drift == 'raw_receipt': call['provider_receipt']['response_text'] = '{}'
        if drift == 'wrong_model': call['requested_model'] = 'other/model'
        if drift == 'wrong_pin': call['requested_provider_slug'] = 'other/provider'
        if drift == 'wrong_actual_provider': call['provider_receipt']['actual_provider'] = 'Other Host'
        ledger['entries'][call_id] = deepcopy(call)
        s.write_json(call_path, call)
    s.write_json(ledger_path, ledger)
    with patch.object(s, 'ask') as ask, pytest.raises(ValueError):
        forecast(ep)
    ask.assert_not_called()


def test_rehashed_raw_and_parsed_cache_cannot_disagree_with_original_paid_bytes(episode):
    ep = episode; paid_fixture(ep)
    with patch.object(s, 'ask', return_value=ep['raw']):
        forecast(ep)
    record = s.read_json(cache_path(ep))
    record['value']['forecasts'][0]['mean_expected_return'] = -.9
    record['raw_response'] = json.dumps(record['value'])
    record['raw_response_sha256'] = hashlib.sha256(record['raw_response'].encode()).hexdigest()
    s.write_json(cache_path(ep), s._seal_record(record))
    with patch.object(s, 'ask') as ask, pytest.raises(ValueError, match='settled paid response'):
        forecast(ep)
    ask.assert_not_called()


def test_missing_local_failed_receipt_does_not_erase_attempt_present_in_shared_authority(episode):
    ep = episode; call_path, ledger_path, _ = paid_fixture(ep, failed=True)
    with patch.object(s, 'ask', side_effect=RuntimeError('Synthetic HTTP 429')):
        with pytest.raises(RuntimeError):
            forecast(ep)
    before = ledger_path.read_bytes(); call_path.unlink()
    with patch.object(s, 'ask') as ask, pytest.raises(ValueError, match='recorded paid attempt'):
        forecast(ep)
    ask.assert_not_called()
    assert ledger_path.read_bytes() == before
