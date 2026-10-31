# Run Rolemark

## Docker Compose

Requires Docker Engine with the Compose plugin. The default configured profile runs two pretrained models locally on CPU. No AI account,
API key or GPU is required. One-time model setup downloads about 420 MB and verifies pinned checksums.
Reserve at least 3 GB for the worker; build/setup require network access, analysis does not.

From the repository root, copy `.env.example` to `.env` **only if you do not already have one**, then run:

```sh
docker compose --profile setup run --build --rm model-setup
docker compose up --build -d
```

Open http://localhost:3000. Upload a synthetic résumé and add a target role for a real local-model review.
The `/demo` route is a separate rules-only sample. Each real report records its actual engine in Document insights. Compose starts a private
PostgreSQL service, applies migrations, starts the API, worker and hourly cleanup service, then the web app. Only the frontend
is published, on the loopback interface. Named volumes retain documents and database data across restarts.

```sh
docker compose ps
docker compose logs -f api worker
docker compose exec api python -m app.cli maintenance
docker compose down                 # keeps your data
```

`WEB_PORT=3001` selects a different host port; also set `CORS_ALLOWED_ORIGINS=http://localhost:3001`
when using it. `APP_ENV_FILE=.env.example` can select a separate environment file without overwriting
an existing `.env`.

The backend's env file needs `APP_ENV=development` for local HTTP; production session cookies require HTTPS.
If you already have a `.env`, set `ML_ENABLED=true` for semantic inference and add `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` from the example.
The Compose-internal database URL is constructed from those values, not the host's `DATABASE_URL`.
Use URL-safe database credentials or percent-encode their URL representation before configuring it.
`BACKEND_URL` is baked into the frontend at build time. Rebuild when changing the proxy destination.

## Native development

Python 3.12+ on Linux, Node 22.12+, npm and PostgreSQL are required. The parser uses Linux resource limits.
Create a dedicated database and set `DATABASE_URL` in `.env`. The example's port 55432 is illustrative;
match it to your own PostgreSQL listener (Compose does not publish a database port).

```sh
python3 -m venv .venv
.venv/bin/pip install -c backend/requirements-dev.lock -e 'backend[dev]'
.venv/bin/alembic -c backend/alembic.ini upgrade head
mkdir -p backend/storage
.venv/bin/uvicorn app.api.main:app --app-dir backend --port 8000
```

For native neural inference use Python 3.12, install `backend/requirements-ml.lock`, and run
`PYTHONPATH=backend .venv/bin/python -m app.ml.provision --models-dir models` once.
Python 3.14 can run the baseline app but is not the pinned CPU model runtime.

In a second terminal, from the root:

```sh
cd backend
../.venv/bin/python -m app.jobs.worker
```

In a third:

```sh
cd frontend
npm ci --ignore-scripts
npm run dev
```

## Verify

Use a **disposable** database for `TEST_DATABASE_URL`: integration tests drop and recreate its public schema.
Never point that setting at your application database.

```sh
.venv/bin/ruff check backend/app ml
.venv/bin/mypy --config-file backend/pyproject.toml backend/app
TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/pytest backend/tests -q
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npx playwright install chromium
# Start production web, API, worker and a separate application DB before running browser journeys.
npm run e2e -- --workers=1
```

`E2E_CHANNEL=chrome` selects an installed Google Chrome instead of Playwright's bundled Chromium.
Generate the upload fixture with `python3 frontend/tests/e2e/fixtures/make_fixture.py` from the root.
The GitHub Actions workflow provisions separate test/application databases and runs the full workflow.

## Before public hosting

Set `APP_ENV=production`, random signing/database/metrics credentials, HTTPS termination and the correct
allowed origin. Use a dedicated migration role and restricted application DB role; the local Compose
example shares a role to simplify development. Configure backups, retention, a daily maintenance task,
and validate restoration. The worker uses a read-only root, dropped capabilities, a process/memory limit
and an internal network; a parser exploit can still reach its mounted documents and database, so do not
represent subprocess resource limits as a complete filesystem sandbox. Review the detailed deployment
and privacy documents before collecting real personal data. Learned-model evaluation is separate.

Guest policy and retention details are in [security and privacy](security-and-privacy.md#guest-reviews). Browser tests need a fresh
application database because the guest allowance deliberately survives report deletion and browser resets.
