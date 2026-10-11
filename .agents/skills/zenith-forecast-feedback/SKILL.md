---
name: zenith-forecast-feedback
description: Register accepted forward CP2 forecasts, measure exact matured horizons, inspect rolling price/direction errors and review repeated skill-participation signals from a full batch. Use for forecast accuracy and proposed research feedback across runs.
compatibility: Repository-installed Python environment; local feedback CLI, no API calls or automatic skill changes.
---

# Zenith forecast feedback

Read `docs/forecast-feedback.md` and the selected feedback policy. Operate
`python -m feedback register`, `score`, `summary` and `propose`; inspect their
help for inputs. Try `python -m feedback demo --store <fresh-path>` only as
an explicitly synthetic contract demonstration.

Admission uses the actual CP2 schema validator, subject equity baseline,
model receipts and frozen effective graph ancestry. Preserve hashes and
exact forecast/truth references. Never hand-edit accepted CP2, substitute
Oracle hindsight, infer an unavailable actual model, or deliver future truth
to a Lab packet.

Score only matured exact horizons with compatible price basis/currency and
raw observation timestamps or explicitly dated session closes. Fetch time
is not a bar date. Preserve pending and data-gap states separately from
direction or target-price misses. Different horizon runs may share an issue
time; record separate target times and horizon IDs, counting that issue time
once for batch eligibility. Inspect errors alongside the no-change price
baseline and all successful as well as failed cases.

Default proposal eligibility needs 20 distinct resolved issue times across
three nonoverlapping issue buckets. Each repeated class needs failures on
three issue times/runs/buckets. Raise these operational gates when needed;
they are not statistical confidence thresholds. Report forecast/issue support
fractions, full denominator, overlap and missing-evidence counts. Sliding
reports and overlapping horizons do not create independent replication.

Use proposals to trace observed participation through exact ancestor edges,
node/skill-addon hashes and context receipts. Do not assign causal blame or
call this a gradient. Review one falsifiable instruction/context change and
require fresh heldout/prospective shadow evidence and uncertainty before
promotion. The current native scientific probability-mapper cannot by itself
validate a price-error improvement. No feedback result automatically edits
a skill, graph, prompt, dossier or release.

Keep the store outside `web/`; these asset-level research records are not
aggregate publication telemetry.
