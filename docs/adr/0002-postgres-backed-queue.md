# ADR 0002: Job queue in PostgreSQL

**Status:** accepted · **Context:** extraction and analysis take seconds, need retries, cancellation
and results that commit atomically with relational data.
**Decision:** a `processing_jobs` table claimed with `FOR UPDATE SKIP LOCKED`; lock expiry for crashed
workers; at most three attempts with exponential backoff; cancel flag honoured before commit; one
logical job per (kind, target).
**Consequences:** no extra infrastructure; polling load grows with volume; no delayed or fan-out jobs.
**Revisit when:** sustained throughput makes the polling measurable, or scheduling and fan-out are needed.

**Lifecycle (refined):** each job runs as prepare (short transaction), compute (no transaction, with a
heartbeat) and commit (short transaction under the user's advisory lock). Only the worker settles jobs;
exhausted jobs are settled as failed (`worker_lost`) and their targets failed with them; maintenance fails
targets whose job no longer exists. Details in [architecture.md](../architecture.md#jobs).
