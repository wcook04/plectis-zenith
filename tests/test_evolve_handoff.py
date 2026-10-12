"""Synthetic paired-run fixtures: export never impersonates completed learning."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from tools.refinement import run_evolve as ev


def paired(tmp_path):
    subject, truth = tmp_path/'LAB', tmp_path/'ORACLE'
    for p in (subject,truth):
        (p/'artifacts').mkdir(parents=True)
    (subject/'artifacts/lab_director.json').write_text('{"data":{"forecast":"synthetic test"}}')
    for name,_ in ev.ORACLE_ARTIFACTS:
        (truth/'artifacts'/f'{name}.json').write_text('{"data":{"fixture":true}}')
    return subject,truth


def test_export_pending_and_refuse_source_drift(tmp_path):
    subject,truth = paired(tmp_path)
    output = tmp_path/'packet.json'
    result = ev.export_agent_handoff(subject,truth,output)
    assert result['status'] == 'awaiting_agent_analysis'
    assert ev.verify_agent_handoff(output)['status'] == 'verified_pending_analysis'
    assert ev.export_agent_handoff(subject,truth,output) == result
    (truth/'artifacts/ideal_cp2.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='source changed'):
        ev.verify_agent_handoff(output)
    with pytest.raises(ValueError, match='differs'):
        ev.export_agent_handoff(subject,truth,output)


def test_missing_quartet_does_not_export(tmp_path):
    subject,truth = paired(tmp_path)
    (truth/'artifacts/ideal_cp2.json').unlink()
    output = tmp_path/'packet.json'
    assert ev.export_agent_handoff(subject,truth,output)['error'] == 'evolve_inputs_not_ready'
    assert not output.exists()


def test_no_bridge_never_writes_analysis_or_learning(tmp_path):
    subject,truth = paired(tmp_path)
    with patch.object(ev, '_append_learning_ledger') as ledger, patch.object(ev, '_apply_patches') as apply:
        result = ev.run_evolve(subject,truth,use_bridge=False)
    assert result['status'] == 'awaiting_agent_analysis'
    assert not (truth/'artifacts/evolve_delta_report.json').exists()
    assert not apply.called and not ledger.called


def test_readiness_state_is_bound_even_when_initially_absent(tmp_path):
    subject,truth = paired(tmp_path)
    output = tmp_path/'packet.json'
    ev.export_agent_handoff(subject,truth,output)
    (truth/'artifacts/feed_readiness_summary.json').write_text('{"ready":false}')
    with pytest.raises(ValueError, match='source changed'):
        ev.verify_agent_handoff(output)
    assert ev.export_agent_handoff(subject,truth,tmp_path/'new.json')['error'] == 'evolve_inputs_not_ready'


def test_self_hash_does_not_authorize_arbitrary_prompt_or_empty_bindings(tmp_path):
    import hashlib
    subject,truth = paired(tmp_path)
    output=tmp_path/'packet.json'
    ev.export_agent_handoff(subject,truth,output)
    original=json.loads(output.read_text())
    for changes in ({'source_hashes':{}}, {'prompt':'Arbitrary substituted prompt'}):
        payload={**original,**changes}
        payload.pop('packet_sha256')
        payload['packet_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        output.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            ev.verify_agent_handoff(output)
