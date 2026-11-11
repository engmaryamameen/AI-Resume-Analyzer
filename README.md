# Rolemaker

Source-cited résumé review, with optional job-description matching.

Rolemaker helps people understand how their résumé communicates experience, ownership, and impact. Upload a document, inspect its extracted text, and review specific feedback alongside the passages that support it. Add a job description to examine evidence against a particular role.

![Rolemaker](docs/images/landing.jpg)

## Features

- **Document processing:** text-based PDF and DOCX uploads, structured extraction, extraction uncertainties, and editable text revisions.
- **Résumé review:** optional local language-model feedback covering strengths, concerns, and editing priorities, with validated source quotations.
- **Role matching:** optional job descriptions, editable requirements, and requirement-level evidence with contradictions and uncertainty.
- **Revision history:** immutable inputs, stale-report detection, reruns, and comparisons between compatible reviews.
- **Reports:** contact-redacted JSON, Markdown, and CSV exports.
- **Guest access:** temporary private reports with a durable network allowance and recovery after an interrupted response.
- **Accounts:** email verification, password recovery, session management, and document/account deletion.
- **Test payments:** optional Stripe sandbox Checkout with signed webhooks and transactional review credits.

The interface supports responsive navigation, keyboard interaction, source expansion, and reduced motion. Upload, processing, empty, error, and completed states use shared components.

Rolemaker reviews document content. It does not verify credentials, rank candidates, replicate an employer's ATS, or predict hiring outcomes. Model interpretations require human review; résumé-domain accuracy has not been independently established.

## Stack

| Layer | Technology |
| --- | --- |
| Web | Next.js 15, React 19, TypeScript, Tailwind CSS, CSS modules |
| API | FastAPI, Pydantic, generated OpenAPI response validators |
| Data | PostgreSQL, SQLAlchemy 2, Alembic |
| Jobs | PostgreSQL queue, renewable leases, fenced commits, bounded retries |
| Extraction | pypdf and bounded DOCX XML parsing in a resource-limited subprocess |
| Analysis | Deterministic checks, optional embedding/NLI matching, optional Qwen review through local Ollama |
| Operations | Docker Compose, nginx, Prometheus metrics and alert rules |
| Tests | pytest, Vitest, Testing Library, Playwright, axe |

## Architecture

The backend is a modular monolith. API handlers validate requests and enqueue work; workers perform extraction and analysis outside database transactions. Ownership checks, row/advisory locks, and fenced settlement coordinate mutations, cancellation, deletion, and job recovery.

```mermaid
flowchart LR
  Browser --> Edge[nginx]
  Edge --> Web[Next.js]
  Web --> API[FastAPI]
  API --> DB[(PostgreSQL)]
  API --> Storage[(Private document storage)]
  Worker --> DB
  Worker --> Storage
  Worker --> Parser[Bounded extraction subprocess]
  Worker --> Matching[Local matching models]
  Worker --> Reviewer[Optional private Ollama service]
```

The browser uses the same origin for the application and `/api/v1`. Model inference stays on operator-controlled infrastructure. No hosted AI API is required. Payment and email integrations have separate outbound connections and credentials.

See [architecture](docs/architecture.md), [design decisions](docs/decisions.md), [database design](docs/database.md), and [API reference](docs/api.md).

## Quick start

Requires Docker Engine with Compose. From the repository root:

```bash
[ -f .env ] || cp .env.example .env
```

Configure `.env` with `APP_ENV=development`, database settings, and a signing key. To start with deterministic checks, set both `ML_ENABLED=false` and `REVIEWER_ENABLED=false`:

```bash
docker compose up --build -d --wait
```

