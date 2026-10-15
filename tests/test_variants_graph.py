"""Frozen topology experiments run through the existing engine and validators."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from system.core.engine import GodModeEngine, LogicalFailure
from system.core.loader import PhysicalLoader
from system.lib.types import StepStatus
from variants.graph import FrozenGraphLoader, apply_graph_variant, variant_sha256

ROOT = Path(__file__).resolve().parents[1]


class _Capture:
    def __init__(self):
        self.manager = self
        self.calls = []

    def ask_ai(self, prompt, config=None, cancel=None):
        self.calls.append((config["meta"]["node_id"], prompt))
        return "INSERTED_CHECK: source uncertainty retained." if config["meta"]["node_id"] == "lab_evidence_check" else "{}"

    def close(self, terminate_browser=False):
        pass


class GraphVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = PhysicalLoader(ROOT, inject_sys_path=False)
        cls.graph = cls.loader.load_all_nodes()
        cls.example = json.loads((ROOT / "examples/variants/lab_evidence_check.json").read_text())

    def payload(self, operations):
        payload = deepcopy(self.example)
        payload["operations"] = operations
        payload["variant_sha256"] = variant_sha256(payload)
        return payload

    def test_full_graph_scope_contracts_and_rank_certificate(self):
        loader = FrozenGraphLoader(self.loader, self.example)
        graph = loader.load_all_nodes()
        self.assertEqual(len(graph), len(self.graph) + 1)
        self.assertIn("lab_evidence_check", graph["lab_decide"].dependencies)
        self.assertNotIn("lab_orient", graph["lab_decide"].dependencies)
        for node_id in ("lab_decide", "lab_director", "lab_integrity"):
            self.assertEqual(replace(graph[node_id], dependencies=self.graph[node_id].dependencies), self.graph[node_id])
        scope = SimpleNamespace(_universe=graph, logger=SimpleNamespace(info=lambda *args: None))
        GodModeEngine._resolve_execution_scope(scope, "lab_decide")
        self.assertEqual(len(scope._execution_scope), 26)
        self.assertIn("lab_integrity", scope._execution_scope)
        self.assertEqual(len(loader.receipt["waves"]), 12)
        cert = loader.receipt["acyclic_certificate"]
        self.assertTrue(all(cert["ranks"][edge["dependency_id"]] < cert["ranks"][edge["node_id"]] for edge in cert["edges"]))
        graph["lab_evidence_check"].meta["reasoning_contract"]["role_contract"]["role_class"] = "changed"
        self.assertEqual(loader.load_node("lab_evidence_check").meta["reasoning_contract"]["role_contract"]["role_class"], "critic")

    def test_inserted_skill_executes_and_reaches_actual_cp1_prompt(self):
        loader = FrozenGraphLoader(self.loader, self.example)
        capture = _Capture()
        with tempfile.TemporaryDirectory() as directory:
            engine = GodModeEngine("variant-execution", root_dir=directory, loader=loader, bridge=capture)
            engine._universe = loader.load_all_nodes()
            orient = engine._universe["lab_orient"]
            engine._write_artifact(orient, StepStatus.SUCCESS, {}, "Forward subject draft.")
            engine._execute_node("lab_evidence_check")
            artifact = json.loads((engine.artifacts_dir / "lab_evidence_check.json").read_text())
            self.assertEqual(artifact["status"], StepStatus.SUCCESS.value)
            with self.assertRaises(LogicalFailure):
                engine._execute_node("lab_decide")
            node_id, prompt = capture.calls[-1]
            self.assertEqual(node_id, "lab_decide")
            self.assertIn("INSERTED_CHECK", prompt)
            self.assertIn("<lab_evidence_check>", prompt)
            self.assertNotIn("<lab_orient>", prompt)
            failure = json.loads((engine.artifacts_dir / "lab_decide.json").read_text())
            self.assertEqual(failure["status"], StepStatus.FAILURE.value)
            self.assertEqual(engine._universe["lab_decide"].output_schema, "isomorphic_cp1")

    def test_cycle_and_dangling_edge_refused(self):
        for operation in [
            {"op": "add_edge", "dependency_id": "lab_decide", "node_id": "lab_orient"},
            {"op": "add_edge", "dependency_id": "absent", "node_id": "lab_decide"},
        ]:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                apply_graph_variant(self.graph, self.payload([operation]), root=ROOT)

    def test_mandatory_ancestry_and_feed_tool_mutation_refused(self):
        for operation in [
            {"op": "remove_edge", "dependency_id": "lab_orient", "node_id": "lab_decide"},
            {"op": "add_edge", "dependency_id": "lab_orient", "node_id": "global_derived_feed"},
            {"op": "remove_experimental_node", "node_id": "lab_integrity"},
        ]:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                apply_graph_variant(self.graph, self.payload([operation]), root=ROOT)

    def test_transitive_oracle_truth_cannot_enter_lab(self):
        operations = deepcopy(self.example["operations"])
        check = operations[0]["node"]
        check["dependencies"].append("oracle_cp2_emitter")
        check["meta"]["reasoning_contract"]["input_contract"]["required_artifacts"].append("oracle_cp2_emitter")
        with self.assertRaisesRegex(ValueError, "truth contamination"):
            apply_graph_variant(self.graph, self.payload(operations), root=ROOT)
        # The existing Oracle node sits behind the check; it never appears as a direct CP1 edge.
        self.assertNotIn("oracle_cp2_emitter", self.graph["lab_decide"].dependencies)

    def test_source_and_variant_identity_drift_refused(self):
        drift = deepcopy(self.example)
        drift["operations"][0]["node"]["instruction"] += " changed"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            apply_graph_variant(self.graph, drift, root=ROOT)
        changed_graph = dict(self.graph)
        changed_graph["lab_orient"] = replace(changed_graph["lab_orient"], instruction="source drift")
        with self.assertRaisesRegex(ValueError, "base source drift"):
            apply_graph_variant(changed_graph, self.example, root=ROOT)

    def test_unknown_fields_invalid_contracts_and_dynamic_calls_refused(self):
        modifications = [
            lambda node: node.update(unknown_field=True),
            lambda node: node.update(type="tool"),
            lambda node: node.update(config={"module": "tools.refinement.version_committer"}),
            lambda node: node["execution"].update(tools=["web_search"]),
            lambda node: node["meta"]["reasoning_contract"]["output_contract"].update(schema_or_standard="private.schema"),
            lambda node: node["meta"]["reasoning_contract"]["side_effect_contract"].update(commit_allowed=True),
        ]
        for modification in modifications:
            operations = deepcopy(self.example["operations"])
            modification(operations[0]["node"])
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                apply_graph_variant(self.graph, self.payload(operations), root=ROOT)
