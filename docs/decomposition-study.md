# Context-informed structural revision

This experiment implements the first mechanism test in the [programme](../program.md). A model receives an ordinary Python program, a task contract and measured examples. It may revise code and, in the unrestricted conditions, change interfaces, state or the decomposition into functions. The experiment uses the existing restricted executor and budgeted provider; there is no new graph execution engine.

## What is being tested

A graph here is the inspectable call structure of ordinary functions. A contextual condition receives the selected function's arguments, calls and callers, mechanically extracted from the current code. It can propose a change across that boundary. This is a focused structural-revision interface, not a network of independently self-modifying agents.

Four authored diagnostic tasks expose distinct cases:

- Synthetic affine sensor calibration: calibrate individual readings before summing. An initial sum-only interface discards multiplicity when the source's offset is nonzero. Calibration coefficients are private and measured examples reveal them.
- Native SQLite allocation: predict the next automatically assigned ID after explicit inserts, deletions and transactions. The initial program preserves visible rows but loses relevant history. AUTOINCREMENT semantics are stated, so a correct solution may use pretrained knowledge rather than discovering a new source law.
- Synthetic keyed events: select values for requested keys using a private member of a disclosed timestamp/arrival family. The initial projection loses key and time information.
- A correct sensor program with zero calibration offset: no structural change is necessary. This checks gratuitous revision.

These are small constructed mechanisms. They are not four independent domains or a representative production workload. Future panels change lengths, key counts, interleavings and transaction combinations within the same specified mechanisms.

## Comparison

All conditions receive the same initial code, contract, eight calibration measurements and fresh development examples. Each has two proposal calls. Its next request receives the complete previous proposal and actual execution errors/outcomes, including rejected candidates. There are no new source probes during this first comparison.

| Condition | Permissions and presentation |
|---|---|
| Global ordinary code | Freely refactor any code, state or interface, add/remove helpers, or reconstruct the whole program. |
| Contextual revision | The same permissions, with a selected local focus and mechanically extracted caller/callee context. |
| Ordinary contracts | The same permissions and function-relationship facts rendered as ordinary code contracts. |
| Fixed interface | Edit only the focus function's body, keeping its signature and all other functions unchanged. |

The global ordinary agent is the primary competitor. The fixed condition diagnoses an information obstruction and does not establish graph superiority. The contracts condition distinguishes useful information from graph framing. Arm order rotates across tasks. Each task's conditions share one pinned model/provider route; provider substitutions are forbidden.

The host validates the model's exact returned source. It never repairs syntax, edits the candidate or retries the request. Model outputs, errors, prompts, source hashes and costs are retained. Invalid candidates cannot replace valid incumbents. Selection compares correct answers, then fewer execution errors, across **all** visible calibration and development cases; a later valid proposal replaces on a complete tie. The initial program remains a possible incumbent.

## Frozen later cases

Preparation freezes data, the two later panels, protocol, dependency hashes and an archived runtime before inference. Neither protected panel enters a prompt. After every trajectory finishes, all initial programs, proposals and selected programs are frozen. The selected programs and every proposal are scored on the screening panel. Confirmation uses the same frozen programs and selection rule on a separate panel; it cannot select a different winner after seeing screening outcomes.

The first-proposal scores distinguish immediate successful reconstruction from further improvement through measured feedback. Exact call-structure changes show what the model rewrote. They do not alone prove that a particular abstraction caused the improvement. For that claim, inspect a boundary witness or a relevant intervention and later consumer.

All-visible information is identical across the two proposal rounds; execution feedback adds the candidate's actual failure, not a previously withheld source label. This comparison therefore tests measured revision using existing evidence. It does not test acquisition of new experiments, cumulative cross-task learning or improvement of the update policy.

## Interpretation and next allocation

A positive unrestricted result with fixed-interface failure establishes that a model can overcome those authored structural obstructions. A contextual/global tie supports ordinary reconstruction and does not earn extra graph credit. If all unrestricted conditions solve everything immediately, making the prompt more elaborate is not a useful next experiment; the next question is whether acquired structure helps a harder subsequent investigation or transfer.

If contextual revision helps beyond ordinary refactoring and contracts, follow with new task/source cases and a context ablation. If a second proposal repairs the first, preserve its actual error-to-change trace and test the change on the untouched panel. If failures are interface/syntax errors, fix the experimental delivery in a new version while retaining the original failed attempts. Model or endpoint changes also create separate studies.