Open [localhost:3000](http://localhost:3000). Upload a résumé and start a review directly, or add a target role. The [synthetic demonstration](http://localhost:3000/demo) uses the actual rules pipeline without retaining personal documents.

For optional models:

- **Semantic requirement matching:** set `ML_ENABLED=true` and run `docker compose --profile setup run --build --rm model-setup` before recreating the worker. See [local models](docs/local-models.md).
- **Editorial AI review:** provision the local reviewer, pin its model digest, enable `REVIEWER_ENABLED`, and start the `ai-review` Compose profile. See [reviewer setup](docs/local-reviewer.md). CPU inference can take minutes.

Containers serve built images. After editing source, rebuild the affected services with `docker compose up --build -d`. To stop the application, run `docker compose stop`; include enabled profiles when stopping their services. Database and upload volumes persist. Do not use `down --volumes` when preserving data.

[Quickstart](docs/quickstart.md) covers ports and troubleshooting. [Environment settings](docs/environment.md) documents configuration, including SMTP and model options. Never commit `.env` or expose server credentials through `NEXT_PUBLIC_*` variables.

## Native development

Requires Linux, PostgreSQL, Node 22.12+, npm, and Python 3.12. Configure a dedicated database in `.env` before migrating. Disable optional models until their dependencies and artifacts are installed.

```bash
python3 -m venv .venv
.venv/bin/pip install -c backend/requirements-dev.lock -e 'backend[dev]'
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend ci --ignore-scripts
```

Start each process in a separate terminal from the repository root:

```bash
# API
.venv/bin/uvicorn app.api.main:app --app-dir backend --port 8000
```

```bash
# Worker
PYTHONPATH=backend .venv/bin/python -m app.jobs.worker
```

```bash
# Frontend
npm run dev
```

The root `dev` command starts only the frontend; PostgreSQL, API, and worker must also run. `BACKEND_URL` defaults to `http://localhost:8000`. Stop any container using port 3000 before starting the native frontend.

## Review pipeline

1. Validate file size, extension, content type, page count, and DOCX structure.
2. Extract text in a bounded subprocess and normalize sections, passages, entities, and dates.
3. If supplied, extract job requirements and retrieve relevant résumé passages.
4. Produce document checks and classify requirement evidence, retaining uncertainty and contradictions.
5. If enabled, generate editorial feedback locally and validate its schema and exact source citations.
6. Commit a complete report with immutable input references and processing provenance.

Semantic matching may fall back to clearly labeled rules. The editorial reviewer fails explicitly on unavailable, incomplete, or invalid output; it never substitutes generic checks as AI-written feedback. Missing document evidence does not establish missing experience. Uploaded documents are not used for training.

Account users can correct extraction, create another résumé revision, and rerun a review. Résumé-only runs store no job revision; comparisons require compatible review contexts. Guests receive one accepted review per network per rolling 24 hours. Failed processing restores that allowance; deleting a successful report does not.

## Payments

Stripe integration supports **test payments only**, with a one-time pack of five review credits for $5 USD. `BILLING_ENABLED=true` enables sandbox Checkout; `BILLING_REQUIRE_CREDITS=true` separately enables spending credits on new account reviews. Both default to false.

Signed provider events settle credits; a browser redirect never confirms payment. Duplicate delivery and analysis retries do not duplicate accounting. Failed or cancelled charged reviews return their credit. Live Stripe keys and events are rejected. See [billing configuration](docs/billing.md).

## Testing

```bash
.venv/bin/ruff check backend/app ml
.venv/bin/mypy --config-file backend/pyproject.toml backend/app
.venv/bin/python frontend/scripts/export-contracts.py --check
node frontend/scripts/compile-contracts.mjs --check
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test
npm --prefix frontend run build
```

Backend integration fixtures recreate the public schema. Use only a disposable PostgreSQL database whose name ends in `_test`:

```bash
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/rolemaker_test .venv/bin/pytest backend/tests -q
```

Browser journeys require a separate application database, API, worker, and production frontend:

```bash
cd frontend
npx playwright install chromium
E2E_BASE_URL=http://localhost:3000 npm run e2e -- --workers=1
```

The suite covers real upload/review workflows, tenant isolation, concurrency, failure recovery, exports, and responsive interactions. [Testing](docs/testing.md) explains isolation, transport fault injection, model checks, and test boundaries. CI is defined in [.github/workflows/verify.yml](.github/workflows/verify.yml).

## Deployment and security

Deploy the web, API, workers, private storage, and PostgreSQL together behind HTTPS. Configure production secrets, allowed origins, trusted proxies, authenticated metrics, SMTP, retention, backups, and resource limits before accepting personal documents. Production accounts require mailbox verification.

Sessions and account-link tokens are hashed; passwords use Argon2id. State-changing account requests require CSRF and origin checks. Private resources are owner-scoped. Extraction limits, defensive exports, cancellation fencing, and deletion locks provide additional boundaries.

Use [deployment](docs/deployment.md), [operations](docs/operations.md), [security and privacy](docs/security-and-privacy.md), and the [threat model](docs/threat-model.md) for release and recovery procedures. Validate model behavior, provider delivery, image advisories, restore procedures, and capacity on the target environment before launch.

## License

[MIT](LICENSE). Third-party fonts, dependencies, and model licenses are documented in [NOTICE.md](NOTICE.md).
