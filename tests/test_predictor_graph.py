"""The replacement really executes the native engine and CP validators."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from system.lib.schema_validator import validate_cp1, validate_cp2
from variants.graph import variant_sha256
from variants.predictor import build_replacement, apply_predictor_replacement, NODE_IDS, PROFILE
from zenith import runtime
from zenith.providers import write_json

ROOT = Path(__file__).resolve().parents[1]


def fixture_root(tmp_path):
    shutil.copytree(ROOT / 'codex', tmp_path / 'codex')
    write_json(tmp_path / 'master_config.json', {'paths': {'runs_dir': 'state/runs'}})
    source = tmp_path / 'recorded'
    write_json(source / 'runtime_context.json', {'as_of': '2015-08-03T20:00:00+00:00'})
    write_json(source / 'artifacts/global_stock_feed.json', {'status': 'success',
        'metadata': {'status': 'success', 'as_of': '2015-08-03T20:00:00+00:00', 'synthetic_fixture': True,
                     'price_basis': 'synthetic_point_quote', 'currency': 'USD'},
        'data': {'columns': ['Ticker', 'Price', 'timestamp'],
                 'rows': [['XOM', 100.0, '2015-08-03T20:00:00+00:00']]}})
    return source


def cp1():
    return {'evidence_dictionary': [{'ref_id': '[1]', 'ledger_id': 'S_00000001',
                                     'subject': 'XOM', 'signal_summary': 'Synthetic point quote.'}],
            'epicentre_thesis': '[1] ' + 'Synthetic fixture transmission uses the subject baseline and concrete invalidation condition. ' * 20}


def test_fixed_replacement_scope_contracts_and_authored_graph_unchanged():
    base = runtime.load_graph(ROOT)
    original = deepcopy(base)
    payload = build_replacement(base)
    graph, receipt = apply_predictor_replacement(base, payload)
    assert base == original and graph['global_stock_feed'] == base['global_stock_feed']
    assert set(graph) == set(NODE_IDS)
    assert runtime.plan(ROOT, 'lab', 'lab_director', payload)['waves'] == [
        ['global_stock_feed'], ['lab_decide'], ['lab_director']]
    assert runtime.plan(ROOT, 'lab')['node_count'] == 28
    assert receipt['invariants']['base_ancestry_preserved'] is False
    assert receipt['invariants']['cp1_cp2_interfaces_preserved'] is True
    assert 'lab_integrity' in receipt['removed_node_ids']
    cp2 = graph['lab_director']
    contract = cp2.meta['reasoning_contract']
    assert contract['input_contract']['required_artifacts'] == list(cp2.dependencies)
    assert contract['learning_contract']['dossier_reads'] == []
    assert 'truth_side_evidence' in contract['injection_contract']['forbidden']
    assert contract['side_effect_contract'] == base['lab_director'].meta['reasoning_contract']['side_effect_contract']
    for key in ('lab_decide', 'lab_director'):
        assert graph[key].output_schema == base[key].output_schema
        assert graph[key].execution['retries'] == 1 and graph[key].execution['tools'] == []
        assert 'global_stock_feed' in graph[key].dependencies


@pytest.mark.parametrize('change', ['hash', 'profile', 'extra', 'base'])
def test_replacement_rejects_unknown_or_changed_identity(change):
    graph = runtime.load_graph(ROOT)
    payload = build_replacement(graph)
    if change == 'hash': payload['variant_sha256'] = '0' * 64
    elif change == 'profile': payload['instruction_profile'] = 'arbitrary_code'
    elif change == 'extra': payload['truth_run'] = 'later-data'
    else: payload['base_node_hashes']['lab_director'] = '0' * 64
    if change != 'hash': payload['variant_sha256'] = variant_sha256(payload)
    with pytest.raises(ValueError): runtime.load_graph(ROOT, payload)


def test_real_three_node_engine_handoff_and_output_validation(tmp_path):
    source = fixture_root(tmp_path)
    payload = build_replacement(runtime.load_graph(tmp_path))
    write_json(tmp_path / 'replacement.json', payload)
    result = runtime.start(tmp_path, mission='lab', target='lab_director', run_id='COMPACT',
        feed_source=str(source), time_anchor='2015-08-03T20:00:00+00:00',
        horizon='next_us_close', graph_variant=str(tmp_path / 'replacement.json'))
    assert result['status'] == 'awaiting_agent'
    assert [item['node_id'] for item in result['pending']] == ['lab_decide']
    packet = json.loads(Path(result['pending'][0]['packet_path']).read_text())
    assert '<global_stock_feed>' in packet['prompt']
    assert 'Only the STOCK lane is supplied' in packet['prompt']
    assert PROFILE == 'stocknet_price_only_cp1_cp2_v2'
    assert 'at least 150 words' in packet['prompt'] and '200-250 words' in packet['prompt']
    assert 'literal bracketed strings' in packet['prompt']
    answer = tmp_path / 'answer.txt'; answer.write_text(json.dumps(cp1()))
    result = runtime.import_response(tmp_path, packet_path=Path(result['pending'][0]['packet_path']),
                                     response_path=answer, model='synthetic-fixture')['run']
    assert [item['node_id'] for item in result['pending']] == ['lab_director']
    second = json.loads(Path(result['pending'][0]['packet_path']).read_text())
    assert '<lab_decide>' in second['prompt'] and '<global_stock_feed>' in second['prompt']
    assert 'at least 165 words' in second['prompt'] and '220-280 words' in second['prompt']
    assert 'do NOT count toward the rationale minimum' in second['prompt']
    assert 'unbracketed ref_id values are invalid' in second['prompt']
    prediction = dict(cp1(), predictions_t=[{'target_id': 'XOM', 'direction': 'UP',
        'snapshot_price': 100.0, 'target_price': 101.0, 'invalidation': 'XOM below subject price by target close.'}],
        trade_rationale='[1] ' + 'Synthetic consequence remains bound to the same subject baseline and horizon. ' * 20)
    answer.write_text(json.dumps(prediction))
    result = runtime.import_response(tmp_path, packet_path=Path(result['pending'][0]['packet_path']),
                                     response_path=answer, model='synthetic-fixture')['run']
    assert result['status'] == 'completed' and result['completed_count'] == 3
    run = tmp_path / 'state/runs/COMPACT'
    cp1_data = json.loads((run / 'artifacts/lab_decide.json').read_text())['data']
    cp2_data = json.loads((run / 'artifacts/lab_director.json').read_text())['data']
    assert validate_cp1(cp1_data).ok and validate_cp2(cp2_data, run).ok
    assert cp2_data['predictions_t'][0]['snapshot_time'] == '2015-08-03T20:00:00+00:00'
    assert cp2_data['predictions_t'][0]['target_time_iso'] == '2015-08-04T20:00:00+00:00'
    assert not (run / 'artifacts/lab_cross_corr_v2.json').exists()
    assert runtime.resume(tmp_path, 'COMPACT')['status'] == 'completed'
