# Frozen executable-investigation evidence

These generated bundles contain complete synthetic inputs, frozen model-authored programs, source-schema mappings and expected outputs. Each `executor.py` and `evaluator.py` is an exact copy from that campaign's pre-inference source archive. Keep versions separate: historical execution failures must not silently become successes under a later interpreter or scorer.

Reproduce every included first/final program and transfer score without credentials or inference:

```sh
python scripts/build_learning_report.py replay
```

The command checks bundle, protocol, program, executor, evaluator and dataset hashes; re-executes the original programs; and compares their numerical outputs, acquisition traces and errors with the recorded results. The [curated receipt](../../docs/investigation-learning-20261013.json) includes every attempted campaign, including failed provider/interface versions and frozen learners from a campaign whose final control was credit-rejected. Incomplete controls stay explicitly missing. Raw provider transport and credentials remain local.

Regenerate only from original local campaigns with `scripts/build_learning_report.py build --study <campaign> ...`. Never hand-edit generated bundles, frozen executors or measured scores. The current runtime owners remain under `zenith/` and `research/`; these copies are historical evidence, not another maintained execution engine.
