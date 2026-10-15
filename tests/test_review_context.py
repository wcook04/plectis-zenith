import copy
import pytest
from zenith.review_context import compact_subject, restore_subject, compact_json
from zenith.providers import text_digest


def long_subject():
    case={"observations":[{"id":i,"value":i/7,"meaning":"cutoff observation"} for i in range(2000)]}
    contexts={};outputs={}
    for i in range(8):
        inputs={"case":{"data":case},**{k:{"data":v} for k,v in outputs.items()}}
        prompt="Instructions\n"+compact_json(inputs)+"\n"
        # Match the native format in which each named envelope occurs verbatim.
        system="Original instruction, including Unicode Δ"
        contexts[f"turn_{i}"]={"inputs":inputs,"prompt":prompt,"system_prompt":system,"schema":{"type":"object"},
            "prompt_sha256":text_digest(prompt),"system_prompt_sha256":text_digest(system),"prompt_utf8_bytes":len(prompt.encode())}
        outputs[f"result_{i}"]={"observation":list(range(1000)),"turn":i}
    return {"run_id":"fixture","manifest":{"frozen":True},"graph":list(contexts),"contexts":contexts,"outputs":outputs,"commitment":{"choice":"zero"}}


def test_eight_turn_record_roundtrips_below_the_existing_prompt_cap():
    subject=long_subject();packed=compact_subject(subject)
    assert len(compact_json(subject))>1_200_000
    assert len(compact_json(packed))<len(compact_json(subject))*.25
    assert restore_subject(packed)==subject


def test_evidence_or_prompt_tampering_rejects():
    packed=compact_subject(long_subject())
    bad=copy.deepcopy(packed);bad['contexts']['turn_0']['prompt_parts'][0]['literal']='changed'
    with pytest.raises(ValueError,match='hash'):restore_subject(bad)
    bad=copy.deepcopy(packed);key=next(iter(bad['evidence_bank']));bad['evidence_bank'][key]='changed'
    with pytest.raises(ValueError,match='hash'):restore_subject(bad)
