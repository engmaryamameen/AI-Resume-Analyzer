# Testing

What the tests cover and how to run them. **No test has been run.** The suites below were written and
checked only for syntax and import consistency; their outcomes are unknown.

## Backend (`backend/tests`)

```bash
pip install -e "backend[dev]"            # add ,ml only if you also want to run the lab's model code
cd backend
pytest -m "not integration"              # unit and HTTP contract tests, no database
TEST_DATABASE_URL=postgresql+psycopg://… pytest -m integration   # needs a DISPOSABLE PostgreSQL
ruff check . && mypy app
```

`TEST_DATABASE_URL` must point at a database you can drop: the fixtures delete the `public` schema and
re-create it with the migration. Tests run with `ML_ENABLED=false` and an empty model directory, so they use
the rule-based engine and need no model files.

| Area | File | What it pins down |
| --- | --- | --- |
| Decision table, calibration | `unit/test_decision_and_calibration.py` | weaker claim wins, negation outranks a mention, conflicts are never support, probabilities only when calibrated, temperature and ECE behaviour |
| Text, BIO decoding, BM25, degrees | `unit/test_ml_text_and_degrees.py` | chunk offsets, span decoding, `MS Office`/`Boston, MA` are not degrees, degree levels |
| Model supply chain | `unit/test_model_supply_chain.py` | approval, checksums, unlisted files, pickle formats, `auto_map`, fingerprint, display policy, the committed manifest |
| Rules engine | `unit/test_rules_engine.py` | roles (affirmed, listed, negated, hedged), verdicts, budget, passages |
| Requirements | `unit/test_requirements.py` | kinds, upgrades, years, degrees, alternatives, inferred requirements, source spans |
| Pipeline | `unit/test_analysis_pipeline.py` | statuses on the demo documents, verbatim evidence, no scores, engine stated, inert injected text, fallback on budget expiry |
| Documents | `unit/test_normalize.py`, `unit/test_validation_and_extraction.py` | sections, dates, contact, wrapped lines; upload validation; sandbox limits, bombs, macros, entities, timeouts |
| Reports, logs, storage | `unit/test_reports_logging_storage.py` | formula neutralisation, redaction, private storage and traversal |
| Configuration, networking | `unit/test_config_and_network.py` | fail-closed production, path resolution, trusted proxies |
| ML lab (torch-free) | `unit/test_ml_lab.py` | markup, validation, leakage detection, split determinism, synthetic data, metrics, the evaluation harness on the rules engine, challenge-set integrity |
| HTTP contract | `api/test_http_contract.py` | error envelope, security headers, CSRF/Origin, auth guards, body limit, demo, model status |
| Workflows | `integration/test_workflows.py` | upload to report, idempotency, tenant isolation, CSRF, admin only by role, failure and retry bounds, worker-lost jobs, cancellation, deletion in every state, account deletion, corrections and staleness, comparison, schema constraints, migration drift |

Not covered: concurrent two-session lock-order tests (deadlock between deletion and a worker commit),
real PDF corpora, load and soak tests, and anything that needs model weights. The lab's encoding,
training, calibration and benchmark code needs `torch` and real models; it has no automated test.

## Frontend (`frontend/tests`)

```bash
cd frontend
npm install --ignore-scripts    # after reviewing and committing a lockfile
npm run typecheck && npm run lint && npm test      # vitest + testing-library + axe
npm run e2e                                         # Playwright against a running stack
```

Unit tests cover the evidence badge and labels, evidence cards, the engine panel in both modes, the rule
that probabilities appear only when the server sends one, assessment metrics with their definitions, the
before/after diff and the comparison notes. The end-to-end spec drives the main journeys against a stack
started as in the README. Tests assert some exact wording, so copy edits can break them.

## Evaluating the models

Model quality is not tested by the suites above. See [TRAINING_AND_EVALUATION.md](TRAINING_AND_EVALUATION.md).
