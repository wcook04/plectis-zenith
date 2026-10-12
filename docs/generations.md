# Learn from experience, compare versions, retain evidence

The daily loop generates experience for improving a reasoning procedure.
An issue snapshot is the situation, the frozen reasoning policy is the version,
and Lab's forecasts plus Oracle's later diagnosis are the experience. Evolve
proposes a transferable change. The incumbent and challenger then face the same
later situations, and a reviewed decision retains one for the following generation.

This is the useful analogy with [AlphaGo Zero's self-improvement cycle](https://deepmind.google/blog/alphago-zero-starting-from-scratch/).
Zenith does not implement self-play, neural weight training or tree search.
Markets supply an external outcome stream; replaying the same dates does not
create independent truth. The comparison criterion must fit forecasting, rather
than copying a game's win percentage.

## Two different transitions

`daily review` creates an experimental successor for the next development day.
This lets the researcher inspect whether a proposed lesson changes behavior.
Its acceptance proves only bounded structure and evidence bindings. It does not
show that the new version is better.

`daily matchoff` compares the selected episode's incumbent with its reviewed
challenger through `research/cohort.py`. Both receive identical snapshots,
assets, issue times, forecast horizons, context profile and disclosed model
identity, and execute the complete 21-reasoner Lab scope. The existing feedback
engine supplies the score. There is no second execution or scoring engine.
XSHG issues use the adapter's exact next-session timestamp, including holidays
and weekends; the native engine does not accept a `next_xshg_close` shortcut.

## Run a comparison

First complete a daily Lab, Oracle and candidate review. The example below
assumes episode 0 forecasts 1 July 2020 and its teacher evidence matures on
2 July. Freeze a later interval before examining its scores:

```sh
python -m zenith daily matchoff --work-dir work/daily-demo --episode 0 \
  --dataset work/datasets/investorbench \
  --start 2020-07-06 --end 2020-07-31 \
  --output work/generation-1 --model DISCLOSED_AGENT_IDENTITY \
  --minimum-improvement 0.001
python -m research cohort-next --study work/generation-1/cohort
```

The numerical margin above is an example, not a researched default. The CLI
requires an explicit choice. The metric is mean issue-level mean target-price
relative error; 0.001 is an absolute reduction of 0.001 in that loss. Each issue
weights its three targets equally, then each issue receives equal weight.

The default response allowance is exactly 21 per run. Rejected corrections also
count. If a run needs room for corrections, declare, for example,
`--max-calls-per-run 23` when freezing it. This permits at most two additional
responses per arm, does not schedule retries, and cannot amend an existing
comparison. It does not change any separate paid-spending authorization.

Follow `cohort-next`'s exact `native_argv`; answer its packets through
`zenith import-response`, resume the run, and execute the returned `attach_argv`.
Repeat until the cohort is complete. All supplied node responses must disclose
the same actual model as the frozen comparison. This identity is declared
metadata for agent imports, not cryptographic proof of which agent reasoned.
Freeze both forecasts for an issue before evaluation. `cohort-evaluate` can
score a completed arm while the other arm is still pending; seeing those
outcomes before writing the other forecast would contaminate the comparison.

The twenty-session example requires **840 reasoning responses**: two versions
times twenty days times twenty-one reasoning nodes. Snapshot acquisition and
comparison preparation make no model calls. This cost is why the first task is
to establish competent base behavior, rather than launch a large blind search.
Paid execution, if separately selected, must retain its existing immutable
spending authorization; an agent comparison does not reset that ledger.

```sh
python -m research cohort-evaluate --study work/generation-1/cohort
python -m zenith daily retain --matchoff work/generation-1 \
  --reviewer DISCLOSED_REVIEWER_IDENTITY
python -m zenith daily init --work-dir work/generation-2-experience \
  --dataset work/datasets/investorbench \
  --start 2020-08-04 --end 2020-08-31 \
  --retention work/generation-1/retention.json
```

Retention requires complete equal support and at least twenty issue dates. A
challenger must exceed the declared improvement margin; otherwise the incumbent
is retained. Failed and incomplete comparisons cannot manufacture a selection.
The twenty-date minimum is an existing decision gate, not a significance test.
The final July forecast matures on 3 August, so the next generation above starts
on 4 August. The initializer verifies the receipt and enforces that boundary.

The immutable receipt binds the teacher review, contenders, frozen cohort,
comparison, selected policy, reviewer and final evidence horizon. Preserve its
directory. Use `--retention`, not a detached copy of the selected policy, to
carry the selection's chronology. This is an auditable local contract, not an
OS sandbox preventing a researcher from inspecting future files.

## What would count as useful learning?

First require improved behavior on the diagnosed failure: for example, a
director separates observed price movement from a proposed cause and makes
its target rule explicit. Then measure later forecast quality against the
unchanged version on common inputs. A direction hit alone cannot establish
either the cause or the benefit of the lesson.

Preserve paired issue losses, coverage, invalid outputs, calls and rejection
history. Compare simple price references and a competent direct reasoner before
claiming benefit from graph complexity. Repeated generations consume history
and increase selection bias; later assessment needs separately frozen periods
and eventually prospective outcomes. The existing sealed holdout interface is
described in [experiments.md](experiments.md); this daily adapter currently
prepares development comparisons only.

Current implementation tests verify progression, selection bindings and timing.
They use explicitly synthetic scores for retention boundary tests. No completed
generation comparison or learned financial advantage is reported.

The [May 5 quantile diagnostic](judgmental-forecasts.md#the-later-instruction-comparison)
completed both native Labs, but one correction took the baseline above its
frozen 21-response allowance. Its descriptive losses are published alongside
the admission failure; they do not constitute an accepted generation comparison.

An explicit native abstention is retained as a terminal `abstained` attempt. It
contributes missing forecast coverage, never a zero-loss observation; the
complete-support gate cannot select a version on such a comparison. The next
action list does not ask for a second answer on that date. See
[the decision contract](abstention.md).
