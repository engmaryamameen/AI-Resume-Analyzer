# Local operations and recovery

These runbooks describe observable failure handling for the local portfolio. There is no hosted
production deployment or production SLA. Do not run destructive drills against a database containing
real data. The integration suite creates a disposable schema and intentionally destroys its contents.

## Worker outage

Symptoms: increasing `job_backlog_oldest_seconds`, increasing `job_last_progress_age_seconds`, and
possibly expired leases. Check worker logs for bounded error codes, database availability, storage
permissions and memory limits. Restart the worker only after correcting the cause. Running jobs are
reclaimed after lease expiry; the attempt number fences stale completion. After max attempts, target
and job settle failed together. Confirm backlog drains and every target has one terminal outcome.

Reproduce safely with `tests/integration/test_worker_process_crash.py`: a real child is killed during
prepare, compute and commit; PostgreSQL rolls back uncommitted settlement; recovery may commit once.
The lease/cancellation/deletion suites cover concurrent claimers and stale heartbeats.

## Database outage

`/readyz` fails and the authenticated metrics scrape fails, making Prometheus `up` zero. Do not
repeatedly resubmit writes: preserve the idempotency key and reconcile state after reconnecting. Check
PostgreSQL availability, credentials, connection limits and disk. Restore connectivity, then restart
workers if needed. Confirm migration revision, successful readiness and backlog progress.

## Storage exhaustion

`storage_free_bytes / storage_total_bytes` below 0.15 alerts. Stop accepting uploads at the ingress
while preserving read access. Inspect volume usage without opening users' documents. Run bounded
maintenance; never manually delete files still referenced by résumé versions. Increase capacity before
re-enabling upload. Verify parser temp space separately. Database WAL and its volume need their own
infrastructure capacity alert; the application gauge measures the upload volume only.

## Model failures

A failed load or timed-out/OOM inference falls back to rules and records provenance. Check artifact
checksums, immutable revisions, memory and offline smoke check. Do not hide fallback in the UI. Keep
rules mode available while investigating. Never relax safetensors/checksum/local-only restrictions to
make a model load. Every optional dependency update must pass the offline smoke and semantic tests.

## Backup and restore rehearsal

The checked-in rehearsal script copies a disposable database into a newly named restore database,
compares every table's row count and content digest, then drops the restore. It never drops or migrates the source:

```bash
ALLOW_DISPOSABLE_RESTORE=1 TEST_DATABASE_URL=postgresql+psycopg://user@localhost/resume_test \
  .venv/bin/python backend/scripts/restore_rehearsal.py
```

Production is outside scope. If that changes, encrypted DB backups and upload-volume snapshots must
be captured consistently, retained under a published policy, and restored into isolated infrastructure.
A logical DB-only rehearsal does not prove recovery of stored documents, encryption keys or point-in-
time WAL. Restored backups may resurrect deleted content: reapply a deletion ledger before exposing
any restored service. Keep that ledger private, access-controlled, and subject to its own retention.

## Schema rollback

Migration `0003` adds email verification and hashed account tokens. Back up first. Test locally with
`alembic downgrade 0002` then `alembic upgrade head` on a disposable database. Downgrade deletes token
and verification state, so old links become invalid. The previous application cannot enforce email
verification; rolling code back is not a safe public launch strategy. Prefer a forward correction if
authentication policy depends on the new schema. No migration rollback is automatically executed
against the developer's existing application database.

## Alerts and dashboard

`deploy/alerts.yml` includes API-down, backlog-without-progress, expired leases, retry backlog, low
storage and ML fallback rules. Validate deterministic firing with:

```bash
docker run --rm --network none -v "$PWD/deploy:/rules:ro" -w /rules \
  --entrypoint /bin/promtool prom/prometheus:v3.10.0 test rules alerts.test.yml
```

Import `deploy/grafana-dashboard.json` and choose a Prometheus datasource. Scrape `/metrics` with a
Bearer token from `METRICS_TOKEN` on the private API network; never publish that endpoint or token.
Database/volume gauges are computed by the API from shared state, so they remain useful across workers.
Inference/extraction counters are worker-local; scraping only the API does not collect worker counters.
The optional fallback alert requires a worker metrics collector before use. For this local portfolio,
logs and report provenance are the authoritative demonstration of fallback. Notification routing and
real failure notifications are deliberately not configured.

## Ingress and identity

`compose.yaml` publishes only nginx on host loopback. nginx forwards `/api/` directly to the API,
replaces supplied forwarding headers, buffers bodies, caps them at 5 MiB + 256 KiB and times out slow
bodies after 10 seconds. The API trusts only nginx's fixed address, `172.30.44.10/32`, and Uvicorn is
started with `--no-proxy-headers`. The web and API have no published ports. Do not add a second ingress
without redesigning trust and rate-limit aggregation. TLS termination is not configured for local use.
If a remote TLS terminator is ever introduced, trust only its exact network address in nginx and
preserve the public scheme. Never trust arbitrary XFF from the internet.

Run `python deploy/verify-ingress.py` for a real unprivileged nginx test with a local echo backend:
spoofed XFF is replaced, chunked excess receives JSON 413 and an incomplete body times out. Unit tests
cover IPv4/IPv6, chained proxies and malformed chains. NAT sharing of an IP allowance is intentional
and explained to visitors. In-process throttles are per API; the single nginx boundary enforces an
aggregate gateway limit across API replicas. Multiple gateways need shared limiting before scaling.

Only the API receives SMTP/account secrets. Worker, migration and maintenance services use explicit
environment allowlists, with no SMTP password, metrics token or session signing key. Their settings
contain non-authentication placeholder keys because those processes do not issue credentials.
