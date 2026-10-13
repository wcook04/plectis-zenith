"""Bounded adaptive profile executed by the native engine's node lifecycle.

The DAG is a finite expansion of an action/result loop. Later reasoning slots
consume earlier receipts; after commit the unused slots are explicitly inactive.
No inference, retries, artifact writing or validation bypasses the native engine.
"""
from pathlib import Path
import json
from jsonschema import Draft202012Validator
from system.core.engine import GodModeEngine
from system.lib.types import CodexNode, NodeType
from system.lib.schema_validator import ValidationResult
from system.lib.reasoning_policy import investigation_policy
from .providers import write_json, digest, text_digest
from .basket_panel import InvestigationStore
from .investigator_contracts import (PROFILE, REVIEW_CONTRACT, MAX_TURNS, MAX_COMPARISONS, DEFAULT_PROCEDURE,
    LAB_INSTRUCTION, REVIEW_INSTRUCTION, action_schema, review_schema)

TARGETS = {"lab":"investigator_final", "refinement":"investigator_review"}


def read(directory, name):
    return json.loads((Path(directory)/"artifacts"/(name+".json")).read_text())["data"]


class InvestigatorGraphLoader:
    def load_all_nodes(self):
        graph = {}
        def add(nid, kind, dependencies=(), instruction="", group="lab", feed=False):
            graph[nid] = CodexNode(id=nid, type=kind, group=group, dependencies=tuple(dependencies),
                instruction=instruction, output_schema="json", meta={"task_profile":PROFILE,"is_feed":feed},
                execution={"retries":1,"tools":[],"timeout":240,"cache_policy":"none"})
        add("investigator_case", NodeType.TOOL, feed=True)
        previous = ["investigator_case"]
        for i in range(1, MAX_TURNS+1):
            turn, result = f"investigator_turn_{i:02}", f"investigator_result_{i:02}"
            add(turn, NodeType.REASONING, previous, LAB_INSTRUCTION)
            add(result, NodeType.TOOL, [*previous,turn])
            previous.append(result)
        add("investigator_final", NodeType.TOOL, previous)
        add("investigator_review_feed", NodeType.TOOL, group="refinement", feed=True)
        add("investigator_review", NodeType.REASONING, ["investigator_review_feed"], REVIEW_INSTRUCTION, group="refinement")
        return graph


