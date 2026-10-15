"""Lossless review view: store repeated evidence once, reconstruct exact requests.

This is deduplication, not summarisation or truncation. A failed reconstruction
stops preparation. The archived full contexts remain the source of truth.
"""
import copy
import json
from .providers import digest, text_digest


def compact_json(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def compact_subject(subject):
    bank = {}

    def reference(value):
        key = digest(value)
        bank.setdefault(key, value)
        return {"evidence_ref": key}

    contexts = {}
    for node, context in subject["contexts"].items():
        spans = []
        inputs = {}
        for name, value in context["inputs"].items():
            # Native Lab inputs are envelopes containing exactly one data key.
            # Preserve unfamiliar envelopes verbatim instead of discarding fields.
            if isinstance(value, dict) and set(value) == {"data"}:
                inputs[name] = {"data": reference(value["data"])}
            else:
                inputs[name] = reference(value)
            encoded = compact_json(value)
            pos = context["prompt"].find(encoded)
            if pos >= 0:
                spans.append((pos, pos + len(encoded), name))
        cursor = 0
        parts = []
        for start, end, name in sorted(spans):
            if start < cursor:
                continue
            if start > cursor:
                parts.append({"literal": context["prompt"][cursor:start]})
            parts.append({"input_json": name})
            cursor = end
        if cursor < len(context["prompt"]):
            parts.append({"literal": context["prompt"][cursor:]})
        contexts[node] = {**{k:v for k,v in context.items() if k not in ("inputs","prompt","schema","system_prompt")},
            "inputs": inputs, "prompt_parts": parts, "schema": reference(context["schema"]),
            "system_prompt": reference(context["system_prompt"])}
    result = {**{k:v for k,v in subject.items() if k not in ("contexts","outputs")},
        "encoding": "zenith_lossless_review_v1",
        "reading_guide": "evidence_ref addresses an exact object in evidence_bank. Each input_json part means compact JSON of the reconstructed named input; concatenate literal and input_json parts to recover the exact original provider prompt. Read each object once and follow input bindings to see which turn knew it. No evidence is summarised or dropped.",
        "contexts": contexts, "outputs": {k:reference(v) for k,v in subject["outputs"].items()},
        "evidence_bank": bank}
    if restore_subject(result) != subject:
        raise ValueError("lossless review reconstruction differs from archived subject")
    return result


def restore_subject(packed):
    bank = packed["evidence_bank"]
    for key, value in bank.items():
        if digest(value) != key:
            raise ValueError("review evidence bank hash mismatch")
    def expand(value):
        if isinstance(value, dict):
            if set(value)=={"evidence_ref"}:
                return copy.deepcopy(bank[value["evidence_ref"]])
            return {k:expand(v) for k,v in value.items()}
        if isinstance(value, list):
            return [expand(v) for v in value]
        return value
    contexts = {}
    for node, context in packed["contexts"].items():
        inputs = expand(context["inputs"])
        prompt = "".join(p["literal"] if "literal" in p else compact_json(inputs[p["input_json"]]) for p in context["prompt_parts"])
        restored = {**{k:v for k,v in context.items() if k not in ("inputs","prompt_parts","schema","system_prompt")},
            "inputs": inputs, "prompt": prompt, "schema": expand(context["schema"]), "system_prompt": expand(context["system_prompt"])}
        if text_digest(prompt) != context["prompt_sha256"] or text_digest(restored["system_prompt"]) != context["system_prompt_sha256"]:
            raise ValueError("review request reconstruction hash mismatch")
        contexts[node] = restored
    return {**{k:v for k,v in packed.items() if k not in ("contexts","outputs","encoding","reading_guide","evidence_bank")},
        "contexts": contexts, "outputs": expand(packed["outputs"])}
