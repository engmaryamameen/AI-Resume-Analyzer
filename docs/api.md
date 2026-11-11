# API

REST over JSON, mounted at `/api/v1`. With `APP_ENV` other than production, interactive docs are served at
`/docs` and the OpenAPI document at `/openapi.json`; those are the exact contract. This page summarises it.

## Conventions

- **Errors** share one envelope: `{"error": {"code", "message", "details", "request_id"}}`. `code` is stable
  and meant for programs; `message` is for people. Every response carries `X-Request-ID`.
- **Authentication** is a session cookie (`rs_session`, HttpOnly, SameSite=Lax, Secure in production).
  State-changing requests also need `X-CSRF-Token` equal to the `rs_csrf` cookie, and an allowed `Origin`.
  Missing or wrong → `403 csrf_failed` / `origin_not_allowed`. Unauthenticated → `401 unauthenticated`.
- **Idempotency**: `POST /resumes` and `POST /analyses` accept `Idempotency-Key` (8–128 characters of
  letters, digits, `-`, `_`, `.`). Repeating a request returns the original object; reusing the key for a
  different request is `409 idempotency_key_reused`.
- **Versions**: edits create new immutable versions. `base_version_no` must be the latest or the call
  fails with `409 stale_base_version`.
- **Pagination**: `limit` (1–50) and `offset`; lists return `{items, total, limit, offset}`.
- **Ownership**: another user's object is `404`, never `403`.
- Long work is asynchronous: creating a résumé or an analysis returns `202`; poll the object until its
  status is final.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /auth/register`, `/auth/login`, `/auth/logout` | account and session |
| `GET /auth/me` | current user |
| `POST /auth/delete-account` | `{password}`; deletes the account and everything it owns. Wrong password → `403 password_incorrect` (the session stays valid) |
| `POST /resumes` | multipart `file` (PDF or DOCX) → `202`, status `processing` |
| `GET /resumes`, `GET /resumes/{id}?version=` | list; detail with the normalised document and versions |
| `PUT /resumes/{id}/corrections` | `{base_version_no, block_edits, contact}` → new version |
| `DELETE /resumes/{id}` | idempotent; works in every state |
| `POST /job-descriptions`, `GET /job-descriptions`, `GET /job-descriptions/{id}?version=` | create from text, list, detail with requirements and warnings |
| `PUT /job-descriptions/{id}/requirements` | `{base_version_no, requirements}` → new version |
| `DELETE /job-descriptions/{id}` | delete |
| `POST /analyses` | `{resume_version_id, jd_version_id?}` → `202`; omit or send null for résumé-only review |
| `GET /analyses`, `GET /analyses/{id}` | list; detail |
| `POST /analyses/{id}/cancel` | queued: cancelled now; running: flagged, result discarded |
| `GET /analyses/{id}/report?format=json\|md\|csv` | download |
| `GET /analyses/compare?base=&target=` | compare two completed analyses |
| `GET /system/models` | whether approved learned models are installed on this server |
| `GET /guest`, `POST /guest/analyze`, `POST /guest/progress`, `DELETE /guest` | guest allowance, multipart review, progress and deletion; guest cookie/Origin rules |
| `GET /demo/samples`, `POST /demo/analyze` | public, synthetic documents, rule-based reading only |
| `GET /admin/overview`, `POST /admin/maintenance` | admin only; counts, no content |
| `GET /healthz`, `/readyz`, `/metrics` | liveness; readiness (database, storage); Prometheus (needs `METRICS_TOKEN`) |


### Requirement replacement contract

`PUT /job-descriptions/{id}/requirements` replaces the complete requirement list in a new
immutable job-description version. Every supplied item requires `text` and `kind`; `category`
defaults to `responsibility`. For an item referencing an existing requirement by `id`, **omitting**
`min_years` preserves its previous threshold (backward compatibility), **explicit `null`** clears
it, and a number from 0 to 60 replaces it. For a newly added item, omission and `null` both mean
no threshold. Items omitted from the list are removed from the new version, not the old version.

`origin` and `source_span` identify where a requirement's text came from, not whether its editable
`kind` or `min_years` annotations remain original. They are preserved only while normalized text
and category still match the previous requirement; changed text or category is marked as user
content without a source span. Earlier versions and their analyses are unchanged.

## Analysis detail

```json
{
  "id": "…", "status": "succeeded",
  "resume_version_id": "…", "latest_resume_version_id": "…",
  "jd_version_id": "…", "latest_jd_version_id": "…",
  "pipeline_version": "pipeline-3",
  "engine": {"mode": "learned|rules", "models": [{"id", "origin", "base_model", "revision", "license"}],
             "calibrated": false, "fingerprint": "…", "notes": []},
  "staleness": {"is_stale": false, "reasons": []},
  "assessments": [{"id": "requirement_evidence|document_structure|writing_style|extraction_reliability",
                   "label", "summary", "metrics": [{"name", "value", "unit", "definition"}], "limitations": []}],
  "matches": [{"requirement": {…}, "status": "supported|mentioned_only|contradicted|insufficient|no_evidence",
               "conflict": false, "probability": null, "reasons": [], "explanation": null,
               "evidence": [{"block_id", "section_kind", "excerpt", "highlights": [[0, 6]],
                             "label", "roles": [], "derived": false,
                             "retrieval_score": null, "retrieval_method": null}]}],
  "recommendations": [{"kind", "title", "detail", "block_id", "excerpt", "fill_in"}],
  "warnings": [], "limitations": [], "mentions": [ … ]
}
```

- There is no overall score or band.
- `probability` is a calibrated estimate for the match's label, or `null`. It is never derived from
  similarity.
- `excerpt` is always verbatim résumé text (at most 400 characters); `derived: true` marks computed
  statements such as total experience, which have no block.
- `retrieval_score` orders candidate passages and must not be shown as a percentage.

## Stable error codes (selection)

`unauthenticated`, `csrf_failed`, `origin_not_allowed`, `password_incorrect`, `payload_too_large`,
`file_too_large`, `empty_file`, `unsupported_file_type`, `file_type_mismatch`, `legacy_doc_unsupported`,
`docx_corrupt`, `pdf_corrupt`, `too_many_pages`, `docx_macro`, `docx_compression_ratio`,
`no_extractable_text`, `extraction_timeout`, `extraction_crashed`, `version_not_ready`,
`stale_base_version`, `idempotency_key_reused`, `analysis_not_complete`, `unknown_block`, `user_busy`,
`rate_limited`. Résumé versions that fail carry one of the extraction codes in `error_code`; analyses
carry `unexpected_<ErrorType>`, `worker_lost` or `job_lost`.

## Rate limits

Per minute, per user or address: 120 general, 10 for uploads and for creating analyses, 10 for
authentication per address (and half that per address and account for logins), 20 for the demo. They are
in-process, so enforce limits at the gateway as well.

## Account lifecycle and client transport

`POST /auth/forgot-password` and `POST /auth/request-verification` accept `{email}` and return the same
empty 204 for known/unknown addresses. Delivery configuration failure is a generic 503; throttling is
429. `POST /auth/verify-email` accepts `{token,password}` and establishes the mailbox owner's password while revoking all sessions; `POST /auth/reset-password` accepts `{token,password}`.
Both return 204 on success, 422 for invalid/expired/used tokens, and 429 for throttling. Reset revokes
all sessions and account tokens; it does not automatically sign the user in. `GET /auth/sessions`
returns current user's active session IDs and timestamps; `DELETE /auth/sessions/{id}` is owner scoped,
CSRF protected and idempotent. An unverified public user receives `email_unverified` (403) on workspace
routes; `/auth/me` remains available so verification and sign-out can be presented safely.

GET transport retries network interruptions/502/503/504 at most twice, with abortable backoff and one
overall timeout. Writes never retry automatically. Preserve an idempotency key for identical payload
retries; changed file/JD/analysis selections require another key. After uncertain guest submission,
read guest state and retain the original payload/key. An idle, unavailable quota response without a guest cookie cannot resolve the outcome: explicitly replay the original request to recover its cookie. A successful prior request can consume the quota
even if its response was lost; changing text does not reset an allowance. Processing responses must be
polled until a terminal state; acceptance is not analysis completion.

Successful JSON DTOs are validated against generated OpenAPI schemas before UI rendering. A malformed
or non-JSON 200 is `invalid_response`, a transport failure is `network_error`, and a deadline is
`request_timeout`. Caller cancellation propagates silently through the query lifecycle. HTTP errors
keep the backend's stable code/message/request ID when the envelope is well formed.

Registration returns `{user,email_verification_required}`. Local mode returns the created user and
session cookies. Public mode always returns `user: null` with verification required, for new and
existing accounts alike, and issues no session. It never fabricates an account identifier.

Guest status, progress, and accepted-upload responses use the concrete `GuestStateOut` schema, including nullable report/error/expiry fields and an enumerated state. Generated client validation rejects missing or mistyped fields.

## Optional test billing

Authenticated `GET /billing` reports configuration, credit balance and pack terms; CSRF-protected `POST /billing/checkout` accepts `Idempotency-Key` and returns a hosted Stripe URL. `POST /billing/webhook` verifies `Stripe-Signature` against raw bytes, with no browser authentication requirement. The server exclusively sets the pack price. Billing is disabled by default; see [billing.md](billing.md) for settlement and failure semantics.

## Optional role and editorial feedback

`jd_version_id` is nullable on analysis creation and responses. A résumé-only review has no requirement matches or requirement-evidence assessment. Guest `job_text` is also optional; a supplied nonempty value must meet normal validation.

Analysis detail includes nullable `review`: `summary`, `strengths`, `concerns`, `next_steps`, `model`, `model_digest`, `prompt_version`, `reviewed_blocks`, `total_blocks`, and `seconds`. Each finding contains a title, detail, and evidence entries with `block_id` and an exact `excerpt`. Invalid model output fails processing with `ai_review_unavailable`.

`GET /system/models` includes reviewer configuration separately from matching-model status. Run provenance, rather than configured status alone, identifies the method actually used. Billing routes and credit semantics are described in [billing](billing.md).
