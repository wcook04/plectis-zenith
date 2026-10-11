"""Static public graph export: native topology, freshness and disclosure boundaries."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from zenith import public_graph as demo
from scripts.build_demo_data import main
from system.core.governance import compute_waves
from system.core.loader import PhysicalLoader
from zenith.runtime import MISSION_TARGETS, scope_for


def test_public_projection_matches_native_graph_and_mission_closure():
    graph = PhysicalLoader(demo.ROOT).load_all_nodes()
    payload = demo.build()
    assert payload['schema'] == 'zenith_public_graph_v1'
    assert [node['id'] for node in payload['nodes']] == sorted(graph)
    assert payload['waves'] == compute_waves(graph)
    expected_edges = {(parent, node.id) for node in graph.values() for parent in node.dependencies}
    assert {(edge['source'], edge['target']) for edge in payload['edges']} == expected_edges
    assert payload['counts'] == {'nodes': len(graph), 'edges': len(expected_edges)}
    for node in payload['nodes']:
        assert set(node) == demo.NODE_FIELDS
        assert node['dependencies'] == sorted(graph[node['id']].dependencies)
        assert node['id'] in payload['waves'][node['wave']]
        assert node['label'] == demo.NODE_LABELS[node['id']]
        assert node['output_schema'] in demo.OUTPUTS
        assert node['output_shape'] == demo.OUTPUTS[node['output_schema']]
    assert {mission['id'] for mission in payload['missions']} == set(demo.GROUPS)
    for mission in payload['missions']:
        target = MISSION_TARGETS.get(mission['id'], 'surv_final_report_author')
        scope = scope_for(graph, target)
        assert mission['target'] == target
        assert mission['node_ids'] == sorted(scope)
        assert mission['waves'] == compute_waves({node_id: graph[node_id] for node_id in scope})
        assert {node_id for wave in mission['waves'] for node_id in wave} == scope
        # Every input is present in the mission projection, including upstream feeds.
        assert all(set(graph[node_id].dependencies) <= scope for node_id in scope)


def test_projection_is_deterministic_and_has_only_disclosed_fields():
    payload = demo.build()
    assert demo.canonical(payload) == demo.canonical(demo.build())
    assert set(payload) == {'schema', 'provenance', 'nodes', 'edges', 'missions', 'groups',
                            'waves', 'counts', 'claim_boundary'}
    assert set(payload['provenance']) == {'source', 'source_sha256', 'exporter_sha256', 'execution'}
    assert payload['provenance']['execution'] == 'static_no_run_state'
    assert all(set(edge) == {'source', 'target'} for edge in payload['edges'])
    assert all(set(mission) == {'id', 'label', 'target', 'node_ids', 'waves', 'availability'}
               for mission in payload['missions'])
    assert all(set(group) == {'id', 'label', 'description'} for group in payload['groups'])
    text = demo.canonical(payload)
    for private_marker in ('/Users/', '/home/', 'file://', 'api_key', 'prompt_sha256',
                           'requested_model', 'actual_model', 'snapshot_price', 'target_price',
                           'instruction', 'config_ref', 'runtime_context', 'work/', 'state/'):
        assert private_marker not in text


def test_loader_private_text_config_and_metadata_are_never_exported():
    graph = PhysicalLoader(demo.ROOT).load_all_nodes()
    expected = demo.build()
    changed = dict(graph)
    changed['lab_director'] = replace(graph['lab_director'],
        instruction='PRIVATE_PROMPT /Users/operator/secret',
        config={'api_key': 'PRIVATE_KEY', 'private_dossier': 'PRIVATE_DOSSIER'},
        meta={'teleology': 'PRIVATE_TELEOLOGY', 'description': 'PRIVATE_DESCRIPTION'})
    with patch.object(demo.PhysicalLoader, 'load_all_nodes', return_value=changed):
        actual = demo.build()
    assert actual == expected
    assert 'PRIVATE_' not in demo.canonical(actual)


def test_unreviewed_ids_and_interface_values_fail_closed():
    graph = PhysicalLoader(demo.ROOT).load_all_nodes()
    unknown = {**graph, 'unreviewed_node': replace(graph['lab_director'], id='unreviewed_node')}
    with patch.object(demo.PhysicalLoader, 'load_all_nodes', return_value=unknown):
        try:
            demo.build()
        except ValueError as error:
            assert 'node-label allowlist' in str(error)
        else:
            raise AssertionError('unknown node was disclosed')
    changed = dict(graph)
    changed['lab_director'] = replace(graph['lab_director'], output_schema='/Users/private/schema')
    with patch.object(demo.PhysicalLoader, 'load_all_nodes', return_value=changed):
        try:
            demo.build()
        except ValueError as error:
            assert 'schema allowlists' in str(error)
        else:
            raise AssertionError('unknown interface was disclosed')


def test_check_detects_missing_tampered_and_authored_source_drift(tmp_path):
    root = tmp_path / 'checkout'
    shutil.copytree(demo.ROOT / 'codex', root / 'codex')
    for name in demo.SOURCE_AUTHORITIES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((demo.ROOT / name).read_bytes())
    output = tmp_path / 'graph.json'
    args = ['--root', str(root), '--output', str(output)]
    assert main([*args, '--check']) == 1
    assert not output.exists()
    assert main(args) == 0
    assert main([*args, '--check']) == 0
    before = output.read_bytes()
    source = root / 'codex/substrate/nodes/lab/director.json'
    raw = json.loads(source.read_text())
    raw['meta']['private_sentinel'] = 'PRIVATE_SOURCE_SENTINEL'
    source.write_text(json.dumps(raw))
    assert main([*args, '--check']) == 1
    assert output.read_bytes() == before  # Check mode must never rewrite stale data.
    assert main(args) == 0
    assert 'PRIVATE_SOURCE_SENTINEL' not in output.read_text()
    assert json.loads(before)['provenance']['source_sha256'] != json.loads(output.read_text())['provenance']['source_sha256']
    assert main([*args, '--check']) == 0
    output.write_text(output.read_text() + ' ')
    assert main([*args, '--check']) == 1


def test_checked_in_export_is_current():
    assert demo.PUBLIC_GRAPH_PATH.as_posix() == 'data/graph/public-graph.json'
    output = demo.ROOT / demo.PUBLIC_GRAPH_PATH
    assert output.read_text() == demo.canonical(demo.build())
