# Bounded Lab context example

`lab_context_16k.json` assigns each of the 21 Lab reasoning nodes a 16,000-character source-context budget, with equal incoming weights by default and a short rule requiring uncertainty when evidence is omitted. It is a fixed example configuration, not a learned policy or demonstrated improvement.

Use `--policy examples/policies/lab_context_16k.json` with `zenith prepare/run`. The original engine still assembles its instructions, contracts and receipt wrappers; their size is additional to the source-context budget. Provider token estimates and model context limits apply separately.

Every excerpt/omission has a source hash and receipt. The policy does not summarize the missing rows or guarantee that retained characters contain representative evidence. Compare it with an untruncated or deliberately selected evidence profile on matched inputs before drawing performance conclusions. Changing policy parameters requires a new policy hash and new frozen run.
