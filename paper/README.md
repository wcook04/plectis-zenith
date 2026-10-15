# Zenith paper

**Zenith: programs, experiments and useful memory** — Will Cook, 15 October 2026. This is a three-page research draft for an unfinished system.

[zenith.tex](zenith.tex) is the current manuscript. The checked-in [zenith.pdf](zenith.pdf) is a **previous edition** and does not contain the latest results. Use the [research website](https://wcook04.github.io/plectis-zenith/) for the current short overview.

The paper asks whether a program, its measured evidence and questions that expose its limits can become useful memory. It reports separate mechanisms, not an integrated self-improving learner:

- **Client test reuse:** two acquired testers find three of four authored SQLite faults without later model calls. Ordinary code reuse ties the retained procedure; fixed tests find all four. [Results and replay](../docs/studies/client/client-investigation-v2-low-20261015.md).
- **Native repair:** repair alone improves later answers from 259/576 to 365/576. The additional investigation conditions do not beat that baseline. [Diagnostic campaign](../docs/studies/native/progress-campaign-20261014.md).
- **Continuation learning:** preserving the history that witnessed a missing distinction repairs an authored learner. All eight native configurations fit, but generic questions cost slightly less and later checks still find errors. [Reproduction](../examples/continuation-memory/witness-preserving-v1/README.md).

The manuscript also distinguishes these results from the earlier controlled memory study. It does not claim independent transfer, recursive self-improvement or a general advantage over ordinary testing. [Programme](../program.md), [current status](../docs/status.md) and [architecture](../docs/architecture.md) connect the claims to their implementations.

To compile locally, install Tectonic and run from the repository root:

```sh
tectonic paper/zenith.tex
```

The source rejects exports longer than three pages. Compilation updates the local PDF; a new published edition must be reviewed and its website edition metadata updated together.
