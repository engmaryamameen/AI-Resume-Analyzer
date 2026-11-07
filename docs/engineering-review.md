# Engineering review disposition

Review date: 2026-11-07. Scope: the local portfolio application, as clarified by its owner.
This project is not being deployed as a public personal-data service. Local test evidence demonstrates
engineering behavior; it does not establish production readiness or accuracy on real résumés.

## Finding disposition

| Finding | Implementation and evidence | Boundary |
|---|---|---|
| P0-01 body limit | Bounded body buffering before dispatch; malformed/duplicate lengths rejected; exact-boundary, chunked, disconnect and early-response ASGI regressions. nginx independently caps bodies and slow clients. | Memory is bounded per request; ingress capacity still needs sizing for a public service. |
| P0-02 proxy identity | Canonical IPs, malformed-chain rejection, explicit trusted edge /32, overwritten XFF, Uvicorn proxy rewriting disabled. Real nginx smoke verifies header replacement and body limits. | Local NAT legitimately shares an allowance. Multiple public gateways would need shared enforcement. |
| P0-03 authentication | Mailbox verification in production; recovery tokens hashed, 30-minute expiry, single use; reissue invalidates old token; recovery revokes all sessions/tokens and sends notification. Active-session list and owner-scoped revocation. Generic public registration and email requests. | SMTP credentials are operator supplied; tests never send real email. MFA is intentionally outside this local portfolio's scope. |
| P0-04 release evidence | Executable CI, schema-drift checks, local PostgreSQL/API/browser/build checks, offline model smoke, restore rehearsal and alert tests. | No deployment or remote green run is claimed. Hosted rollout/rollback is outside the owner's requested scope. |
| P1-01 stale queries | Explicit query keys; different-key data hidden synchronously; superseded results ignored; slow reads aborted. Regression tests cover switching, late resolution, errors, retry and unmount. | Queries intentionally do not introduce a global cache. |
| P1-02 guest identity | Complete file-object + trimmed job payload bound to retry key. Identical retries retain key; changed input creates key. Ambiguous outcomes reconcile guest state before another submission. | Allowances still apply when the server accepted a prior request. |
| P1-03 cancellation | Caller abort composed with request timeout; retry delay abortable; body-reading timeout covered; queries cancel on replacement/unmount; polling avoids overlapping reloads. | Aborting a write cannot reverse a transaction already accepted by the server. |
| P1-04 shell | Session gate, typed navigation/sidebar and independent sign-out controls; unverified workspace gate; lifecycle-safe session request. | Client gating improves presentation; backend enforces authentication, ownership, CSRF and verification. |
| P1-05 feature boundaries | Guest lifecycle hook + tagged reducer + rendering view; auth components moved into feature; report widgets split by evidence, recommendations and engine/assessment domains. | Routes import the owning feature directly; forwarding files have been removed. |
| P1-06 API contracts | Feature-owned endpoint modules, shared transport/errors, generated OpenAPI response contracts and ahead-of-time validators. CI rejects drift. Invalid JSON, HTML 200 and wrong DTO shape become normalized errors. | TypeScript domain interfaces remain readable handwritten views; runtime wire validation is generated. |
| P1-07 state conventions | Query identity/loading/error/refreshing owns remote data; guest reducer owns async lifecycle; mutation guard prevents duplicate guest submissions; routes explicitly reload after writes. | No unnecessary cache/invalidation framework is introduced. |
| P1-08 worker robustness | Competing PostgreSQL claimers, stale-claim fencing, cancellation/deletion tests, and process kills during prepare/compute/commit with exactly one recovered settlement. | This is deterministic fault injection, not a long-running production soak. |
| P1-09 real benchmark | Challenge evaluation remains reproducible; independent-holdout provenance gate rejects absent/synthetic data, group leakage, missing coverage and insufficient source groups. | No licensed/consented independent corpus exists. Owner explicitly excludes professional use; no real-world accuracy claim or fabricated labels. |
| P1-10 operations | Scrape-time DB backlog/lease/retry/progress gauges; storage gauges; Grafana dashboard; executable Prometheus alerts and simulated alert tests; restore rehearsal and incident runbooks. | Worker-local counters need separate scraping before a public multi-process deployment. No notification destination is configured or exercised. |
| P2-01 naming | Typed nav objects and feature/domain boundaries; transport/wire names remain compatible. | Broad cosmetic renaming is intentionally avoided. |
| P2-02 transactions | Registration flushes; session issuance commits registration and session atomically in local mode; public registration commits separately before mailbox activation. Token issuance/consumption serialize on the user; rollback and concurrent-consumption tests. | See transaction ownership below. |
| P2-03 privacy | Backup/WAL/download caveats added to privacy copy and retention documentation; expired account tokens cleaned up. | A live delete does not erase copies in backups. Encryption/key management is an operator responsibility if deployed. |
| P2-04 hardening | Nonce-based production script CSP, browser hydration/security tests, edge rate limits, dependency scans and patched locks, existing parser sandbox/adversarial tests retained. | Browser inline styles remain permitted; script eval/unsafe-inline are absent in production. |
| P2-05 accessibility | Existing narrow-screen, keyboard and screen-reader browser suite; accessible recovery/verification/session controls; progress status remains announced. | Native confirmation dialogs remain where adequate. |
| P2-06 API ergonomics | Comparison queries URL encoded; stable errors documented; retry only GET, no automatic mutation retry; idempotency remains backend authoritative. | Dynamic resource IDs are UUIDs validated by the API. |
| P2-07 DB/performance | Owner listing index verified on 10,000 résumés/100 owners and claim plan recorded on 5,000 jobs; retention selects at most 200 documents/guest workspaces per sweep; row purges at most 1,000; orphan keys streamed with bounded DB lookup batches. Resume-draining integration regression. | No production throughput target is claimed; capacity must be measured if scope changes. |
| P2-08 model behavior | Deterministic ambiguity/negation/date/degree/fallback suites retained; offline semantic smoke tests support, irrelevance and negation; probabilities remain absent unless calibrated. | A smoke test is not generalization evidence. |
| P2-09 portfolio | Architecture/ADRs remain; review disposition, threat model, operational runbooks, benchmark limits and verification evidence added. | A walkthrough describes the reproducible demo; production claims are expressly excluded. |

