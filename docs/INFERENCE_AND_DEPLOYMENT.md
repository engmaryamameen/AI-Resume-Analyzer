# Inference and deployment

How the models run in production, what they need, how to configure and operate the system, and what
happens when something is missing or goes wrong.

**Status.** Nothing here has been deployed, load-tested or benchmarked. Sizes are estimates from published
parameter counts, and no user or throughput figure is claimed. The checks that must be done on a real
installation are listed at the end.

## Processes

| Process | Command | Notes |
| --- | --- | --- |
| API | `uvicorn app.api.main:app --app-dir backend` | stateless; never loads a model. Needs no `ml` extra |
| Worker | `python -m app.jobs.worker` (from `backend/`) | the only process that runs models and extraction; one job at a time per process |
| Web | `next start` (from `frontend/`) | stateless; proxies `/api/v1` to the API |
| PostgreSQL | managed or self-hosted | single primary; also holds the job queue |

Inference is a logical module inside the worker, not a separate service. Run more worker processes for
more concurrent jobs; each one holds its own copy of the models in memory.

## Offline operation

- The application never downloads anything. The Hugging Face libraries are forced offline and every load
  uses local files only.
- A fresh clone, an installed environment and a populated `models/` directory are enough to run with no
  outbound network (the worker still needs PostgreSQL).
- No user text is sent anywhere outside the machines you operate.

## Models at runtime

Loading (`app/ml/local.py`, `app/ml/artifacts.py`):

1. The worker reads `models/manifest.json`. If it is missing or invalid, or `ML_ENABLED=false`, the worker
   runs the rule-based reading and records why.
2. All three models must be approved. For each: every listed file must exist with the recorded size and
   SHA-256; no unlisted file may be present; only `safetensors` weights are accepted; a config with
   `auto_map` is refused; the label sets must match the application's.
3. The models are loaded once at worker start, set to evaluation mode, on `ML_DEVICE`.

Any failure at any step means the worker starts in rules mode (with the reason in its log and on every
analysis it produces) instead of crashing.

Inference is bounded:

- batches of `ML_BATCH_SIZE` items; passages sorted by length within a batch to limit padding;
- a wall-clock budget `ML_MAX_SECONDS` per analysis, checked between batches; the job's heartbeat is
  renewed while it works;
- inputs are truncated at fixed token limits (extractor 256, verifier 320, retriever 192) and long
  passages are chunked at sentence boundaries;
- out-of-memory conditions are caught and reported as "engine unavailable".

On budget expiry or an engine failure the whole analysis is redone with the rules engine and says so
(`engine.notes`, a warning, and a metric). It is never a mixture.

### CPU and GPU

| | CPU (default) | GPU (`ML_DEVICE=cuda`) |
| --- | --- | --- |
| Needed | none beyond the `ml` extra | a CUDA-enabled PyTorch build and a CUDA device; the worker refuses to start the learned engine if none is available |
| Memory (estimate) | about 1.5–2 GB per worker | the same weights plus activations; a few GB of VRAM is enough |
| Tuning | `ML_THREADS`, `ML_BATCH_SIZE` | `ML_BATCH_SIZE` |
| Use when | most deployments; a résumé is a few dozen short passages | high volume, or if the CPU budget is not met |

Both paths run the same code and the same weights. Measure with `python -m ml.bench` on the target
hardware before choosing; do not rely on the estimates above.

## Graceful degradation

| Situation | What happens |
| --- | --- |
| No manifest, models not approved, files missing or changed | rules mode; every analysis says "rule-based reading" |
| Not enough memory, device error | `EngineUnavailable` → the analysis is redone in rules mode and says why |
| Analysis exceeds `ML_MAX_SECONDS` | same, with the reason "ran out of its time budget" |
| Worker down | uploads and analyses stay queued and show as waiting; nothing is lost |
| Worker dies mid-job | the job's lock expires; it is retried up to `JOB_MAX_ATTEMPTS`, then marked failed (`worker_lost`) and its résumé version or analysis is failed with it |
| Models change after an analysis | the analysis keeps its recorded engine and is shown as produced by a different method |
| PostgreSQL down | `/readyz` fails; the API returns 5xx |

The user interface shows which engine produced each analysis and, from `GET /api/v1/system/models`,
whether learned models are approved on this server. The web process reports what the manifest says; the
worker's actual state is whatever each analysis recorded.

## Configuration

