# ADR 0007: Extraction in an isolated child process

**Status:** accepted, with a stated gap · **Decision:** untrusted files are parsed by a
self-contained script under `python -I` in a child process with CPU, memory, file-size and
descriptor rlimits, an empty environment and a timeout. Output is one JSON object; any anomaly is a
failure with a stable code.
**Consequences:** a parser crash or hang can't take down the worker. **Gap:** rlimits are not a
security boundary and don't restrict the network; production must add container isolation with
egress denied (see INFERENCE_AND_DEPLOYMENT.md). OCR, if added, goes behind this same boundary.
