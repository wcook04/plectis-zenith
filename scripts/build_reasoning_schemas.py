"""Export the runtime-owned ontology for API readers and offline inspection."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from zenith import runtime
from zenith.financial_reasoning import schema_for
from zenith.providers import write_json

graph=runtime.load_graph(runtime.DEFAULT_ROOT,task_profile="financial")
schemas={n.id:schema_for(n.id,persisted=True) for n in graph.values()
         if n.type.value=="reasoning" and n.group in {"lab","oracle","refinement"}}
write_json(runtime.DEFAULT_ROOT/"examples/full-graph/reasoning-schemas.json",{
    "schema":"zenith_reasoning_ontology_export_v1","owner":"zenith/financial_reasoning.py",
    "evidence_semantics":"Model selects E IDs; code-owned catalog binds each ID to an exact source, data-relative pointer and value hash. Persisted records include used bindings.",
    "derived_cp2_fields":"forecasts, selections, forecast_basis, cutoff, target_time and cp1_sha256 are supplied by numerical code after model-output validation",
    "schemas":schemas})
