"""Exercise the agent-facing reflection commands using native synthetic feedback."""
import contextlib
import io
import json

import pytest

from feedback.demo import run as feedback_demo
from research.__main__ import main
from system.lib.reasoning_policy import validate_reasoning_policy
from zenith import runtime


def write(path, payload):
    path.write_text(json.dumps(payload))
    return path


def call(args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        assert main([str(arg) for arg in args]) == 0
    return json.loads(stream.getvalue())


def test_native_feedback_to_cli_candidate_preserves_evidence(tmp_path):
    store = tmp_path / 'feedback'
    evidence = feedback_demo(store)
    proposal_id = evidence['candidate_feedback_proposals'][0]['proposal_id']
    proposal = store / 'proposals' / f'{proposal_id}.json'
    source = json.loads(proposal.read_text())
    scope = write(tmp_path / 'scope.json', {
        'schema': 'zenith_reflection_scope_v1', 'as_of': '2026-03-01T00:00:00Z',
        'development_run_ids': sorted({row['issue_run_id'] for row in source['evidence']}),
        'heldout_run_ids': [],
    })
    packet = tmp_path / 'packet.json'
    result = call(['reflection-packet', '--proposal', proposal, '--scope', scope, '--output', packet])
    assert result['state'] == 'reflection_ready'
    assert json.loads(packet.read_text())['proposal']['evidence'] == source['evidence']
    edit = write(tmp_path / 'edit.json', {
        'node_id': 'lab_director', 'parameter': 'skill_addon',
        'value': 'Compare each proposed target with the no-change baseline.',
        'hypothesis': 'An explicit baseline comparison reduces target-price error.',
        'variant_id': 'baseline-comparison',
    })
    output = tmp_path / 'candidate'
    result = call(['reflection-candidate', '--packet', packet, '--edit', edit, '--output', output])
    assert result['live_mutation_permission'] is False
    policy = json.loads((output / 'policy.json').read_text())
    validate_reasoning_policy(policy, runtime.load_graph(runtime.DEFAULT_ROOT))
    assert policy['nodes']['lab_director']['skill_addon'] == json.loads(edit.read_text())['value']
    assert json.loads((output / 'candidate.json').read_text())['state'] == 'review_only'
    original = (output / 'candidate.json').read_bytes()
    with pytest.raises(SystemExit) as error:
        main(['reflection-candidate', '--packet', str(packet), '--edit', str(edit), '--output', str(output)])
    assert error.value.code == 2
    assert (output / 'candidate.json').read_bytes() == original
    # A fresh destination does not make changed source evidence admissible.
    proposal.write_text(proposal.read_text() + ' ')
    rejected = tmp_path / 'rejected'
    with pytest.raises(SystemExit) as error:
        main(['reflection-candidate', '--packet', str(packet), '--edit', str(edit), '--output', str(rejected)])
    assert error.value.code == 2
    assert not rejected.exists()


def test_reflection_cli_rejects_scope_override_without_writing(tmp_path):
    output = tmp_path / 'packet.json'
    with pytest.raises(SystemExit) as error:
        main(['reflection-packet', '--proposal', 'unused', '--scope', 'unused',
              '--as-of', '2026-03-01T00:00:00Z', '--output', str(output)])
    assert error.value.code == 2
    assert not output.exists()
