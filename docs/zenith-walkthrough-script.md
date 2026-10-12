# Zenith: spoken walkthrough

Draft for Will, 12 October 2026. About ten to eleven minutes of speech, plus time to
inspect the graphs. Read the spoken sections; headings and screen cues are not
narration. The architecture describes the intended complete loop.
The preparation example states how far execution has actually reached.

**This is not financial advice.** The [research notice](../RESEARCH_NOTICE.md)
applies to this script and any recording or excerpt made from it.

## 1. The idea

Right, so this is Zenith. It's a research project about whether we can improve
a procedure by understanding where it repeatedly goes wrong.

Before I explain it: this is not financial advice. The market data and model
outputs are research examples, not investment recommendations. Don't use any
of this to make financial decisions.

The starting point is quite simple. We have a network of reasoning nodes.
Each node is given something, does a particular piece of work, and produces
something that another node can read.

So we can see what information went in, what the node said, and where that
answer went next. The arrows show which outputs a step receives.

What I want to do is run the same graph over different periods, see what
happened afterwards, and trace the failures backwards. Then we can look for
the failures that keep repeating, make one change, and actually test it.

## 2. Start with the inputs

This example keeps the real saved stock, ETF and prediction-market data.
Only macro and news are invented replacements, clearly labelled as such.
The calculator recomputes its summaries from the resulting inputs.

The real inputs stay in the computation even where their raw payloads aren't
on the public website. We show their provenance separately from the invented
examples. That is a mixed-data demonstration, not a fully synthetic one.

The idea is to take a snapshot from an earlier time and give the graph that
information. It chooses a subset of assets and makes predictions. We freeze
what it said before opening the later snapshot.

But a snapshot doesn't have to mean one still image of the market. It can
contain a history: price movements, news and other observations up to that
point. So it's more like a video so far, saved at a cutoff. We could try to
predict a later state, or a whole future path. Those are different tasks and
need different ways of measuring the result.

That gives us two questions. Did it choose a useful subset to examine? And
how close were its predictions? We need to measure both. Choosing fewer easy
cases shouldn't let it look better while ignoring everything it got wrong
or left out.

## 3. Lab, Oracle and Evolve

Lab is the part that reads the earlier information and forms the prediction.
The current Lab has twenty-five nodes, including six input artifacts.

First, it inventories the data. Then six miners examine their own lanes.
A cross-correlation step brings their observations together. Orient develops
competing explanations, and Decide saves the working thesis at a checkpoint.

Then there's a second pass. The miners go back to the original feeds with
that thesis in mind and look for evidence that supports or challenges it.
Their findings are brought together again. Director saves the predictions,
and Integrity checks the result.

Those checkpoints matter because we need to preserve what the graph actually
said. Otherwise, once we know the outcome, it's very easy to rewrite the story.

Oracle is the part that gets the later snapshot. It compares the frozen
prediction with what happened, reviews the evidence and proposes where the
reasoning may have failed. The name doesn't mean its diagnosis is correct.
A wrong answer doesn't tell us, by itself, which step caused it.

Evolve proposes a change based on that diagnosis. It could change an
instruction, the context a node receives, or a connection between nodes.
The model weights stay fixed. That is the intended loop; this version has
not yet completed a forecast or an Oracle and Evolve comparison.

## 4. What kind of failure was it?

This is the part I want to spend time on. Was the relevant evidence missing
from the saved data altogether? Was it there, but never passed to the node
that needed it? Or did the node have it and reason badly from it?

Those are different failures. If the information wasn't available, changing
the reasoning instruction may not help. If it was available but lost along
the way, we can inspect that route through the graph.

We trace back to the first recorded claim that the evidence doesn't support.
Sometimes we won't be able to tell what caused the mistake. That should stay
unknown. We can research an event afterwards to understand it, but we can't
then pretend that explanation was information the earlier graph had.

And sometimes the problem is more basic: the node runs out of space before
finishing its answer. That's an execution failure. We shouldn't automatically
call it a reasoning failure just because it happened in a reasoning node.

## 5. Repeat it, change one thing, compare again

We keep the graph fixed while we collect runs. Then we examine different
windows of those runs, moving the window along and changing its width.
That helps us see whether a failure is recurring or depends on one period.
Overlapping windows still contain the same underlying cases, so we don't
count them as independent evidence.

We choose a repeated failure, freeze one proposed change, and compare the
old and changed versions on the same later inputs. We need a declared measure
of improvement, and we need to record what got worse as well.

If the evidence supports keeping the change, that can become the next base
graph. Then we repeat the process. That's the idea I was reaching for with
the self-play comparison: successive versions have to earn their place.
Here we have finite historical records and imperfect feedback, so the
comparison is much less controlled.

## 6. What has actually run

The preparation command makes an earlier and later packet. It copies the
three retained real feeds exactly, adds the invented macro and news examples,
and runs the existing calculator again. It doesn't fetch new data or call a model.

We have checked the reduced graph and loaded all six inputs through the native
Lab engine. It prepares the first reasoning request and then waits for a response.
That is how far this configuration has reached. There is no completed forecast
or measured improvement yet.

Older results belong to their original graph and inputs. Changing the inputs
doesn't let us reuse those numbers as evidence for this version. We need to
run and evaluate the actual configuration we are describing.

The saved clocks also need care. A collection time doesn't necessarily tell
us when each underlying observation first became available. And a current
model may already know later events. Those questions have to be addressed
before calling a result a clean historical test.

