# Research boundary

Reviewed against the official FCA sources below on 11 October 2026. This document records the prototype's product scope and release-review questions. It is not a legal opinion, regulatory approval or a finding that public launch is cleared.

## Current local scope

Zenith is a local research engine for agent-native market graphs and reproducible experiments. Its internal CP2 and Oracle artifacts can contain instrument-specific forecasts and trade rationale inherited from the research contracts. These are private research outputs; this repository has no public website or deployment.

The licensed historical benchmark reports statistical forecast error, not portfolio returns or profit. There is no broker integration or trading execution. Public release of generated research would require reviewing the actual content and presentation, including instrument-specific recommendations. A research label or disclaimer alone does not establish a lawful perimeter.

## Requirements for research results

- Identify the dataset, source, version, licence, observation dates and label definitions. Record any missing-data treatment and exclusions.
- Publish the train/validation/test split, preprocessing, score definitions and comparison baselines. Separate evaluation data from fitting and tuning.
- Show sample counts, limitations and uncertainty where supported. Display unsuccessful attempts and unavailable measurements honestly.
- Preserve requested and actual model identity separately. Distinguish measured cost, estimated cost and unavailable cost; state units and the measurement basis.
- Do not label statistical accuracy as investment success or imply that a leading model identifies investments worth buying. A past dataset result is not a current market prediction.
- Restrict telemetry exports to the stated allowlist. Do not include private prompts, model responses, instrument-level signals, asset probabilities or personal information in aggregates or drilldowns.

## Why these boundaries matter

FCA guidance distinguishes facts from advice, but selection, value judgments and context can give information the force of a recommendation. Factual performance tables against published criteria may be information; “best investment” framing changes the question. [PERG 8.28](https://handbook.fca.org.uk/handbook/perg8/perg8s29), provisions updated 23 February 2018.

Avoid treating public availability or absence of personalisation as legal clearance. For an unauthorised operator, advice on the merits of particular investments can be regulated even when it is not personalised. The narrower personal-recommendation definition applies to appropriately authorised firms. The current PERG page also notes that its targeted-support update is pending. [PERG 8.24](https://handbook.fca.org.uk/handbook/perg8/perg8s25), current page observed 11 October 2026.

A communication made in the course of business that invites or induces investment activity can be a financial promotion. If that applies, establish the lawful route—authorisation, approval by a permitted approver, or an applicable exemption—before publication. Free access and research labels are not automatic exemptions. [FCA: approving financial promotions](https://www.fca.org.uk/firms/financial-promotions-and-adverts/approving-financial-promotions), updated 28 May 2024. Trading tools marketed using profit promises can also raise promotion questions. [PERG 8.4.24](https://handbook.fca.org.uk/handbook/perg8/perg8s4).

## Review before public release

This local extraction has not been publicly deployed. Before public launch, obtain UK regulatory-perimeter review of the actual product, outputs, downloads and promotional material. Check dataset redistribution rights and any collection of personal data separately. Never claim “FCA compliant”, “FCA approved” or “legally cleared” on the basis of this research.

Review each shareable communication in context: a cropped score panel or social headline should retain its dataset, evaluation-period and limitation context. FCA social-media guidance addresses balanced, clear promotions and the responsibility of unauthorised communicators. [FG24/1](https://www.fca.org.uk/publications/finalised-guidance/fg24-1-finalised-guidance-financial-promotions-social-media), published 26 March 2024.

Reassess scope before adding investment recommendations, current forecasts, financial-return simulations, broker links or personalised tools. Actual investment recommendations can engage UK MAR requirements on objective presentation and conflict disclosure. [FCA: Market Abuse Regulation](https://www.fca.org.uk/markets/market-abuse/regulation). COBS performance rules have defined application scopes; they are not blanket rules for every research website. They would need assessment if financial performance is later shown. [COBS 4.6](https://handbook.fca.org.uk/handbook/cobs4/cobs4s6?timeline=true), updated 6 April 2026.

“Benchmark” here means an evaluation of models. If a future index is used to determine financial-instrument/contract values or amounts, or for certain fund tracking, allocation or performance-fee purposes, assess UK Benchmarks Regulation separately. [FCA Wholesale Data Market Study, Annex 2, paragraphs 2.1–2.3](https://www.fca.org.uk/publication/market-studies/ms23-1-5-annex-2.pdf), 2024.

## UI wording

**Site description:** “Historical model benchmarks and aggregate research-system telemetry. Inspect the data, methods and evidence behind each result.”

**Benchmark note:** “Scores describe this historical dataset and evaluation split. They are statistical research results, not investment returns or recommendations.”

**Telemetry note:** “Aggregate operational measurements. Private model predictions are not published here.”

**Release note:** “Local research prototype. Public release requires review of the regulatory perimeter, data rights and launch wording.”

These statements must describe the product's actual behaviour. A disclaimer cannot substitute for appropriate scope and review.