class InvestigatorEngine(GodModeEngine):
    def _store(self):
        if not hasattr(self,"_investigation_store"):
            self._investigation_store = InvestigationStore(read(self.run_dir,"investigator_case"))
        return self._investigation_store

    def _history(self, node):
        return {nid:read(self.run_dir,nid) for nid in node.dependencies if nid.startswith("investigator_result_") and
                not read(self.run_dir,nid).get("inactive")}

    def _gather_inputs(self, node):
        if node.id.startswith("investigator_turn_"):
            history = self._history(node)
            return {"case":{"data":self._store().context()},
                **{nid:{"data":value} for nid,value in history.items()},
                "execution_limits":{"data":{"turn":int(node.id[-2:]),"maximum_turns":MAX_TURNS,
                    "comparisons_remaining":MAX_COMPARISONS-sum(r["action"]["kind"]=="compare" for r in history.values())}}}
        # No generic legacy feed compression applies to this separately versioned profile.
        return {nid:json.loads((self.artifacts_dir/(nid+".json")).read_text()) for nid in node.dependencies}

    def _options(self, history):
        return [c for row in history.values() for c in row["receipt"].get("candidates",[])]

    def prepare_reasoning_prompt(self, node, inputs=None, config=None):
        inputs = self._gather_inputs(node) if inputs is None else inputs
        prompt,config = super().prepare_reasoning_prompt(node,inputs,config)
        if node.id == "investigator_review":
            packet = inputs["investigator_review_feed"]["data"]
            feedback = bool(packet["repair_history"])
            schema = review_schema(list(packet["subject"]["graph"]),packet["baskets"],feedback)
            system = REVIEW_INSTRUCTION+"\nCONTRACT: "+REVIEW_CONTRACT
            if feedback:
                system += "\nACTIVE TASK NOW: assess the tested proposal using repair_history at the start of the input. This is NOT a fresh initial diagnosis. State what the control and candidate actually did, including unchanged results, then reject, revise, retain_for_evaluation or no_change. A repeated initial proposal is not a continuation. Check the code-owned decision_audit before asserting numerical ordering; the default reference is advisory, not a requirement to minimize every displayed MSE. If your earlier diagnosis is contradicted, withdraw it explicitly. Do not infer semantic success from a signature alone."
            else:
                system += "\nCheck the code-owned decision_audit before attributing a selection error. The default is advisory; departing from its minimum is not automatically defective."
        else:
            history = self._history(node)
            schema = action_schema(self._store().baskets,["case",*history],
                [*self._store().options,*[c["candidate_id"] for c in self._options(history)]],int(node.id[-2:])==MAX_TURNS,
                sum(r["action"]["kind"]=="compare" for r in history.values()) < MAX_COMPARISONS)
            policy = self.investigation_policy
            system = LAB_INSTRUCTION+"\nACTIVE REPLACEMENT PROCEDURE:\n"+policy["procedure"]
            prompt += "\nACTIVE_PROCEDURE\n"+json.dumps(policy,ensure_ascii=False)
        prompt += "\nRESPONSE_SCHEMA\n"+json.dumps(schema,separators=(",",":"))
        if len(prompt.encode()) > 1_200_000:
            raise ValueError("investigator prompt exceeds explicit byte cap; no content was silently dropped")
        self._schemas = getattr(self,"_schemas",{})
        self._schemas[node.id] = schema
        write_json(self.artifacts_dir/"context"/(node.id+".json"),{"inputs":inputs,"prompt":prompt,
            "system_prompt":system,"schema":schema,"prompt_sha256":text_digest(prompt),
            "system_prompt_sha256":text_digest(system),"prompt_utf8_bytes":len(prompt.encode())})
        return prompt,{**config,"system_prompt":system,"response_format":{"type":"json_schema",
            "json_schema":{"name":node.id,"strict":True,"schema":schema}}}

    def _validate_schema_output(self,node,output_schema,parsed):
        try:
            Draft202012Validator(self._schemas[node.id]).validate(parsed)
            if node.id == "investigator_review":
                packet = read(self.run_dir,"investigator_review_feed")
                if not packet["repair_history"] and parsed["disposition"] not in ("propose","no_change"):
                    raise ValueError("initial review may propose or decline; continuation decisions require repair history")
                change = parsed["disposition"] in ("propose","revise")
                if change != bool(parsed["replacement_procedure"].strip()):
                    raise ValueError("only propose/revise supplies an exact replacement")
                if change and (not parsed["witness_steps"] or parsed["expected_effect"]["action"]=="none"):
                    raise ValueError("proposal needs a witness and observable effect")
                if parsed["disposition"]=="revise" and parsed["replacement_procedure"]==packet["repair_history"][-1]["proposal"]["replacement_procedure"]:
                    raise ValueError("revision is identical to the tested procedure; use a continuation disposition")
            else:
                action = parsed["action"]
                history = self._history(node)
                if action["kind"] == "commit":
                    self._store().commit(action["candidate_ids"],self._options(history))
                if action["kind"] == "compare" and sum(r["action"]["kind"]=="compare" for r in history.values()) >= MAX_COMPARISONS:
                    raise ValueError("aggregate comparison allowance exhausted")
        except Exception as exc:
            return ValidationResult.failure([str(exc)])
        return ValidationResult.success()

    def _exec_reasoning(self,node,inputs,config):
        if node.id.startswith("investigator_turn_") and any(row["action"]["kind"]=="commit" for row in self._history(node).values()):
            return {"inactive":True,"model_call":False},{"inactive":True,"reason":"already committed"}
        meta,data = super()._exec_reasoning(node,inputs,config)
        meta["investigator_schema_validated"] = PROFILE
        if node.id == "investigator_review" and data["disposition"] in ("propose","revise"):
            incumbent = inputs["investigator_review_feed"]["data"]["incumbent_policy"]
            policy = investigation_policy(data["replacement_procedure"],incumbent["policy_sha256"])
            write_json(self.run_dir/"candidate_policy.json",policy)
        return meta,data

    def _exec_tool(self,node,inputs,config):
        if node.meta.get("is_feed"):
            return super()._exec_tool(node,inputs,config)
        history = self._history(node)
        if node.id == "investigator_final":
            commits = [row["receipt"] for row in history.values() if row["action"]["kind"]=="commit"]
            if len(commits) != 1:
                raise ValueError("action allowance exhausted without exactly one commitment")
            graph = {"investigator_case":[]}
            for nid in history:
                turn = nid.replace("result","turn")
                graph[turn] = ["investigator_case",*[p for p in history if p<nid]]
                graph[nid] = [*graph[turn],turn]
            graph[node.id] = ["investigator_case",*history]
            write_json(self.run_dir/"execution_graph.json",{"schema":"zenith_investigator_execution_v1",
                "profile":PROFILE,"nodes":graph,"actual_model_calls":len(history),
                "inactive_slots":MAX_TURNS-len(history),"dependency_basis":"actual supplied contexts, not self-reported citations"})
            return {},{**commits[0],"target_time":self._target_time_iso,"policy_sha256":self.investigation_policy["policy_sha256"],
                "action_count":len(history),"comparison_count":sum(r["action"]["kind"]=="compare" for r in history.values())}
        turn = node.id.replace("result","turn")
        decision = read(self.run_dir,turn)
        if decision.get("inactive"):
            return {"inactive":True},{"inactive":True,"reason":"already committed"}
        action = decision["action"]
        if action["kind"] == "inspect":
            receipt = self._store().inspect(action["source"])
        elif action["kind"] == "compare":
            sequence = 1+sum(r["action"]["kind"]=="compare" for r in history.values())
            receipt = self._store().compare(action["source"],action["quantity"],sequence)
        else:
            receipt = self._store().commit(action["candidate_ids"],self._options(history))
        return {},{"action":action,"decision":decision,"receipt":receipt,"receipt_sha256":digest(receipt)}

    def _calculate_run_grade(self):
        for nid in self._execution_scope:
            path = self.artifacts_dir/(nid+".json")
            if not path.exists() or json.loads(path.read_text()).get("status") not in ("success","loaded"):
                return "red","missing or failed native investigator artifact: "+nid
        return "green","native investigator contracts passed; usefulness remains empirical"

    def _write_lab_contract_audit(self):
        failures = [nid for nid,status in self._node_outcomes.items() if status=="failure"]
        report = {"task_profile":PROFILE,"hard_fails":failures,"boundary":"structural execution, not semantic correctness"}
        write_json(self.artifacts_dir/"lab_contract_audit.json",{"status":"success","data":report})
        return report


def subject_record(directory):
    directory = Path(directory)
    manifest = json.loads((directory/"zenith_run.json").read_text())
    graph = json.loads((directory/"execution_graph.json").read_text())["nodes"]
    return {"run_id":directory.name,"manifest":manifest,"graph":graph,
        "contexts":{p.stem:json.loads(p.read_text()) for p in sorted((directory/"artifacts/context").glob("*.json"))},
        "outputs":{nid:read(directory,nid) for nid in graph if nid!="investigator_case"},
        "commitment":read(directory,"investigator_final")}
