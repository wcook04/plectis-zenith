"""Mechanism tests: synthetic responses are never historical learning results."""
from copy import deepcopy
import json

import pytest

from benchmarks.traderharness import FEATURES, sha
from research import ashare_protocol as protocol
from research import ashare_study as study
from research import trading_protocol as typed
from research.engine import write_json, read_json


def packet(date='2023-06-01', n=2):
    result = {'schema': 'zenith_trading_packet_v2', 'issue_date': date,
              'issue_at': date + 'T07:01:00+00:00',
              'entry_at': date + 'T23:30:00+00:00', 'exit_at': date + 'T23:59:00+00:00', 'assets': []}
    for i in range(1, n + 1):
        aid = f'asset_{i}'
        identity = {'ref_id': aid + ':identity', 'kind': 'filing', 'content': 'Fixed issuer 600519',
                    'available_at': result['issue_at'], 'availability_basis': 'observed_timestamp', 'source_sha256': 'a' * 64}
        news = {**identity, 'ref_id': aid + ':news_1', 'kind': 'news', 'content': 'FORWARD_ONLY profit grew30%.'}
        result['assets'].append({'asset_id': aid,
            'evidence_refs': [aid + ':' + k for k in ('history', 'state', 'anchor')] + [identity['ref_id'], news['ref_id']],
            'history20': [{'Open': 1., 'High': 1.1, 'Low': .9, 'Close': 1., 'Volume': 1.} for _ in range(20)],
            'preceding_close': 1., 'features': dict.fromkeys(FEATURES, .01),
            'anchor_mean_return': .01, 'info_status': 'available', 'context_evidence': [identity, news]})
    result['packet_sha256'] = sha(result)
    return result


def rows(date='2023-06-01', phase='training', n=2):
    return [{'sample_id': date + ':s' + str(i), 'symbol': 's' + str(i), 'phase': phase,
             'issue_date': date, 'target_date': date, 'outcome_available_at': date + 'T23:59:01+00:00',
             'actual_return': i * .01, 'features': [i * .01] * len(FEATURES), 'momentum': .01,
             'review_evidence': [{'id': 'later_shared', 'content': 'HINDSIGHT_SECRET',
                                  'available_at': date + 'T23:59:00+00:00'}]} for i in range(1, n + 1)]


def interpretation(p):
    return {'schema': 'zenith_trading_interpretation_v1', 'packet_sha256': p['packet_sha256'],
            'interpretations': [{'asset_id': a['asset_id'], 'summary': 'Expectations unknown.',
                                'evidence_refs': a['evidence_refs'][:1]} for a in p['assets']]}


def forecast(p, interp):
    return {'schema': 'zenith_trading_forecast_v1', 'packet_sha256': p['packet_sha256'],
            'interpretation_sha256': typed.interpretation_sha256(interp),
            'forecasts': [{'asset_id': a['asset_id'], 'mean_expected_return': .01, 'abstain': False,
                          'reasoning': 'Weak evidence.', 'evidence_refs': a['evidence_refs'][:1]} for a in p['assets']]}


def test_information_treatments_keep_prices_identity_and_clocks_but_not_semantics():
    p = packet()
    before = deepcopy(p)
    rich, meta, price = [protocol.project(p, m) for m in ('rich', 'metadata', 'price')]
    assert 'FORWARD_ONLY' in protocol.interpret_prompt(rich)
    assert 'FORWARD_ONLY' not in protocol.interpret_prompt(meta)
    assert 'FORWARD_ONLY' not in protocol.interpret_prompt(price)
    assert '600519' in protocol.interpret_prompt(price)
    for a, b, c in zip(rich['assets'], meta['assets'], price['assets'], strict=True):
        assert a['history20'] == b['history20'] == c['history20']
        assert a['anchor_mean_return'] == b['anchor_mean_return'] == c['anchor_mean_return']
        assert len(a['context_evidence']) == len(b['context_evidence'])
        assert len(c['context_evidence']) == 1
    assert p == before


def test_teacher_contrast_changes_only_privileged_reporting_and_clock():
    p = packet()
    interp, r = interpretation(p), rows()
    f = forecast(p, interp)
    outcome = protocol.teacher_case(p, f, interp, r, '2024-01-01T00:00:00+00:00', hindsight=False)
    hindsight = protocol.teacher_case(p, f, interp, r, '2024-01-01T00:00:00+00:00', hindsight=True)
    assert outcome['outcomes'] == hindsight['outcomes']
    assert outcome['packet'] == hindsight['packet']
    assert 'HINDSIGHT_SECRET' not in protocol.review_prompt(outcome)
    assert 'HINDSIGHT_SECRET' in protocol.review_prompt(hindsight)
    assert 'HINDSIGHT_SECRET' not in protocol.forecast_prompt(p, interp)
    assert hindsight['update_available_at'] == '2023-06-01T23:59:01+00:00'


