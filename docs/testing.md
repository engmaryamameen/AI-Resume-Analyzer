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
