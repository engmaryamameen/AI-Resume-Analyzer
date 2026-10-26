# ADR 0006: No single overall score

**Status:** accepted · **Context:** one composite number invites false precision, rewards keyword
stuffing and reads as a prediction.
**Decision:** each requirement gets an evidence status (supported, mentioned only, contradicted,
insufficient, no evidence) with reasons and verbatim excerpts. Four descriptive assessments (requirement
evidence, document structure, writing style, extraction reliability) report counts, shares and durations,
each with a definition. A probability is shown only when a calibrated estimate exists and meets the
manifest's display policy; raw similarity is never shown as one. Changing the pipeline bumps
`PIPELINE_VERSION`, so older results show as produced by a different method.
**Consequences:** a busier results page. If a composite is ever added it needs its own versioned formula,
calibration against real outcomes and visible limits.