Report source/task results and full costs, not just a pooled percentage. Hundreds of outputs within four authored tasks do not provide hundreds of independent replications. Correct answers, execution errors and source changes are separate observations. Cheap inference permits more informative comparisons; it does not make repeated testing on the same exposed panel independent confirmation.

## Owners and commands

[Task sources](../research/decomposition_tasks.py) own native measurement, synthetic contracts, private references and panel generation. [Study runner](../research/decomposition_study.py) owns freezing, prompts, selection, endpoint routing, evaluation and exact replay. [Export/replay](../scripts/build_decomposition_report.py) publishes an explicit allowlist of scientific artifacts and billing fields; transport/account records remain local.

```sh
python -m research.decomposition_study prepare work/decomposition-run \
  --model qwen/qwen3.8-omni-flash --providers alibaba --reasoning-effort none
python -m research.decomposition_study run work/decomposition-run --env-file /path/to/local.env
python -m research.decomposition_study confirm work/decomposition-run
python -m research.decomposition_study replay work/decomposition-run
python scripts/build_decomposition_report.py export work/decomposition-run examples/decomposition/v1
python scripts/build_decomposition_report.py replay examples/decomposition/v1
```

Select current eligible models/endpoints from official metadata before preparing each campaign. The default four-task/four-condition/two-proposal protocol permits 32 calls. Its $0.75 ceiling is a maximum, not an invoice estimate. Shared admission allows at most three active calls across the host and one on a pinned endpoint. A model with one eligible endpoint consequently runs serially. Atomic admission prevents duplicate run starts, and active calls settle before failure closeout.

## Follow-on rule induction

The separately versioned [state-discovery fixtures](../research/state_discovery_tasks.py) adapt mechanisms from deep returns 02 and 13. Three synthetic resettable sources map integer sequences to integer observations. A disclosed finite family has 4,464 combinations: a small cubic polynomial, optional adjacent-value or preceding-sum interaction, and one to four ordered cumulative-sum passes. The exact choices are private. Twelve calibration receipts uniquely identify each selected source within that family; a host-only enumeration verifies this fact. The model does not receive that enumerator, correct reference, coefficients or continuation witnesses.

Each task has 24 further development cases, 24 screen cases and24 confirmation cases. Development lengths are at most 6; screening uses 8–14 and confirmation 16–32. Public context includes the entire input history. Success therefore establishes source-rule induction and longer-sequence reuse within the supplied family, **not** discovery of a minimal streaming state. Evaluator witnesses show that equal present outputs can have unequal continuations; they motivate state learning but do not prove that any successful model used that representation.

Global, contextual and ordinary-contract conditions each receive two proposals. The fixed-interface diagnostic is omitted. Qwen and DeepSeek use the same frozen data. A subsequent DeepSeek variant changes reasoning from disabled to low and increases the output allowance from 6,144 to 12,288 tokens. This is a diagnostic change to inference effort on the same sources, not independent replication or an equal-token comparison. Its panel observations must not be counted as new source diversity. All original failed runs remain published. The generic runner protocol describes the initial mechanism stage; each state dataset and its model-evidence task boundary explicitly identify this follow-on as entirely synthetic.


## Practical configuration on fresh sources

After delivery failures in the first state studies, a further comparison varies DeepSeek reasoning off versus low on six newly selected source configurations. Ordinary contracts is common to both settings; a third condition gives low reasoning the simpler global ordinary-program prompt. All receive identical observations and explicit examples of the already-existing syntax restrictions: the harmless single `_` local variable is now accepted, other private names remain forbidden, multiplication replaces exponentiation, and function defaults are forbidden. No candidate is manually repaired. Each source has two proposals, and source/route pairing is preserved across the two configurations. The low-reasoning allowance remains larger, so the comparison estimates the useful delivered configuration, not an isolated effect at equal tokens. Compared with the previous stage, the executor and syntax guidance also changed; original results remain frozen.

The new configurations include all three interaction modes and cumulative depths beyond the initial selected mechanisms. They remain within the same supplied family. This is transfer across source settings with a clearer interface, not new-domain transfer, acquisition of a new hypothesis language or an improved update algorithm. The original low run and both original nonreasoning failures remain immutable evidence.
