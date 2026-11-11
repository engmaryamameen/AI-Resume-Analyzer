# Database

PostgreSQL, accessed with SQLAlchemy 2 and migrated with Alembic. The schema is defined in
`backend/app/db/models.py`. Alembic revisions `0001_initial_schema`, `0002_guest_analysis`, `0003_account_lifecycle`, and `0004_review_credits` create the current schema.
A test compares the models with the migrated database to catch drift (`test_migrations_match_models`).
The integration suite applies migrations to an isolated database and checks model/schema agreement. See the dated verification record for actual execution results.

## Tables

| Table | Holds | Notes |
| --- | --- | --- |
| `users` | email (unique, normalised), Argon2id hash, role | `role` is `user` or `admin`; admin is granted only by `python -m app.cli grant-admin` |
| `account_tokens` | hashed, purpose-bound verification/recovery tokens and expiry | single-use; reissue replaces older tokens; reset revokes tokens and sessions |
| `guest_allowances` | keyed network hash and next allowed time | durable rolling quota; deletion does not reset it |
| `guest_analyses` | private guest token hash, owner and input references, expiry | separate temporary principal; cleanup cascades private documents |
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

Document-owned tables carry `user_id` (denormalised where needed) so ownership checks are explicit. Guest network allowances use a keyed address hash rather than an account identity.
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
- Document/job transactions touching several of {user, document, version, run, job} first take
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

The five schema revisions must be applied in order with `alembic upgrade head`. Add further
migrations; make destructive changes in two steps (expand, then contract) so old and new code can run
side by side. Run migrations with a separate role from the application's (see
[deployment.md](deployment.md#database)).

Credential verification/session issuance and password reset use the same user-row lock. Retention rechecks latest-version age inside the deletion lock, so a fresh revision cannot be removed merely because its parent appeared in an earlier scan.

## Review credits (migration 0004)

`billing_orders` records an account's Checkout intent, request key, unique Stripe session and settlement flag. `credit_entries` is a signed account ledger with constrained purchase/review/refund amounts and unique references. The account is the owner; deleting it cascades both tables. Ledger references to runs deliberately survive report deletion so a completed review does not become free by deleting it. Balance changes serialize on the existing owner advisory lock. See [billing.md](billing.md).

## Optional target role (migration 0005)

`analysis_runs.jd_version_id` is nullable for résumé-only review. No synthetic job row is created. Both résumé-only and targeted runs preserve immutable résumé input references. Cross-mode comparison is rejected. Downgrade refuses to make the column non-nullable while résumé-only runs exist, preserving their data. Source-cited editorial feedback and model provenance live in the run summary.
