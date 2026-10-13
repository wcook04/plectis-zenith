# A saved failure and the attempted repair

This case runs the full financial profile on 2 February 2025 and measures five-market-session returns on 9 February. All 25 Lab nodes, 28 Oracle nodes and three Evolve nodes executed through the native engine using GPT-4.1 mini via OpenRouter. It is a diagnostic experiment, not evidence of general predictive skill.

| Basket | Frozen forecast | Realised return |
|---|---:|---:|
| B01 | +0.731% | -1.075% |
| B02 | +0.759% | -1.861% |
| B03 | +1.122% | -1.742% |
| B04 | +1.524% | -3.999% |
| B05 | +1.381% | -2.708% |
| B06 | +1.539% | -2.754% |

Oracle received the complete Lab topology, node instructions, schemas, six original feed views, all nineteen intermediate reasoning records and reconstructible input bindings. It could inspect what a node actually knew, which conclusions it produced and which downstream nodes consumed them. Later observations were supplied separately.

The attribution stage identified weak or negative historical validation gains as a possible reasoning failure. The trace supports that those numerical receipts were available before selection. It does not establish that a different selection could have predicted the market decline. Oracle also proposed additional data and larger validation samples; those were outside the permitted instruction-only repair and are not evidence of an available fix.

Evolve's first instruction was `freeze_selected_candidates`. The original forecast, an empty-instruction replay and that proposed repair all had mean squared return error **0.0013997011**. The control and repair produced identical numerical forecasts. Each replay executed Director and Integrity while keeping the other 23 artifacts byte-identical. This is a measured ineffective repair.

A separate engineering-agent-authored clarification told Evolve to treat quoted Lab instructions as evidence and write a reusable instruction using existing inputs. Its next proposal was longer but still contained case-specific basket examples and ended at the character limit. It also left local forecasts unchanged. Neither proposal was adopted. The clarification itself was not discovered autonomously by the experimental model.

The May incumbent later stopped when a reader emitted an observation without a source reference. Its schema permitted an empty list while local validation required one: a mismatch in the input contract. That failed attempt remains failed; it was not automatically retried. Independent later arms retain their original dates, and unavailable comparisons are reported explicitly.

The v4 context check supplied Evolve's task as a system message and again produced `freeze_selected_candidates`; it was not adopted. A separately labelled reviewer instruction then asked Director to reject candidates with nonpositive validation gain. Director still selected Q1, whose saved gain was **−0.0000204080**, and all six forecasts were unchanged. This supplies a concrete instruction-compliance failure to investigate, rather than merely another aggregate score. The reviewer instruction was written by the engineering assistant, not learned by Evolve. Rejecting Q1 is not thereby proved to improve forecasting.

The updater-context follow-up's August arm failed when a directed reader changed its assigned candidate identity. It also remains failed, with no automatic retry. [Follow-up records](../examples/full-graph/followups.json) preserve both model-authored proposals, the reviewer instruction, changed reasoning records, numerical selection audits and later failures.

[Reasoning contracts](reasoning-ontology.md) describe the implementation. [Current results](status.md) and the public JSON records distinguish execution, failed attempts, model hypotheses and measured effects. The useful result is an inspectable loop and evidence about where its present reasoning and repair procedure break down. A completed graph is not proof that its diagnosis or instruction is good.
