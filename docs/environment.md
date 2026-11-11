# Environment reference

Backend settings come from `backend/app/core/config.py`, process environment, and the repository `.env` (environment wins). Settings are cached per process: restart affected services after changes. Never commit `.env`, paste secrets into issues, or put server secrets in `NEXT_PUBLIC_*` variables. Production is the default when `APP_ENV` is omitted.

## Required and operational settings

| Variable | Default / purpose |
| --- | --- |
| `APP_ENV` | `production`; `development` for local HTTP, `test` for isolated verification. Production uses Secure cookies, requires verified mailboxes, and rejects placeholder secrets. |
| `SECRET_KEY` | Placeholder rejected in production; generate a long random signing/HMAC key. Changing it invalidates existing session, account-link and guest token hashes. |
| `DATABASE_URL` | SQLAlchemy `postgresql+psycopg://...`; native API/worker/migrations must point to the same dedicated application database. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000`; comma-separated exact browser origins. Update when changing the public port/origin. |
| `TRUSTED_PROXIES` | Empty; comma-separated trusted peer IPs/CIDRs. Never trust arbitrary forwarded addresses. Compose trusts the fixed nginx peer. |
| `STORAGE_DIR` | `backend/storage`; private uploads, inaccessible as static files. Compose uses `/data/storage`. |
| `MODEL_DIR` | `models`; approved manifests and weights. Compose mounts `/app/models`. |
| `SESSION_TTL_HOURS` | `72`. |
| `RETENTION_DAYS` | `90` since the most recent document revision. Eligibility is rechecked under deletion locks. Cleanup must be scheduled. |
| `METRICS_TOKEN` | Empty; production metrics require operator configuration. Treat it as a credential. |

## Account mail

| Variable | Purpose |
| --- | --- |
| `PUBLIC_APP_URL` | `http://localhost:3000`; canonical link origin. Production email requires HTTPS. |
| `SMTP_HOST` | Empty disables delivery. Use the provider's implicit-TLS SMTP host. |
| `SMTP_PORT` | `465`; the implementation uses `SMTP_SSL`, not STARTTLS on port 587. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Provider credentials; a provider app password when required. Never a browser-side variable. |
| `SMTP_FROM` | Provider-authorized sender address. |

Development registration works without SMTP. Recovery and verification email requests report delivery unavailable when configuration is missing. Known and unknown eligible addresses receive the same public response when delivery is configured. Delivery failures are logged without addresses/tokens and require requesting a new link; delivery is not durable across a process crash.

## Resource and queue controls

| Variable | Default |
| --- | --- |
| `MAX_UPLOAD_BYTES` | `5242880` (5 MiB) |
| `MAX_PDF_PAGES` | `8` |
| `MAX_JD_CHARS` | `20000` |
| `PARSER_TIMEOUT_SECONDS`, `PARSER_MEMORY_MB` | `20`, `512` |
| `JOB_MAX_ATTEMPTS`, `JOB_LOCK_SECONDS` | `3`, `120` |
| `RATE_LIMIT_PER_MINUTE` | `120` |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `10` |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | `10` |
| `RATE_LIMIT_DEMO_PER_MINUTE` | `20` |

Rate counters are process-local; durable guest allowances are in PostgreSQL. More API replicas require an operator's aggregate traffic/rate-limit strategy.

## Local inference

| Variable | Default / meaning |
| --- | --- |
| `ML_ENABLED` | `true`; set `false` for the rules-only installation. Missing/rejected artifacts fall back to rules with recorded provenance. |
| `ML_DEVICE` | `cpu` (`cuda` also accepted when provisioned) |
| `ML_THREADS`, `ML_BATCH_SIZE`, `ML_MAX_SECONDS` | `4`, `16`, `120` |

Compose configures offline Hugging Face/Transformers flags for the worker. Model provisioning is a separate network-enabled step, not an inference-time download. Python 3.12 and `backend/requirements-ml.lock` are the pinned CPU runtime.

## Compose, frontend and verification

| Variable | Meaning |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Initialize the Compose PostgreSQL database. Password required. Defaults for user/database are `margin` / `margin_notes`; preserve existing volume credentials. Compose constructs its own internal database URL. |
| `APP_ENV_FILE` | Defaults to `.env`; select another file for service injection. Compose interpolation still follows Compose's environment/`--env-file` rules, so use `docker compose --env-file ...` when selecting interpolation values too. |
| `WEB_PORT` | Host nginx port, default `3000`, bound to loopback. |
| `BACKEND_URL` | Next.js rewrite target; native default `http://localhost:8000`, Docker build uses `http://api:8000`. Rebuild after changing it. |
| `PORT`, `LISTEN_HOST` | Native standalone web listener; default server port `3000`, startup script defaults host to loopback. |
| `TEST_DATABASE_URL` | Disposable PostgreSQL only. Integration fixtures drop/recreate its public schema. Never the application database. |
| `E2E_BASE_URL`, `E2E_CHANNEL`, `E2E_RECORD_VIDEO` | Browser target, optional installed Chrome, optional recording. Defaults are `http://localhost:3000`, bundled Chromium, and recording on failures. |

Destructive integration fixtures require a disposable PostgreSQL database whose name ends in `_test`; this guard does not replace checking that the database contains no application data.

## Optional Stripe test billing

`BILLING_ENABLED` defaults to `false`. With it off, account analyses remain free. With it on, `STRIPE_SECRET_KEY` must start with `sk_test_` and `STRIPE_WEBHOOK_SECRET` must contain the endpoint/listener signing secret (`whsec_`). Public URLs are derived from `PUBLIC_APP_URL`; prices and credits are fixed server-side. No browser Stripe key or client-selected price is accepted. See [billing.md](billing.md).

## Local editorial reviewer

The reviewer is independent of `ML_ENABLED` (embedding/NLI requirement matching).

| Variable | Default / meaning |
| --- | --- |
| `REVIEWER_ENABLED` | `false`; enable only after provisioning and testing the local model. |
| `REVIEWER_URL` | `http://review-model:11434`; only loopback or the private Compose service is accepted. |
| `REVIEWER_MODEL` | `qwen3:4b-instruct` |
| `REVIEWER_MODEL_DIGEST` | Empty; pin the provisioned digest to reject unexpected model changes. |
| `REVIEWER_TIMEOUT_SECONDS` | `300`; bounded to 30–600 seconds. |
| `BILLING_REQUIRE_CREDITS` | `false`; with billing enabled, explicitly opt into charging for new account reviews. |

See [local reviewer setup](local-reviewer.md) for resource limits, provisioning and failure behavior.