def test_teacher_rejects_test_rows_and_post_training_reporting():
    p = packet()
    with pytest.raises(ValueError, match='training-only'):
        protocol.teacher_case(p, None, None, rows(phase='test'), '2024-01-01T00:00:00+00:00', hindsight=True)
    r = rows()
    r[0]['review_evidence'][0]['available_at'] = '2024-02-01T00:00:00+00:00'
    with pytest.raises(ValueError, match='boundary'):
        protocol.teacher_case(p, None, None, r, '2024-01-01T00:00:00+00:00', hindsight=True)


def test_late_teacher_report_delays_lesson_and_memory_availability():
    p = packet()
    r = rows()
    for row in r:
        row['review_evidence'][0]['available_at'] = '2023-06-08T12:00:00+00:00'
    case = protocol.teacher_case(p, None, None, r, '2024-01-01T00:00:00+00:00', hindsight=True)
    assert case['update_available_at'] == '2023-06-08T12:00:00+00:00'
    review = {'case_id': p['issue_date'], 'classification': 'unresolved'}
    assert protocol.retrieve_memories(packet('2023-06-07'), [case], [review]) == []
    assert len(protocol.retrieve_memories(packet('2023-06-09'), [case], [review])) == 1


def test_common_review_references_are_valid_without_duplicate_allowed_ref_failure():
    p = packet()
    case = protocol.teacher_case(p, None, None, rows(), '2024-01-01T00:00:00+00:00', hindsight=True)
    review = {'case_id': p['issue_date'], 'classification': 'unresolved', 'trigger': 'Unknown expectations',
              'lesson': 'Do not infer surprise.', 'disconfirmation': 'An expectation source is supplied.',
              'uncertainty': 'No established cause.', 'evidence_refs': ['later_shared']}
    assert protocol.parse_review(json.dumps(review), case) == review


def test_blinded_proposal_cannot_receive_reviews_or_outcome():
    assert 'SECRET' not in protocol.skill_prompt('blinded', [{'case_id': 'SECRET', 'lesson': 'SECRET'}])


def test_mse_decomposition_ranking_and_incomplete_support():
    r = rows()
    predictions = {r[0]['sample_id']: .03, r[1]['sample_id']: .04}
    result = study.evaluate(r, predictions)
    assert result['metrics']['mse'] == pytest.approx(.0004)
    assert result['metrics']['relative_shape_mse'] == pytest.approx(0.)
    assert result['metrics']['common_level_mse'] == pytest.approx(.0004)
    assert result['pairwise_order_accuracy'] == 1
    incomplete = study.evaluate(r, {r[0]['sample_id']: .01})
    assert incomplete['metrics']['mse'] is None and incomplete['daily'] == []
    assert study.paired(result, incomplete)['mean_difference'] is None


def test_mse_equal_weights_dates_not_number_of_assets():
    r = rows() + rows('2023-06-08', n=1)
    pred = {row['sample_id']: row['actual_return'] + (1 if row['issue_date'] == '2023-06-08' else 0) for row in r}
    assert study.evaluate(r, pred)['metrics']['mse'] == .5


def test_semantic_probes_are_label_free_and_do_not_mutate_real_packet():
    p = packet()
    probes = protocol.semantic_probes(p)
    assert len(probes) == 7
    assert 'actual_return' not in json.dumps(probes)
    assert len({r['packet']['packet_sha256'] for r in probes}) == 7
    for probe in probes:
        typed.validate_packet(probe['packet'])
    assert p == packet()


def test_memory_selection_does_not_rank_realized_returns():
    cases = [protocol.teacher_case(packet(d), None, None, rows(d), '2024-01-01T00:00:00+00:00', hindsight=True)
             for d in ['2023-06-01', '2023-06-08', '2023-06-15', '2023-06-22']]
    reviews = [{'case_id': c['case_id'], 'classification': 'unresolved'} for c in cases]
    selected = protocol.retrieve_memories(packet('2024-02-01'), cases, reviews)
    for c in cases:
        c['outcomes'][0]['actual_return'] = 1000 if c['case_id'] == '2023-06-22' else -999
    changed = protocol.retrieve_memories(packet('2024-02-01'), cases, reviews)
    assert [r['case_id'] for r in selected] == [r['case_id'] for r in changed]


def test_stage_binding_rejects_altered_training_predictions(tmp_path):
    write_json(tmp_path / 'binding.json', {'frozen_sha256': 'fixed'})
    study.save_stage(tmp_path, 'training', {'prediction': .1})
    write_json(tmp_path / 'training.json', {'prediction': .2})
    with pytest.raises(ValueError, match='stage changed'):
        study.load_stage(tmp_path, 'training')


def test_cost_plan_has_explicit_quote_and_all_core_contrasts():
    packets = {d: packet(d) for d in ['2023-06-01', '2024-06-01', '2025-06-01']}
    spec = {'splits': {'training': ['2023', '2024'], 'validation': ['2024', '2025'], 'test': ['2025', '2026']}}
    plan = study.cost_plan(spec, packets)
    assert plan['maximum_core_calls'] == 29
    assert plan['conservative_cost_usd'] is None
    priced = study.cost_plan(spec, packets, input_per_million=.3, output_per_million=1.2)
    assert priced['conservative_cost_usd'] > 0


