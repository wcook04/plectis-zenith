# Progress v5: repair-admission amendment

This is a prospective amendment to the [v4 Progress protocol](progress-protocol-20261014.md).
The v4 three-parent qualification exposed a generic Python admission failure:
ordinary UTF-8 repair candidates using standard pure expressions, including
bit shifts, were rejected before their behavior could be tested. Preserve the
complete v4 qualification, its model attempts, native observations, invalid
candidates and settled charges as an engineering result. The v4 twelve-parent
diagnostic was never opened and contributes no outcome or charge. Do not repair
v4 in place or pool its qualification scores with v5.

V5 changes only the generic Python admission path and its prompt allowlist:
admit bounded pure string joining, `chr`, and `LShift`/`RShift`, the forms
blocked in v4's UTF-8 repairs. Other syntax and safety constraints remain as
before. An offline regression test must show that a minimal strict
incremental UTF-8 implementation using these forms is admitted and passes
the supplied public examples, while rejected imports and unsafe execution
remain rejected. The test is an interface gate, not a diagnostic observation.

All scientific arms, query allowances, native contracts, stronger fixed
UTF-8 boundary pack, parent matching, repair selection rule, scoring,
masked-feedback isolation and cost accounting remain as in v4. The adaptive
and masked arms share one paid first provider action, then separately
reexecute first native and parent queries. Their second prompts differ only
in whether measured outcomes are visible. Every arm still receives exactly
one whole-program repair call, including `repair_only`.

Before any v5 paid call, freeze new source, model/endpoint evidence, protocol,
datasets, seeds, parent episodes, protected query panels, and the analysis
code. Use qualification seed `2026101408` and diagnostic seed `2026101411`,
with panels disjoint from
each other and from v4's opened qualification panel; check and report actual
query overlap. A repeated prompt can generate a byte-identical parent even
on a new provider episode. Count repeated parent prompt and source hashes
across stages, and do not call repeated programs independent subjects.
These replacement seeds were selected by exact later-input disjointness
before any v5 model response. The earlier prepared seed pair
`2026101403`/`2026101404` overlapped on protected UTF-8 inputs, was rejected
before a paid call, and supplies no outcome. Preserve the pre-inference
seed-selection receipt and prepared folders without treating them as trials.

Run a new three-parent qualification, one parent per SQLite, LRU and UTF-8
contract, under a separate $0.60 hard ceiling and at most 36 unique model
calls. Its gate requires valid direct-arm delivery on every contract, an
actual paired second-turn distinct legal query, zero investigator-error
misattribution, at least one selected repair candidate per contract that
executes all supplied development examples without a runtime/admission
error, and the offline admission regression above. This executable-delivery
condition does not require a correct answer on every example. If the gate
fails, retain the complete attempt and do not open the v5 diagnostic. If it
passes, run the separately frozen twelve-parent diagnostic, four per
contract, under its own $0.60 hard ceiling and 144 unique-call ceiling.
Actual calls and charges may be lower. Never append tuned runs to either
freeze.

The primary outcome remains the all-parent paired adaptive-minus-masked
confirmation answer difference. Report fixed, ordinary, finite batch,
repair-only and unchanged-parent controls, family-stratified counts,
second-turn opportunity, native work within family, selected and unchanged
repairs, invalid attempts, actual model calls and known/unknown cost. V4 is
engineering evidence; v5 qualification is excluded from v5 diagnostic
estimates. Three authored native mechanisms do not establish transfer,
acquired memory, or improvement of a learning policy.
