# Zenith paper

**Zenith: programs, experiments and useful memory** — Will Cook, 15 October 2026. This is a three-page research draft for an unfinished system.

[Read the current PDF](zenith.pdf) or inspect its [LaTeX source](zenith.tex). This edition separates measured results from proposed directions and invites collaboration and guidance. The [research website](https://wcook04.github.io/plectis-zenith/) provides the short overview.

The paper asks whether a program, its measured evidence and questions that expose its limits can become useful memory. It reports separate mechanisms, not an integrated self-improving learner:

- **Client test reuse:** two acquired testers find three of four authored SQLite faults without later model calls. Ordinary code reuse ties the retained procedure; fixed tests find all four. [Results and replay](../docs/studies/client/client-investigation-v2-low-20261015.md).
- **Native repair:** repair alone improves later answers from 259/576 to 365/576. The additional investigation conditions do not beat that baseline. [Diagnostic campaign](../docs/studies/native/progress-campaign-20261014.md).
- **Continuation learning:** preserving the history that witnessed a missing distinction repairs an authored learner. All eight native configurations fit, but generic questions cost slightly less and later checks still find errors. [Reproduction](../examples/continuation-memory/witness-preserving-v1/README.md).

The manuscript also distinguishes these results from the earlier controlled memory study. It does not claim independent transfer, recursive self-improvement or a general advantage over ordinary testing. Its final page describes the proposed link between measured distinctions and improving the improver, relevant prior work, and a possible mathematics connection. [Programme](../program.md), [current status](../docs/status.md) and [architecture](../docs/architecture.md) connect the claims to their implementations.

To compile locally, install Tectonic and run from the repository root:

```sh
tectonic paper/zenith.tex
```

The source rejects exports longer than three pages. Compilation updates the local PDF. After reviewing all rendered pages, update both SHA-256 values in `zenith/web_content.py::PAPER_EDITION` together. The website labels a PDF current only while the manuscript and PDF match that reviewed pair; editing either makes it a previous edition until a new pair is reviewed. Checksums bind the reviewed files, not the correctness of their claims.