## 7. The larger idea

The bigger idea is still theoretical. Eventually, we'd want to run this with
properly licensed financial snapshots, including proprietary data, with much
better records of what was actually available at each point.

Then the graph itself could adapt to the conditions it's reasoning about.
Think of each reasoning node as having a dossier: the common rules, its
specific job, and the prompt that tells it how to do that job.

That prompt can have parts. Each part can have a setting between zero and
one, and each setting corresponds to slightly different wording.

Take the Polymarket miner. It still reads the seed state and the Polymarket
data. It still extracts the interesting signals under the same rules and
returns the same kind of output. The setting makes a small change to how it
interprets those signals. If there is evidence of an unusually greedy market,
for example, how much emphasis should it give to sentiment as an explanation
for apparent consensus? That doesn't mean the consensus must be wrong.

So zero point one and zero point two could be very similar instructions,
with a slight difference in emphasis. The job stays the same. The factual
evidence, ranking rules and required checks stay the same. The number tells
us which wording to put in that part of the prompt.

And that generalises across the reasoning nodes. A miner has its own
interpretive choices. A node bringing several feeds together has different
ones. We can keep one shared set of market-condition signals, then have a
small controller choose the settings for each node.

VIX could be one signal, or we could examine a separate sentiment index.
Neither tells us everything about the regime. We'd have to learn whether
those signals help choose the settings at all, using only information
available before the prediction.

The controller could be an actual neural network with learned weights. Its
outputs would determine the wording used by the reasoning graph. The language
model's own weights would stay fixed.

There is a limit to the backpropagation comparison, though. Ordinary
backpropagation works through numerical operations with known derivatives.
A change in wording and a hosted model response don't give us that directly.
We can search over the settings, or train the numerical controller from
measured results. Tracing an explanation backwards through the graph doesn't,
by itself, tell us the right parameter update.

## 8. What comes next

First, we need the existing graph to complete and produce predictions we can
actually score. Then we can compare fixed instructions with these small,
condition-dependent variations on more later cases. The evaluation needs to
be decided before we see their outcomes, and the judging rules stay fixed.

The aim is a graph that reasons usefully across very different situations
without wasting work. We'd want to measure performance in different regimes
and through changes between them, including the cases where it does badly.
We can't promise a graph that predicts every possible future. Sometimes the
available information just won't distinguish what happens next.

That's the vision: learn how the same reasoning jobs should be carried out
under different conditions, keep the versions that earn their place, and
preserve enough evidence to see why we kept them. It's a research direction,
not a forecasting capability we've demonstrated yet.

And again, this is not financial advice. It's an experimental research
prototype. None of the examples or model outputs should be used to make
financial decisions.

## Screen cues and recording notes

Use the existing [diagrams](graphs.md) and [research-direction diagram](research-direction.md#external-signals-choose-the-settings).
These are optional visuals, not a claim that a live execution will complete.

| Spoken section | Show | Cue words |
|---|---|---|
| The idea | Overview diagram | input · step · output |
| Inputs | Per-feed provenance and five lanes plus CALC | real · synthetic replacement · derived |
| Lab, Oracle and Evolve | Lab, then Oracle, then Evolve diagrams | first pass · thesis · check |
| Failure types | One node's inputs, instruction and saved output | absent · not surfaced · misread |
| Repeat and compare | Overview's later-comparison step | same graph · one change · later |
| Prepared example | [Current status](status.md) | six inputs loaded · awaiting Seed · no forecast |
| Larger idea | [Paper, page 3](../paper/zenith.pdf) and [controller detail](research-direction.md#external-signals-choose-the-settings) | same job · small wording change · learned settings |
| Next steps | Full Lab graph | complete · score · repeat |

Keep “Research prototype. This is not financial advice.” legible on screen,
especially beside historical prices or model outputs. Mark archived material
with its date. Do not display credentials or private feed payloads. The public
diagrams and redacted result are enough for this explanation.

For a standalone excerpt, retain a spoken or visible notice within the excerpt,
not only in the full video's introduction or description. Keep “no completed
forecast / no demonstrated prediction improvement” attached to the result.
Avoid a title or thumbnail that presents the experiment as a successful trading
system. The notice is not a guarantee of legal compliance; see the
[publishing boundary](../RESEARCH_NOTICE.md#publishing-and-reuse).

Suggested description, with the notice before any collapsed text:

> This is not financial advice. Zenith is an experimental research prototype.
> Historical examples and model outputs are not investment recommendations and
> must not be used to make financial decisions. This walkthrough explains the
> Lab, Oracle and Evolve architecture, a mixed-input preparation example, and the
> limits of the current evidence. Improved forecasting has not been established.
> [Repository](https://github.com/wcook04/plectis-zenith) ·
> [Research notice](https://github.com/wcook04/plectis-zenith/blob/main/RESEARCH_NOTICE.md)

## Factual anchors for revision

- [Graph architecture](architecture.md) and [exact dependencies](graphs.md).
- [Proposed semantic settings and neural controller](research-direction.md),
  including pinned GitHub references and the limits of the backpropagation analogy.
- [Failure classification](failure-diagnosis.md), including source visibility
  and the distinction between diagnosis and tested cause.
- [Mixed demo](demo.md), [input provenance](../examples/demo/provenance.json)
  and [preparation result](../examples/demo/result.json).

Refresh the preparation/result section against these records before recording
after any new experiment. Keep future plans in future tense.