## Transaction ownership

`get_db` rolls back exceptions and closes the request session; it does not implicitly commit.
`session_scope` commits on success and rolls back exceptions. Existing feature services that commit
continue to own their units of work; callers must not assume a later rollback undoes an earlier commit.

`auth.service.register` now flushes only. `create_session` commits user, audit event and session together.
Public registration creates no session: it commits the account and requests email delivery after the
response. A failed email is recoverable by requesting another link. A failed cookie delivery is
recoverable through sign-in. `lifecycle.issue_token` flushes; the delivery task owns commit before SMTP.
`consume_token` commits the password/verification, invalidation and audit atomically. Raw tokens are
never stored in the database. SMTP is an external operation and cannot be made atomic with SQL;
delivery failure logs only an exception type and the user may reissue a link.

Lifecycle operations lock the user before token rows, serializing reissue/reset/verification. Worker
settlement and content deletion retain their established advisory-user-lock then job-row order.

## Frontend dependency and state rules

Route → feature API/hooks/components → shared transport, domain types and presentation primitives.
Routes and components import the owning feature module directly. Shared HTTP code imports no
feature. Pure UI primitives import no API. Query keys include operation and every input; old-key results
are never rendered as current. Same-key refreshes expose `refreshing` and keep their current result;
list views announce refresh activity. Forms own local values. Mutations are explicit, disable controls,
retain retry identity when appropriate, and refresh affected queries after success.

CSP validators are compiled ahead of time. Runtime `new Function`/schema compilation would break the
nonce policy and must not be reintroduced. Regenerate with:

```bash
.venv/bin/python frontend/scripts/export-contracts.py
node frontend/scripts/compile-contracts.mjs
```

## Portfolio demonstration

Use synthetic fixture documents only: guest upload → extraction/progress → evidence report → delete;
register locally → upload → review extracted text → create target role → analyze → correct evidence
and rerun → compare → export → delete résumé/account. Browser tests automate this sequence and retain
failure traces. A recording can be captured from the same local sequence; nothing is published.

Mailbox verification requires choosing a password and revokes every session/token. This prevents a
pre-registered account from retaining an attacker-chosen credential after its real owner verifies.
