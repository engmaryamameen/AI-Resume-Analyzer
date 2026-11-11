# Testing

Use the pinned baseline dependencies. Model weights are not needed for the application suites.
The CI workflow is `.github/workflows/verify.yml`.

## Backend

Integration fixtures drop and recreate their database schema. Use a dedicated disposable database;
never point `TEST_DATABASE_URL` at the application database.

```sh
.venv/bin/ruff check backend/app ml
.venv/bin/mypy --config-file backend/pyproject.toml backend/app
TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/pytest backend/tests -q
```

Tests cover file validation and parser limits, rules, model artifact policy, tenant isolation, CSRF,
versions/staleness, job retries and cancellation, deletion, exports, migrations and guest quota races.
The torch-free lab tests cover schema validation, splits, synthetic data and baseline evaluation.

## Frontend

```sh
cd frontend
npm ci --ignore-scripts
npm run format:check
npm run typecheck
npm run lint
npm test
npm run build
npx playwright install chromium
npm run e2e -- --workers=1
```

Browser tests require a production frontend, API, worker and fresh disposable application database.
The guest test consumes the network allowance, which intentionally survives report deletion. Use a
separate Compose project/volumes for QA rather than clearing the real application's quota.
`E2E_BASE_URL` selects the test server; `E2E_CHANNEL=chrome` selects an installed Chrome.

For an isolated Compose E2E stack, the **browser origin must match the API origin allowlist**.
For example, if the E2E web container is published at `http://localhost:3001`, set
`E2E_BASE_URL=http://localhost:3001` for Playwright and
`CORS_ALLOWED_ORIGINS=http://localhost:3001` for the API container **before creating it**.
Check the effective setting with `docker compose -p resume-e2e --env-file /tmp/resume-e2e.env
-f compose.yaml -f /tmp/resume-e2e-ports.yml config`; rebuild/recreate the API
if the allowed origin changes. The middleware and guest analyze endpoint both require a
matching Origin for POST requests; do not disable their checks for tests.

The guest test requires a **new disposable database/volume for each run**. A failed
first attempt may already have consumed the quota, so simply rerunning the test,
clearing the browser, or deleting the guest report does not restore the allowance.
The test fails early with a descriptive error if the allowance was already consumed.
Never remove a real user/database volume to reset E2E state.

Coverage includes guest upload, registration, extraction review, requirement edits, source inspection,
user-authored corrections, reruns, comparisons, exports, deletion and failed sign-out. Responsive tests
exercise upload, processing and limited states at ten widths, asserting column geometry as well as
horizontal overflow. Public/workspace checks include keyboard navigation, focus and automated axe scans.

## Scope

Local verification and CI establish software behavior, not production capacity, external penetration
testing, universal accessibility or learned-model accuracy. Real parser corpora, load/soak tests,
restoration drills and learned evaluation remain separate checks. See [deployment.md](deployment.md)
and [local-models.md](local-models.md).

## Real CPU model smoke check

After provisioning, run `docker compose run --rm --no-deps worker python -m app.ml.check`.
It requires the actual pinned weights and fails if the engine falls back to rules. It checks semantic
retrieval, support, unrelated text, negation and suppression of uncalibrated probabilities. The separate
CI job repeats this with the CPU runtime. These are inference integration checks, not an accuracy study.
For a provisioned full stack, `E2E_SEMANTIC=1 npm run e2e -- --workers=1` also asserts the actual model
method on completed guest/account reports. Use a fresh disposable application database.

## Failure and isolation coverage

The suite covers query identity/cancellation, frozen guest retry payloads, account-token concurrency and expiry, registration atomicity, bounded maintenance, and worker-process termination. SMTP host/from are cleared during tests to prevent delivery through developer mailbox settings. `E2E_RECORD_VIDEO=1` records synthetic browser journeys.

Before CI, run both contract checks from the repository root:

```bash
.venv/bin/python frontend/scripts/export-contracts.py --check
node frontend/scripts/compile-contracts.mjs --check
```

Regenerate without `--check` after intentional API changes. The generator reads the repository's
Prettier configuration so formatting checks and drift checks agree. No runtime validator compilation
or script-eval CSP exception is required.

Destructive integration fixtures require a disposable PostgreSQL database whose name ends in `_test`; this guard does not replace checking that the database contains no application data.

## Concurrency and transport failures

The account tests use separate PostgreSQL connections and a lock timeout to prove reset/verification cannot occur between credential verification and session issuance. Retention tests commit an actual newer version between candidate selection and deletion. The guest API test proves same-key cookie recovery without exposing a report through network identity. Its browser journey forwards the first request to the real API, then aborts the committed response and clears the cookie before asking the UI to recover with the same key. Only the transport fault is injected; extraction and analysis use the actual local worker.

The query tests resolve an older read after a simulated mutation invalidation and require a second non-overlapping read, including when the older read fails. Account-link tests run both modes under React Strict Mode. Prometheus fixtures include real scrape labels and an independently progressing instance.

## Résumé-only reviews and interface behavior

`test_resume_only.py` covers optional job descriptions, exports, comparison boundaries, and reviewer failure settlement. `test_resume_reviewer.py` validates model identity, output schema, exact quotations, and local endpoint restrictions using a controlled transport; these tests do not establish model quality.

`resume-only.spec.ts` exercises account upload, parsing, and review through the running backend. `public-interface.spec.ts` checks desktop navigation, compact footer, intermediate disclosure heights, reduced motion, and list alignment at mobile/tablet/desktop widths. Its controlled guest-availability response isolates presentation from the durable quota.
