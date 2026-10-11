---
name: dossier-updater
description: Apply the typed dossier_updater operation to its declared context.
---
# dossier_updater

- Input ports: `delta_analyzer`.
- Output contract: `text`. Mission: `refinement`.
- Implementation: `codex/substrate/nodes/refinement/dossier_updater.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `b62e8e518e87349666e010dff9bd0cadfd9ba516c0165b00d8780d0f143aeace`.
- Inspect: `python -m zenith inspect dossier_updater`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