Everything comes from environment variables (`.env.example` lists them, with placeholders only). In
production (the default when `APP_ENV` is unset) the application refuses to start with a placeholder
`SECRET_KEY` or database credential.

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENV` | `production` | `development`, `test` or `production`. Production enables secure cookies and HSTS and hides the API docs |
| `DATABASE_URL`, `SECRET_KEY` | placeholders | required in production |
| `STORAGE_DIR`, `MODEL_DIR` | `backend/storage`, `models` | relative paths resolve against the repository root, not the working directory |
| `TRUSTED_PROXIES` | empty | networks whose `X-Forwarded-For` is trusted for rate limiting |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | allowed browser origins |
| `ML_ENABLED`, `ML_DEVICE`, `ML_THREADS`, `ML_BATCH_SIZE`, `ML_MAX_SECONDS` | `true`, `cpu`, 4, 16, 120 | learned-engine settings |
| `JOB_MAX_ATTEMPTS`, `JOB_LOCK_SECONDS` | 3, 120 | retries and heartbeat window |
| `MAX_UPLOAD_BYTES`, `MAX_PDF_PAGES`, `MAX_JD_CHARS`, `PARSER_TIMEOUT_SECONDS`, `PARSER_MEMORY_MB` | 5 MB, 8, 20 000, 20 s, 512 MB | input limits |
| `SESSION_TTL_HOURS`, `RETENTION_DAYS` | 72, 90 | sessions and data retention (90 is a placeholder; decide before launch) |
| `METRICS_TOKEN` | empty | `/metrics` is disabled unless set |
| `RATE_LIMIT_*` | see `app/core/config.py` | per-minute limits |

Terminate TLS at the edge, and make the edge set `X-Forwarded-For`; list the edge in `TRUSTED_PROXIES`.
The in-process rate limiter is per replica, so enforce limits at the gateway too.

## The worker's container

The extraction child process is limited by the worker (wall clock, CPU seconds, address space, descriptors,
`RLIMIT_NPROC=0`, no privilege gain, capped output, empty environment, the whole process group killed on
timeout) and the worker itself sets `PR_SET_DUMPABLE=0`. These limits reduce what a parser exploit can do.
They do **not** restrict which files it can read, network access or system calls. The container must:

- have **no outbound network** except to PostgreSQL;
- use a read-only root filesystem, with a small writable temp directory and the storage directory;
- hold no secrets other than the database credential (and not the API's `SECRET_KEY`);
- run as an unprivileged user, with a seccomp profile and all capabilities dropped;
- mount `models/` read-only.

Without that isolation the sandbox only protects against denial of service, not against a compromised
parser reaching the worker's data. Verify the container configuration before exposing the service.

## Database

Use a separate migration role and a least-privilege application role:

```sql
CREATE ROLE resume_migrator LOGIN PASSWORD '…';   -- owns the schema; used only by Alembic
CREATE ROLE resume_app LOGIN PASSWORD '…';        -- used by API and worker
GRANT CONNECT ON DATABASE resume_intel TO resume_app;
GRANT USAGE ON SCHEMA public TO resume_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO resume_app;
ALTER DEFAULT PRIVILEGES FOR ROLE resume_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO resume_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

Run `alembic -c backend/alembic.ini upgrade head` before starting new code. Connections use a pool of 10
plus 5 overflow per process, `statement_timeout` 15 s and `idle_in_transaction_session_timeout` 30 s.
Size `max_connections` for roughly `15 × (API replicas + workers)` plus headroom. Schema: [database.md](database.md).

## Operations

Administrator accounts are created only on the server:

```bash
python -m app.cli grant-admin someone@example.com     # the account must exist already
python -m app.cli maintenance                         # schedule daily
python -m app.cli verify-models                       # after provisioning or changing models
```

`maintenance` deletes data past retention, removes orphaned files, fails jobs whose worker vanished, and
purges expired sessions, idempotency keys, finished jobs and old audit events. Each step is idempotent.
`GET /api/v1/admin/overview` shows counts only, no content.

Observability: `/metrics` (token-protected) exposes HTTP counts and latency by route template,
extraction outcomes, analysis duration and outcomes, analyses by engine mode, engine fallbacks by reason,
per-stage inference latency, job retries, queue depth and database statement latency. Logs are JSON with a
request id; the worker gives each job its own id. Labels never contain document content or identifiers.
Suggested alerts: queue depth growing for 10 minutes, fallbacks to rules mode, extraction or analysis
failure rate, p95 request latency, database connection saturation.

Storage lives under `STORAGE_DIR` (mode 0700; files 0600; random keys). With several hosts it must be
shared storage, or `BlobStore` needs an object-storage implementation (not written). Encrypt the volume.

## Before going live

1. Provision and approve models, or knowingly run in rules mode.
2. Run the verification steps below on the target hardware.
3. Set production secrets, TLS, proxies, the worker container and database roles as above.
4. Decide the real retention period and write backup retention that matches the privacy page.

### Checks that need an authorised environment

Nothing below has been done:

- install dependencies from reviewed lockfiles; run `pytest` (unit, then the integration tests against a
  disposable PostgreSQL), `ruff`, `mypy`, the frontend `typecheck`, `lint`, unit tests and e2e;
- run `alembic upgrade head`, the downgrade, and the migration-drift test;
- run the ML workflow in [TRAINING_AND_EVALUATION.md](TRAINING_AND_EVALUATION.md) on real, lawfully
  obtained data, and `ml.bench` on the target hardware;
- start the worker with and without approved models and confirm the mode each analysis records;
- test the worker container isolation (no network, read-only filesystem, no secrets) with a hostile
  PDF/DOCX corpus, and test the extractor limits;
- confirm the revisions in `models/manifest.json` against the model repositories;
- generate a dependency licence inventory and run a vulnerability audit on the resolved lockfiles.
