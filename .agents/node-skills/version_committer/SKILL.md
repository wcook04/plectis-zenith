---
name: version-committer
description: Apply the typed version_committer operation to its declared context.
---
# version_committer

- Input ports: `dossier_updater`.
- Output contract: `text`. Mission: `refinement`.
- Implementation: `codex/substrate/nodes/refinement/version_committer.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `8d739638b71539ab481ffce6489849f496ec2395af7ac4c261dc0cfefbd664ad`.
- Inspect: `python -m zenith inspect version_committer`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
