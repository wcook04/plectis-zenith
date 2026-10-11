"""Exact graph/evidence contracts, including a live canonical graph consumer."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import check_semantics as semantic


class SemanticContractTests(unittest.TestCase):
    def certificate(self):
        return {'schema_version': 'zenith_graph_rank_certificate_v1',
                'node_ids': ['feed', 'lab', 'check'], 'ranks': {'feed': 0, 'lab': 1, 'check': 2},
                'edges': [{'dependency_id': 'feed', 'node_id': 'lab'}, {'dependency_id': 'lab', 'node_id': 'check'}],
                'condition': 'rank(dependency)<rank(node)'}

    def test_actual_canonical_graph_typed_certificate(self):
        spec = semantic.generate()
        receipt = semantic.validate_contract(spec, semantic.ROOT)
        self.assertTrue(receipt['ok'])
        self.assertGreaterEqual(receipt['node_count'], 71)
        self.assertGreaterEqual(receipt['edge_count'], 205)
        self.assertFalse(receipt['behavioral_semantics_verified'])
        lab = [s for s in spec['skills'] if s['forward_only']]
        self.assertTrue(lab)
        self.assertTrue(all(s['output_sort'] for s in lab))
        self.assertTrue(all(set(s['input_sorts']) == set(s['incoming_context_classes']) for s in lab))

    def test_backward_self_cycle_unknown_and_duplicate_edges_rejected(self):
        for source, target in [('check', 'feed'), ('lab', 'lab'), ('absent', 'lab')]:
            with self.subTest(edge=(source, target)):
                cert = self.certificate()
                cert['edges'].append({'dependency_id': source, 'node_id': target})
                with self.assertRaises(ValueError):
                    semantic.validate_rank_certificate(cert)
        cert = self.certificate()
        cert['edges'].append(cert['edges'][0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            semantic.validate_rank_certificate(cert)

    def test_forward_edge_insertion_passes(self):
        cert = self.certificate()
        cert['edges'].append({'dependency_id': 'feed', 'node_id': 'check'})
        self.assertEqual(semantic.validate_rank_certificate(cert)['edge_count'], 3)

    def test_rank_certificate_must_use_exact_natural_ranks(self):
        for value in (True, -1, 1.5):
            cert = self.certificate()
            cert['ranks']['lab'] = value
            with self.assertRaises(ValueError):
                semantic.validate_rank_certificate(cert)
        cert = self.certificate()
        cert['ranks']['invented'] = 0
        with self.assertRaises(ValueError):
            semantic.validate_rank_certificate(cert)

    def test_typed_ports_and_truth_edge_into_lab_rejected(self):
        original = semantic.generate()
        modified = copy.deepcopy(original)
        target = next(s for s in modified['skills'] if s['forward_only'] and s['input_sorts'])
        incoming = next(iter(target['input_sorts']))
        target['input_sorts'][incoming] = 'invented-incompatible-sort'
        with self.assertRaisesRegex(ValueError, 'input sort'):
            semantic.validate_contract(modified)
        modified = copy.deepcopy(original)
        target = next(s for s in modified['skills'] if s['forward_only'] and s['input_sorts'])
        incoming = next(iter(target['input_sorts']))
        target['incoming_context_classes'][incoming] = 'truth_side_evidence'
        with self.assertRaisesRegex(ValueError, 'forward-only'):
            semantic.validate_contract(modified)

    def test_canonical_source_hash_drift_and_false_boolean_rejected(self):
        original = semantic.generate()
        modified = copy.deepcopy(original)
        path = next(iter(modified['source_hashes']))
        modified['source_hashes'][path] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            semantic.validate_contract(modified, semantic.ROOT)
        modified = copy.deepcopy(original)
        modified['skills'][0]['forward_only'] = 'false'
        with self.assertRaisesRegex(ValueError, 'boolean'):
            semantic.validate_contract(modified)

    def test_cutoff_and_subject_truth_boundary(self):
        self.assertTrue(semantic.validate_evidence([{'available_at': 9, 'context_class': 'subject_side_evidence'}], cutoff=10)['ok'])
        with self.assertRaisesRegex(ValueError, 'after'):
            semantic.validate_evidence([{'available_at': 11, 'context_class': 'subject_side_evidence'}], cutoff=10)
        with self.assertRaisesRegex(ValueError, 'truth-side'):
            semantic.validate_evidence([{'available_at': 9, 'context_class': 'truth_side_evidence'}], cutoff=10)
        self.assertTrue(semantic.validate_evidence([{'available_at': 9, 'context_class': 'truth_side_evidence'}], cutoff=10, forward_only=False)['ok'])
        with self.assertRaisesRegex(ValueError, 'timezone'):
            semantic.validate_evidence([{'available_at': '2025-01-01T00:00:00', 'context_class': 'subject_side_evidence'}], cutoff=10)

    def test_iso_timestamps_map_to_same_natural_cutoff(self):
        receipt = semantic.validate_evidence([{'available_at': '2025-01-01T12:00:00+01:00',
                                               'context_class': 'subject_side_evidence'}], cutoff='2025-01-01T11:00:00Z')
        self.assertTrue(receipt['ok'])
        for bad in (True, -1, '2025-01-01T00:00:00.5Z'):
            with self.assertRaises(ValueError):
                semantic.parse_time(bad)

    def test_lean_generator_uses_exact_checked_rank_certificate(self):
        cert = self.certificate()
        source = semantic.lean_instance(cert)
        self.assertIn('ranks : Array Nat := #[0, 1, 2]', source)
        self.assertIn('edges : List (Vertex × Vertex) := [((0, 0), (1, 1)), ((1, 1), (2, 2))]', source)
        self.assertIn('rank_checks_sound certificate_valid', source)
        self.assertNotIn('sorry', source)
        cert['edges'].append({'dependency_id': 'check', 'node_id': 'feed'})
        with self.assertRaises(ValueError):
            semantic.lean_instance(cert)

    def test_lean_receipt_refuses_axiom_dependencies(self):
        def runner(args, **kwargs):
            if args[:3] == ['elan', 'toolchain', 'list']:
                return mock.Mock(stdout=semantic.TOOLCHAIN + '\n')
            return mock.Mock(returncode=0, stdout="'test' depends on axioms: [propext]", stderr='')
        with mock.patch.object(semantic.shutil, 'which', return_value='/mock/elan'):
            with mock.patch.object(semantic.subprocess, 'run', side_effect=runner):
                with self.assertRaisesRegex(ValueError, 'axiom-free'):
                    semantic.check_lean(self.certificate())

    def test_general_lean_source_has_no_unproved_declarations(self):
        source = (semantic.ROOT / 'formal/ZenithSemantics.lean').read_text()
        self.assertNotRegex(source, r'(?m)^\s*(axiom|sorry|admit)\b')
        for name in ('composition_refines', 'composition_contract', 'safe_context_append',
                     'ranked_graph_acyclic', 'insert_edge_preserves_rank', 'checked_refines'):
            self.assertIn(f'theorem {name}', source)


if __name__ == '__main__':
    unittest.main()
