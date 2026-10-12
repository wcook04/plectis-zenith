"""The shared, versioned reasoning ontology for the financial task profile.

JSON Schema validates structure; code-owned evidence IDs bind stated evidence
to the actual prompt inputs. Neither check certifies the truth of an inference.
"""
import json
from jsonschema import Draft202012Validator
from .providers import digest

VERSION="zenith.reasoning.v3"


def obj(properties, required=None):
    return {"type":"object","properties":properties,"required":list(properties) if required is None else required,
            "additionalProperties":False}


def arr(items, minimum=0, maximum=12):
    return {"type":"array","items":items,"minItems":minimum,"maxItems":maximum}


TEXT={"type":"string","minLength":1,"maxLength":6000}
TEXTS=arr(TEXT)
EVIDENCE_ID={"type":"string","pattern":"^E[0-9a-f]{6}_[0-9]{3,5}$"}
REFS=arr(EVIDENCE_ID)
CLAIM=obj({"id":{"type":"string","pattern":"^C[1-9][0-9]*$"},
    "kind":{"enum":["observation","hypothesis","inference","limitation","decision","diagnosis"]},
    "statement":TEXT,"evidence_refs":REFS,"certainty":{"enum":["observed","supported","tentative","unknown"]}})
DISTINCTION=obj({"id":{"type":"string","pattern":"^D[1-9][0-9]*$"},"question":TEXT,
    "alternatives":arr(TEXT,2,4),"status":{"enum":["unresolved","supported","rejected"]},"evidence_refs":REFS})
CATEGORIES=["evidence_absent","evidence_discarded","inference_error","numerical_model_error",
            "irreducible_uncertainty","no_supported_failure"]
ATTRIBUTION=obj({"node_id":TEXT,"category":{"enum":CATEGORIES},"evidence_ref":EVIDENCE_ID,
    "claim":TEXT,"feasible_test":TEXT,"uncertainty":TEXT})
REPAIR=obj({"node_id":TEXT,"skill_addon":{"type":"string","minLength":1,"maxLength":512},
    "evidence_ref":EVIDENCE_ID,"hypothesis":TEXT,"expected_effect":TEXT})
QUERY=obj({"target":{"enum":[f"B{i:02}" for i in range(1,7)]},
    "source":{"enum":[f"B{i:02}" for i in range(1,7)]+["ALL","INDEX"]},
    "operation":{"enum":["trend","breadth","volume","lag"]},"lag":{"enum":[0,1,5,20]},
    "reason":TEXT})
STAGES={
    "inventory":obj({"available_views":TEXTS,"missing_inputs":TEXTS}),
    "extract":obj({"questions":TEXTS}),
    "synthesize":obj({"priority_distinctions":TEXTS}),
    "orient":obj({"proposed_tests":TEXTS}),
    "plan":obj({"queries":arr(QUERY,6,6)}),
    "investigate":obj({"candidate_id":{"type":"string","pattern":"^Q[1-6]$"},
        "verdict":{"enum":["supports","contradicts","inconclusive"]},"reason":TEXT}),
    "decide":obj({"selected_candidates":{**arr({"type":"string","pattern":"^Q[1-6]$"},0,6),"uniqueItems":True},"rationale":TEXTS}),
    "audit":obj({"issues":TEXTS}),
    "review":obj({"attributions":arr(ATTRIBUTION,0,6)}),
    "attribute":obj({"attributions":arr(ATTRIBUTION,0,6)}),
    "explain":obj({"assessments":arr(obj({"node_id":TEXT,"status":{"enum":["supported","challenged","unresolved"]},"reason":TEXT}),0,6)}),
    "repair_proposals":obj({"repair_candidates":arr(REPAIR,0,3),"failure_summary":TEXTS}),
    "select_repair":obj({"node_id":TEXT,"evidence_ref":EVIDENCE_ID,"hypothesis":TEXT,"expected_effect":TEXT,"alternative_explanation":TEXT}),
    "write_repair":REPAIR,
}


def stage_for(node_id):
    if node_id.startswith("lab_miner_v2_"): return "investigate"
    if node_id.startswith("lab_miner_"): return "extract"
    if node_id.startswith("lab_cross_corr_"): return "synthesize"
    if node_id.startswith("oracle_truth_"): return "review"
    return {"lab_seed_state":"inventory","lab_orient":"orient","lab_decide":"plan",
        "lab_director":"decide","lab_integrity":"audit","oracle_attribution_map":"attribute",
        "oracle_explain":"explain","oracle_cp2_emitter":"repair_proposals",
        "delta_analyzer":"select_repair","dossier_updater":"write_repair"}[node_id]


def schema_for(node_id, *, persisted=False):
    stage=stage_for(node_id)
    schema={"$schema":"https://json-schema.org/draft/2020-12/schema", **obj({
        "schema_version":{"const":VERSION},"node_id":{"const":node_id},"stage":{"const":stage},
        "reasoning":obj({"claims":arr(CLAIM,1,8),"distinctions":arr(DISTINCTION,0,6),"uncertainties":TEXTS}),
        "result":STAGES[stage]})}
    if persisted:
        schema["properties"]["evidence_catalog"]={"type":"object","additionalProperties":obj({
            "source":TEXT,"pointer":{"type":"string"},"value_sha256":TEXT,"hint":TEXT})}
        schema["required"].append("evidence_catalog")
    if persisted and node_id == "lab_director":
        baskets=[f"B{i:02}" for i in range(1,7)]
        derived={"forecasts":obj({b:{"type":"number"} for b in baskets}),
            "selections":obj({b:TEXT for b in baskets}),"forecast_basis":{"const":"EMPIRICAL"},
            "cutoff":TEXT,"target_time":TEXT,"cp1_sha256":TEXT}
        schema["properties"].update(derived);schema["required"].extend(derived)
    return schema


