"""Frozen policy integration uses the real engine and preserves source artifacts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from system.core.engine import GodModeEngine
from system.lib.reasoning_policy import apply_reasoning_policy, policy_sha256, validate_reasoning_policy
from system.lib.types import CodexNode, NodeType, StepStatus


class _Bridge:
    def __init__(self):
        self.manager = self
        self.prompts = []

    def ask_ai(self, prompt, config=None, cancel=None):
        self.prompts.append(prompt)
        return "accepted text"

    def close(self, terminate_browser=False):
        pass


class ReasoningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.node = CodexNode("target", NodeType.REASONING, dependencies=("a", "b"), instruction="BASE CONTRACT")
        self.graph = {"target": self.node, "a": CodexNode("a", NodeType.REASONING), "b": CodexNode("b", NodeType.REASONING)}
        self.inputs = {"a": {"data": "A" * 2000}, "b": {"data": "B" * 2000}}

    def policy(self, **row):
        policy = {"variant_id": "weighted-v1", "nodes": {"target": row}}
        policy["policy_sha256"] = policy_sha256(policy)
        return policy

    def test_weighted_excerpts_are_valid_explicit_and_preserve_inputs(self):
        policy = self.policy(incoming_weights={"a": 3, "b": 1}, max_context_chars=256)
        before = deepcopy(self.inputs)
        views, addon, receipt = apply_reasoning_policy(self.node, self.inputs, validate_reasoning_policy(policy, self.graph))
        self.assertEqual(self.inputs, before)
        self.assertEqual(receipt["retained_source_chars"], 256)
        self.assertEqual(views["a"]["retained_source_chars"], 192)
        self.assertEqual(views["b"]["retained_source_chars"], 64)
        self.assertEqual(receipt["excerpt_dependency_ids"], ["a", "b"])
        json.loads(json.dumps(views))
        self.assertEqual(receipt, apply_reasoning_policy(self.node, self.inputs, policy)[2])

    def test_zero_weight_has_explicit_omission_and_original_hash(self):
        policy = self.policy(incoming_weights={"b": 0})
        views, _, receipt = apply_reasoning_policy(self.node, self.inputs, policy)
        self.assertEqual(views["a"], self.inputs["a"])
        self.assertEqual(views["b"]["context_policy_view"], "omitted")
        self.assertEqual(len(views["b"]["original_sha256"]), 64)
        self.assertEqual(receipt["omitted_dependency_ids"], ["b"])

    def test_invalid_policy_refused(self):
        cases = [
            self.policy(incoming_weights={"truth": 1}),
            self.policy(incoming_weights={"a": -1}),
            self.policy(max_context_chars=1),
            self.policy(unknown_field=True),
            self.policy(skill_addon="x" * 513),
        ]
        drift = self.policy(skill_addon="before")
        drift["nodes"]["target"]["skill_addon"] = "after"
        cases.append(drift)
        unknown = self.policy()
        unknown["nodes"]["absent"] = {}
        unknown["policy_sha256"] = policy_sha256(unknown)
        cases.append(unknown)
        for case in cases:
            with self.subTest(policy=case), self.assertRaises(ValueError):
                validate_reasoning_policy(case, self.graph)
        invalid_weight = self.policy()
        invalid_weight["nodes"]["target"]["incoming_weights"] = {"a": float("inf")}
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_reasoning_policy(invalid_weight, self.graph)

    def test_real_engine_prompt_policy_and_content_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "master_config.json").write_text("{}")
            nodes = root / "codex/substrate/nodes/test"
            nodes.mkdir(parents=True)
            for node in self.graph.values():
                (nodes / f"{node.id}.json").write_text(json.dumps({"id": node.id, "type": "reasoning", "instruction": node.instruction, "dependencies": list(node.dependencies)}))
            bridge = _Bridge()
            policy = self.policy(incoming_weights={"b": 0}, skill_addon="Respect counterevidence.")
            engine = GodModeEngine("policy-test", root_dir=str(root), bridge=bridge, reasoning_policy=policy)
            originals = {}
            for edge, envelope in self.inputs.items():
                path = engine.artifacts_dir / f"{edge}.json"
                path.write_text(json.dumps(envelope))
                originals[path] = path.read_bytes()
            prompt, config = engine.prepare_reasoning_prompt(self.node, deepcopy(self.inputs), {})
            self.assertIn("BASE CONTRACT", prompt)
            self.assertIn("Respect counterevidence.", prompt)
            self.assertIn("remain binding", prompt)
            self.assertIn('"context_policy_view":"omitted"', prompt)
            self.assertIn("[CONTEXT_POLICY_RECEIPT]", prompt)
            self.assertEqual(config["meta"]["node_id"], "target")
            self.assertEqual(engine.prepare_reasoning_prompt(self.node, deepcopy(self.inputs), {})[0], prompt)
            self.assertEqual(len(list((engine.artifacts_dir / "context_policy").glob("*.json"))), 1)
            metadata, response = engine._exec_reasoning(self.node, deepcopy(self.inputs), {})
            self.assertEqual(bridge.prompts, [prompt])
            self.assertEqual(response, "accepted text")
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)
            policy["nodes"]["target"]["skill_addon"] = "external mutation"
            self.assertEqual(engine.prepare_reasoning_prompt(self.node, deepcopy(self.inputs), {})[0], prompt)

    def test_absent_policy_preserves_exact_prompt_view(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = GodModeEngine("no-policy", root_dir=directory, bridge=_Bridge())
            prompt, _ = engine.prepare_reasoning_prompt(self.node, self.inputs, {})
            self.assertNotIn("CONTEXT_POLICY_RECEIPT", prompt)
            self.assertNotIn("LEARNED_SKILL_TAKEAWAY", prompt)
            self.assertIn("A" * 2000, prompt)
            self.assertIn("B" * 2000, prompt)

    def test_cached_result_cannot_cross_policy_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nodes = root / "codex/substrate/nodes/test"
            nodes.mkdir(parents=True)
            for node in self.graph.values():
                (nodes / f"{node.id}.json").write_text(json.dumps({"id": node.id, "type": "reasoning", "dependencies": list(node.dependencies)}))
            policy = self.policy(skill_addon="first variant")
            engine = GodModeEngine("cache", root_dir=directory, bridge=_Bridge(), reasoning_policy=policy)
            engine._write_artifact(self.node, StepStatus.SUCCESS, {}, "answer")
            self.assertTrue(engine._is_completed(self.node))
            changed = self.policy(skill_addon="second variant")
            engine._reasoning_policy = validate_reasoning_policy(changed, self.graph)
            self.assertFalse(engine._is_completed(self.node))
            engine._reasoning_policy = None
            self.assertFalse(engine._is_completed(self.node))
