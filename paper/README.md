# Zenith paper

**Zenith** — Will Cook, 15 October 2026. This is a three-page research draft for an unfinished system.

[Read the current PDF](zenith.pdf) or inspect its [LaTeX source](zenith.tex). This edition separates measured results from proposed directions and invites collaboration and guidance. The [web edition](https://wcook04.github.io/plectis-zenith/) presents the manuscript with the same scholarly terminology, table, citations and repair-loop figure.

The paper asks whether a program, its measured evidence and questions that expose its limits can become useful memory. It reports separate mechanisms, not an integrated self-improving learner:

- **Client test reuse:** two acquired testers find three of four authored SQLite faults without later model calls. Ordinary code reuse ties the retained procedure; fixed tests find all four. [Results and replay](../docs/studies/client/client-investigation-v2-low-20261015.md).
- **Native repair:** repair alone improves later answers from 259/576 to 365/576. The additional investigation conditions do not beat that baseline. [Diagnostic campaign](../docs/studies/native/progress-campaign-20261014.md).
- **Continuation learning:** counterexample refinement retains each new access history with its distinguishing continuation, restoring an established weighted-automata invariant. All eight native configurations fit their finite challenges, but generic questions cost slightly less and later checks still find errors. [Reproduction](../examples/continuation-memory/witness-preserving-v1/README.md).

The manuscript also distinguishes these results from the earlier controlled memory study. It does not claim independent transfer, recursive self-improvement or a general advantage over ordinary testing. Its final page describes the proposed link between measured distinctions and improving the improver, relevant prior work, and a possible mathematics connection. [Programme](../program.md), [current status](../docs/status.md) and [architecture](../docs/architecture.md) connect the claims to their implementations.

## Reviewed sources and their use

| Source edition | Use and boundary |
|---|---|
| [Predictive Representations of State (2001)](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf) | Conceptual context for future-test probabilities. Its construction assumes a known stochastic model; it does not supply Zenith's black-box learner. |
| [Worrell's undated weighted-automata notes](https://www.cs.ox.ac.uk/people/james.worrell/MA-learning.pdf) | Observation tables and paired history/continuation rank refinement. Zenith's finite challenges replace the global equivalence oracle assumed by the notes. |
| [ILF, CCS 2019](https://doi.org/10.1145/3319535.3363230) | A neural testing policy learned from symbolic-execution demonstrations. Fast deployment is separate from expert acquisition and weight training. |
| [CoverUp, 2025, v4](https://arxiv.org/abs/2403.16218v4) | An authored coverage/error-feedback driver refines regression tests with a fixed LLM. Coverage does not establish specification correctness or acquired policy transfer. |
| [Voyager, 2023, v2](https://arxiv.org/abs/2305.16291v2) | An executable skill library supports composition and reuse inside Minecraft; the acquisition procedure remains fixed. |
| [STOP, COLM 2024, v3](https://arxiv.org/abs/2310.02304v3) | Recursive optimization of a code-improvement scaffold under a fixed language model, utilities and controller. |
| [Hyperagents, 2026, v1](https://arxiv.org/abs/2603.19461v1) | Editable task/meta-agent code and tests of an acquired meta-agent's usefulness. Stronger compounding evidence remains statistically unresolved. |

The [portable source records](references.json) own reviewed metadata, exact source-edition hashes, page or section locators, claim boundaries and the manuscript passages each source supports. They contain citation evidence rather than copies of the supplied source documents. The [citation builder](../scripts/build_paper_references.py) generates the manuscript's inline bibliography from these records and checks every citation against its reviewed supporting passage. The website reads the same records.

The `/api/v1/paper` response also derives its `reading` content directly from the manuscript's paragraphs, table and citations through [paper_reading.py](../zenith/paper_reading.py). This restricted TeX-to-Markdown projection rejects unsupported content. The frontend renders it through the existing reading components. The [figure builder](../scripts/build_paper_reading.py) renders the manuscript's TikZ source into `paper/repair-loop.svg`, served at `/assets/repair-loop.svg` and included in the public snapshot. Its caption is projected directly from the TeX with the reading content. Keep the source and generated figure together when revising it.

A changed cited claim requires another review of its source and support boundary before updating the recorded passage and hash. Refreshing a hash alone cannot establish support for new wording. Bibliography or source-record changes likewise need review against the cited edition.

## Build and check

From the repository root, check the source editions and claim bindings before compiling:

```sh
python scripts/build_paper_references.py --check
```

After reviewed metadata changes, run `python scripts/build_paper_references.py` to regenerate the inline bibliography, then repeat `--check`. Before committing, `python scripts/build_paper_references.py --index` checks the staged manuscript and source records rather than the working copies.

To build the PDF and web figure locally, install Tectonic and Poppler's `pdftocairo`, then run from the repository root:

```sh
tectonic paper/zenith.tex
python scripts/build_paper_reading.py
```

The source rejects exports longer than three pages. Compilation updates the local PDF; the figure builder uses the same TikZ through Tectonic and `pdftocairo` to update the SVG. Inspect every PDF page and the SVG before updating `zenith/web_content.py::PAPER_EDITION`. It keeps a reviewed manuscript/PDF hash pair and a separate diagram-source/SVG hash pair. Update the affected pair together after review. The website labels an artifact current only while its source and rendered output match the reviewed pair. Checksums bind the reviewed files, not the correctness of their claims.