def test_verification_never_runs_missing_node(tmp_path):
    with pytest.raises(ValueError, match='observation missing'):
        study.node(tmp_path, 'missing', 'prompt', lambda x: x, {'_cache_only': True})


def test_synthetic_full_study_executes_contracts_and_rejects_resealed_selection(tmp_path, monkeypatch):
    """Exercise actual cache/reparse path with a declared synthetic transport."""
    from research import trading_study
    calls = []

    def ask(directory, key, prompt, spec):
        calls.append(key)
        if key.startswith('review_'):
            case = json.loads(prompt.split('CASE_JSON\n')[1])
            return json.dumps({'case_id': case['case_id'], 'classification': 'unresolved',
                'trigger': 'Expectations absent.', 'lesson': 'Preserve uncertainty.',
                'disconfirmation': 'Expectation supplied.', 'uncertainty': 'No cause established.',
                'evidence_refs': [case['packet']['assets'][0]['evidence_refs'][0]]})
        if key.startswith('proposal_'):
            ctx = json.loads(prompt.split('\n')[-1])
            return json.dumps({'schema': 'zenith_trading_skill_v1', 'skill': 'Candidate conditional lesson.',
                               'rationale': 'Testable change.', 'evidence_refs': ctx['allowed_refs'][:1]})
        payload = json.loads(prompt.split('EVIDENCE_JSON\n')[1])
        if key.startswith('interpret_'):
            return json.dumps(interpretation(payload))
        return json.dumps(forecast(payload['packet'], payload['interpretation']))

    monkeypatch.setattr(trading_study, 'ask', ask)
    all_rows = rows('2023-06-01', n=10) + rows('2023-06-08', n=10) + rows('2024-06-01', 'validation', n=10) + rows('2025-06-01', 'test', n=10)
    # Lexicographic symbol order is the adapter's frozen join convention.
    symbols = sorted({r['symbol'] for r in all_rows})
    packets = {d: packet(d, n=10) for d in sorted({r['issue_date'] for r in all_rows})}
    spec = {'budget': {}, 'authorization': {'synthetic': True}, 'symbols': symbols,
            'teacher_boundary': '2023-12-31T23:59:59+08:00', 'claim_limit': 'synthetic only',
            'anchor': {'coefficients': [0.] * (len(FEATURES) + 1), 'mean': [0.] * len(FEATURES), 'scale': [1.] * len(FEATURES)}}
    write_json(tmp_path / 'binding.json', {'frozen_sha256': 'fixture'})
    study.development(tmp_path, spec, all_rows, packets)
    study.learn(tmp_path, spec, all_rows, packets)
    selected = study.select(tmp_path, spec, all_rows, packets)
    assert selected['choices'] == dict.fromkeys(study.ARMS, 'rich')  # unchanged wins ties
    altered = deepcopy(selected)
    altered['policies']['rich']['skill'] = 'Unproposed test skill.'
    altered['selection_sha256'] = sha({k: v for k, v in altered.items() if k != 'selection_sha256'})
    write_json(tmp_path / 'selection.json', altered)
    before = len(calls)
    with pytest.raises(ValueError, match='selection differs'):
        study.final(tmp_path, spec, all_rows, packets)
    assert len(calls) == before and not (tmp_path / 'final-seal.json').exists()
    write_json(tmp_path / 'selection.json', selected)
    result = study.final(tmp_path, spec, all_rows, packets)
    assert result['scores']['rich']['complete']
    before = len(calls)
    assert study.final(tmp_path, spec, all_rows, packets) == result
    assert len(calls) == before
    # Even resealing a derived result cannot override the authentic node scores.
    altered = deepcopy(result)
    altered['scores']['rich']['metrics']['mse'] = 0.
    study.save_stage(tmp_path, 'result', altered)
    with pytest.raises(ValueError, match='final projection'):
        study.final(tmp_path, spec, all_rows, packets)


def test_unicode_memory_is_packed_before_prompt_generation():
    p = packet()
    case = protocol.teacher_case(p, None, None, rows(), '2024-01-01T00:00:00+00:00', hindsight=True)
    review = {'case_id': p['issue_date'], 'classification': 'unresolved',
              **{k: '中' * 240 for k in ('trigger', 'lesson', 'disconfirmation', 'uncertainty')}}
    memories = protocol.retrieve_memories(packet('2024-02-01'), [case] * 4, [review] * 4)
    assert 1 <= len(memories) <= 3
    assert len(json.dumps(memories, sort_keys=True, separators=(',', ':')).encode()) <= 24000
    later = packet('2024-02-01')
    protocol.forecast_prompt(later, interpretation(later), memories=memories)