def resolve_pointer(data, pointer):
    if pointer == "": return data
    if not pointer.startswith("/"): raise ValueError("evidence pointer must be a JSON pointer starting with /")
    for token in pointer[1:].split("/"):
        key=token.replace("~1","/").replace("~0","~")
        if isinstance(data,list):
            if not key.isdigit() or (len(key)>1 and key.startswith("0")): raise ValueError("invalid list pointer")
            data=data[int(key)]
        else: data=data[key]
    return data


def evidence_catalog(inputs, namespace="input"):
    prefix="E"+digest(namespace)[:6]+"_"
    """Assign opaque handles to real input values before the model is called."""
    catalog={}
    def visit(source,value,pointer,depth):
        text=json.dumps(value,ensure_ascii=False,separators=(",",":"))
        catalog[f"{prefix}{len(catalog)+1:03}"]={"source":source,"pointer":pointer,
            "value_sha256":digest(value),"hint":text[:100] or "empty"}
        if depth>=3:return
        if isinstance(value,dict):
            for key,child in value.items():
                if key=="evidence_catalog":continue
                visit(source,child,pointer+"/"+str(key).replace("~","~0").replace("/","~1"),depth+1)
        elif isinstance(value,list):
            for index,child in enumerate(value):
                visit(source,child,pointer+"/"+str(index),3)
    for source,env in sorted(inputs.items()):visit(source,env.get("data"),"",0)
    return catalog


def validate_record(node_id, record, inputs, catalog=None):
    errors=sorted(Draft202012Validator(schema_for(node_id)).iter_errors(record),key=lambda e:str(e.path))
    if errors: raise ValueError("; ".join(f"{list(e.path)}: {e.message}" for e in errors[:4]))
    catalog=evidence_catalog(inputs,node_id) if catalog is None else catalog
    reasoning=record["reasoning"]
    for key in ("claims","distinctions"):
        rows=reasoning[key]
        if len({r["id"] for r in rows})!=len(rows):raise ValueError("reasoning IDs must be unique within a node")
        for row in rows:
            if row.get("kind") in {"observation","inference","decision","diagnosis"} and not row["evidence_refs"]:
                raise ValueError("observations, inferences, decisions and diagnoses need evidence references")
            for evidence_id in row["evidence_refs"]:
                if evidence_id not in catalog:raise ValueError("unknown evidence ID: "+evidence_id)
                ref=catalog[evidence_id]
                value=resolve_pointer(inputs[ref["source"]].get("data"),ref["pointer"])
                if digest(value)!=ref["value_sha256"]:raise ValueError("evidence catalogue binding changed")
    used={eid for key in ("claims","distinctions") for row in reasoning[key] for eid in row["evidence_refs"]}
    def collect(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key=="evidence_ref":used.add(child)
                else:collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    collect(record["result"])
    for eid in used:
        if eid not in catalog:raise ValueError("unknown evidence ID: "+eid)
        ref=catalog[eid]
        if digest(resolve_pointer(inputs[ref["source"]].get("data"),ref["pointer"]))!=ref["value_sha256"]:
            raise ValueError("evidence catalogue binding changed")
    return {eid:catalog[eid] for eid in sorted(used)}



def prompt_contract(node_id):
    return """\nREASONING RECORD CONTRACT: Return exactly this schema. Claims and
distinctions have local IDs; their full identities are node_id plus that ID.
Select evidence_refs and every result.evidence_ref ONLY from the EVIDENCE_CATALOG supplied below. Copy IDs
from THIS node’s catalogue, not source paths or an upstream node’s IDs. Code has already bound each ID to an exact input
value, source node and field. Do not invent IDs. A hypothesis can remain tentative.
Distinctions contain at least two explicit alternatives. Certainty is a stated
epistemic status, not a measured probability. Put role-specific output in result.
Write 2-4 consequential claims and at most 3 distinctions; do not transcribe
whole numeric tables. Cite their IDs and preserve the strongest contradiction.
JSON_SCHEMA:\n"""+json.dumps(schema_for(node_id),separators=(",",":"))


def provider_schema(node_id,catalog,lab_node_ids):
    """Provider grammar narrows identities; local validation still owns semantics."""
    # JSON round-trip breaks shared schema-fragment aliases before specialization.
    schema=json.loads(json.dumps(schema_for(node_id)));schema.pop("$schema",None)
    def visit(value):
        if isinstance(value,dict):
            if value.get("pattern")==EVIDENCE_ID["pattern"]:
                value.clear();value["$ref"]="#/$defs/evidence_id";return
            if "const" in value:value["enum"]=[value.pop("const")]
            value.pop("uniqueItems",None)  # Enforced by the runtime; not every provider accepts it.
            for key,child in value.items():
                if key=="node_id" and isinstance(child,dict) and "enum" not in child and "const" not in child:
                    child.clear();child.update(type="string",enum=lab_node_ids)
                else:visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(schema)
    schema["$defs"]={"evidence_id":{"type":"string","enum":list(catalog)}}
    return schema
