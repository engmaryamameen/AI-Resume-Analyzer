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
| `POST /analyses` | `{resume_version_id, jd_version_id}` → `202` |
| `GET /analyses`, `GET /analyses/{id}` | list; detail |
| `POST /analyses/{id}/cancel` | queued: cancelled now; running: flagged, result discarded |
| `GET /analyses/{id}/report?format=json\|md\|csv` | download |
| `GET /analyses/compare?base=&target=` | compare two completed analyses |
| `GET /system/models` | whether approved learned models are installed on this server |
| `GET /demo/samples`, `POST /demo/analyze` | public, synthetic documents, rule-based reading only |
| `GET /admin/overview`, `POST /admin/maintenance` | admin only; counts, no content |
| `GET /healthz`, `/readyz`, `/metrics` | liveness; readiness (database, storage); Prometheus (needs `METRICS_TOKEN`) |

## Analysis detail

```json
{
  "id": "…", "status": "succeeded",
  "resume_version_id": "…", "latest_resume_version_id": "…",
  "jd_version_id": "…", "latest_jd_version_id": "…",
  "pipeline_version": "pipeline-2",
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
