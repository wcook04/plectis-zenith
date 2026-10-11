"""Build a static, positive-allowlist public graph projection for backend consumers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_GRAPH_PATH = Path('data/graph/public-graph.json')

from system.core.governance import compute_waves
from system.core.loader import PhysicalLoader
from zenith.runtime import MISSION_TARGETS, scope_for


GROUPS = {
    'feeds': ('Evidence feeds', 'Authored data-input and calculation nodes.'),
    'lab': ('Lab', 'Research and forecasts using the subject-side evidence available at issue time.'),
    'oracle': ('Oracle', 'Compare frozen forecasts with later observations and prepare hindsight feedback.'),
    'refinement': ('Refinement', 'Analyze feedback and prepare versioned learning updates.'),
    'surveillance': ('Surveillance', 'An authored monitoring graph requiring separate execution configuration.'),
}
LANES = {'STOCK': 'Stock', 'ETF': 'ETF', 'MACRO': 'Macro', 'NEWS': 'News',
         'POLYMARKET': 'Prediction market', 'STOCKGRID': 'Positioning',
         'CALCULATOR': 'Calculation', 'SPINE': 'Synthesis'}
OUTPUTS = {
    'text': 'Text artifact', 'json': 'Structured JSON artifact',
    'isomorphic_cp1': 'Structured thesis checkpoint',
    'isomorphic_cp2': 'Structured forecast checkpoint',
    'schema_cp2_critique': 'Structured forecast critique',
    'schema_prediction_reconciliation': 'Structured forecast reconciliation',
    'schema_realized_hindsight_brief': 'Structured hindsight brief',
}
NODE_LABELS = {
    'global_stock_feed': 'Stock prices', 'global_etf_feed': 'ETF prices',
    'global_macro_feed': 'Macro indicators', 'global_news_feed': 'News evidence',
    'global_polymarket_feed': 'Prediction markets', 'global_stockgrid_feed': 'Positioning evidence',
    'global_calculator_feed': 'Calculations', 'lab_seed_state': 'Research brief',
    'lab_cross_corr_v1': 'Cross-lane synthesis, pass 1', 'lab_cross_corr_v2': 'Cross-lane synthesis, pass 2',
    'lab_orient': 'Research orientation', 'lab_decide': 'CP1 thesis',
    'lab_director': 'CP2 forecasts', 'lab_integrity': 'Integrity audit',
    'oracle_subject_index': 'Original evidence index',
    'oracle_subject_lab_cross_corr_v2': 'Original cross-lane synthesis',
    'oracle_subject_lab_decide': 'Original CP1 thesis', 'oracle_subject_lab_director': 'Original CP2 forecasts',
    'oracle_truth_diff_equity': 'Observed price differences', 'oracle_truth_diff_macro': 'Observed macro differences',
    'oracle_truth_map': 'Hindsight reconstruction', 'oracle_attribution_map': 'Forecast critique',
    'oracle_explain': 'Reconciliation', 'oracle_cp2_emitter': 'Hindsight comparison',
    'delta_analyzer': 'Learning delta analysis', 'dossier_updater': 'Learning update proposal',
    'version_committer': 'Versioned learning update',
    'surv_macro_v1_synthesis': 'Monitoring synthesis, pass 1',
    'surv_macro_v1_context_search': 'Monitoring context search',
    'surv_macro_v2_structure': 'Monitoring synthesis, pass 2',
    'surv_final_report_author': 'Monitoring report',
}
for suffix, label in {'stock': 'Stock', 'etf': 'ETF', 'macro': 'Macro', 'news': 'News',
                      'poly': 'Prediction market', 'calc': 'Calculation', 'stockgrid': 'Positioning'}.items():
    NODE_LABELS[f'lab_miner_{suffix}'] = f'{label} analysis, pass 1'
    NODE_LABELS[f'lab_miner_v2_{suffix}'] = f'{label} analysis, pass 2'
    NODE_LABELS[f'oracle_subject_{suffix}_feed'] = f'Original {label.lower()} evidence'
    NODE_LABELS[f'oracle_truth_{suffix}'] = f'Hindsight {label.lower()} analysis'
    if suffix != 'etf':
        NODE_LABELS[f'surv_micro_v1_{suffix}'] = f'{label} monitoring, pass 1'
        NODE_LABELS[f'surv_micro_v2_{suffix}'] = f'{label} monitoring, pass 2'

NODE_FIELDS = frozenset({'id', 'label', 'description', 'type', 'group', 'lane',
                         'dependencies', 'output_schema', 'output_shape', 'wave'})
SOURCE_AUTHORITIES = ('system/core/loader.py', 'system/core/governance.py',
                      'system/core/engine.py', 'system/lib/types.py', 'zenith/runtime.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def source_sha256(root, manifest):
    """Hash authored nodes and native loading/scoping/wave authorities, never runs."""
    hashes = {f'node:{node_id}': hashlib.sha256(path.read_bytes()).hexdigest()
              for node_id, path in sorted(manifest.items())}
    hashes.update({f'authority:{name}': hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in SOURCE_AUTHORITIES})
    return hashlib.sha256(canonical(hashes).encode()).hexdigest()


def build(root=ROOT):
    root = Path(root).resolve()
    loader = PhysicalLoader(root)
    graph = loader.load_all_nodes()
    if set(graph) != set(NODE_LABELS):
        raise ValueError('Authored node inventory changed; review the public node-label allowlist before exporting.')
    waves = compute_waves(graph)
    wave_index = {node_id: index for index, wave in enumerate(waves) for node_id in wave}
    nodes = []
    for node_id, node in sorted(graph.items()):
        if node.group not in GROUPS or node.lane not in LANES or node.output_schema not in OUTPUTS or node.type.value not in {'tool', 'reasoning'}:
            raise ValueError('Node interface changed; review the public group/lane/type/schema allowlists.')
        nodes.append({'id': node_id, 'label': NODE_LABELS[node_id], 'description': GROUPS[node.group][1],
                      'type': node.type.value, 'group': node.group, 'lane': node.lane,
                      'dependencies': sorted(node.dependencies), 'output_schema': node.output_schema,
                      'output_shape': OUTPUTS[node.output_schema], 'wave': wave_index[node_id]})
    edges = [{'source': dependency, 'target': node.id} for node in sorted(graph.values(), key=lambda n: n.id)
             for dependency in sorted(node.dependencies)]
    missions = []
    for mission in ('lab', 'oracle', 'refinement', 'feeds', 'surveillance'):
        target = MISSION_TARGETS.get(mission, 'surv_final_report_author')
        scope = scope_for(graph, target)
        mission_waves = compute_waves({node_id: graph[node_id] for node_id in sorted(scope)})
        missions.append({'id': mission, 'label': GROUPS[mission][0], 'target': target,
                         'node_ids': sorted(scope), 'waves': mission_waves,
                         'availability': 'authored_requires_execution_configuration' if mission == 'surveillance' else 'native_plan_target'})
    return {'schema': 'zenith_public_graph_v1',
            'provenance': {'source': 'native authored graph', 'source_sha256': source_sha256(root, loader.manifest),
                           'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           'execution': 'static_no_run_state'},
            'nodes': nodes, 'edges': edges, 'missions': missions,
            'groups': [{'id': name, 'label': label, 'description': description} for name, (label, description) in GROUPS.items()],
            'waves': waves, 'counts': {'nodes': len(nodes), 'edges': len(edges)},
            'claim_boundary': 'This is the authored graph, not completed inference, forecast accuracy, or acceptance of a learned variant.'}
