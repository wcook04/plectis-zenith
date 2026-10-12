# Zenith paper

> **This is not financial advice.** This is experimental research. Historical
> examples and model outputs are not investment recommendations and must not be
> used to make financial decisions. See the [research notice](../RESEARCH_NOTICE.md).

[zenith.pdf](zenith.pdf) is the four-page paper. [zenith.tex](zenith.tex) is its
complete source, including diagrams and references. Build with
`tectonic paper/zenith.tex` from the repository root.

The paper follows the original idea through actual earlier/later feed snapshots,
the native reasoning graphs and the measured execution result. It distinguishes
runtime repairs from improved forecasts. Update its example from saved results;
keep borrowed methods and data cited where used. Keep it within four pages.

The paper uses *language-model program*, *discrete prompt optimisation* and
*context-conditioned prompt selection* to distinguish the graph, its adjustable
text and the proposed controller. DSPy, MIPRO, ProTeGi and TextGrad are cited at
their specific uses. Page 3 separates prediction-time prompt assembly from
development-time fitting; prompt settings and learned controller weights are
different objects. The [research direction](../docs/research-direction.md)
contains the fuller terminology and source comparisons.
