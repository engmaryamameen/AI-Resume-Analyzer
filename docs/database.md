# Database

PostgreSQL, accessed with SQLAlchemy 2 and migrated with Alembic. The schema is defined in
`backend/app/db/models.py` and created by a single migration, `backend/alembic/versions/0001_initial_schema.py`.
A test compares the models with the migrated database to catch drift (`test_migrations_match_models`).
Neither has been run yet.

## Tables

| Table | Holds | Notes |
| --- | --- | --- |
| `users` | email (unique, normalised), Argon2id hash, role | `role` is `user` or `admin`; admin is granted only by `python -m app.cli grant-admin` |
| `sessions` | keyed hash of the session token, hash of the CSRF token, expiry | raw tokens exist only in the browser |
| `resume_documents` | one logical résumé per row | content lives in versions |
| `resume_versions` | immutable versions: status, error code, storage key, extension, SHA-256, size, `normalized`, `parseability` | `source` is `upload` or `user_correction`; unique `(document_id, version_no)` |
| `job_descriptions`, `job_description_versions` | the posting and its immutable versions (`paste`, `user_correction`) | raw text per version |
| `job_requirements` | one row per requirement of a version | kind, category, origin (`extracted`, `inferred`, `user`), terms, `min_years`, source span; unique `(jd_version_id, ordinal)` |
| `analysis_runs` | one résumé version against one job-description version | status, pipeline version, model fingerprint, engine info, extracted mentions, assessments, summary (recommendations, limitations), warnings |
| `requirement_matches` | one row per requirement per run | status, calibrated probability or NULL, conflict flag, reasons, evidence, explanation |
| `processing_jobs` | the queue | kind, target id, status, attempts, lock expiry, cancel flag, last error |
| `idempotency_keys` | claimed keys with a request hash and the result id | unique `(user_id, scope, key)` |
| `audit_events` | action, target type/id, request id, detail | no content; `user_id` becomes NULL when the user is deleted |

Every private table carries `user_id` (denormalised where needed) so each ownership check is one predicate.
Deleting a user cascades to everything private.

## Integrity rules enforced by the database

- `analysis_runs`: `(status = 'succeeded') = (assessments IS NOT NULL)`. A succeeded run without results
  cannot exist, and results without success cannot exist.
- `requirement_matches`: status in the five evidence statuses; probability NULL or between 0 and 1;
  unique `(run_id, requirement_id)`.
- `processing_jobs`: kind and status enumerations, `max_attempts >= 1`, unique `(kind, target_id)` so a
  target has at most one job per kind; a partial index serves claiming.
- Enumerations (`role`, versions' `status`/`source`, requirement `kind`/`category`/`origin`) are CHECK
  constraints.
- Foreign keys cascade on delete from user, document, version, run and requirement, so deleting a résumé
  removes its versions, analyses and matches.

## Concurrency

- The queue is claimed with `SELECT … FOR UPDATE SKIP LOCKED`.
- Every transaction touching several of {user, document, version, run, job} first takes
  `pg_advisory_xact_lock` for the user, then row locks (`backend/app/db/locks.py`). See
  [architecture.md](architecture.md#lock-order).
- Version creation locks the parent row and checks `base_version_no` against the latest version
  (`backend/app/db/versioning.py`).
- Sessions use `statement_timeout` 15 s and `idle_in_transaction_session_timeout` 30 s, so a stuck
  statement or an abandoned transaction cannot hold locks indefinitely.

## JSON columns

`normalized` (blocks, sections, entries, contact, uncertainties), `parseability`, `engine`, `extraction`,
`assessments`, `summary`, `warnings`, `terms`, `source_span`, `reasons` and `evidence` are JSONB, validated
by Pydantic models on the way in and out (`documents/schema.py`, `analysis/schema.py`,
`ml/contracts.py`). They are read as whole documents, never queried field by field, which is why they are
not normalised into tables.

## Migrations

There is one initial migration because no deployed data exists yet. Once a database is in use, add
migrations; make destructive changes in two steps (expand, then contract) so old and new code can run
side by side. Run migrations with a separate role from the application's (see
[deployment.md](deployment.md#database)).
