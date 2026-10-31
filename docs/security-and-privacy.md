# Security and privacy

What is protected, how, and what is deliberately not claimed. The user-facing version of the privacy
section is the `/privacy` page of the app.

Automated security/workflow tests cover the controls below. They do not constitute a penetration
test, compliance certification or guarantee against a determined attacker.

## Assets and threats

| Asset | Main threats | Main controls |
| --- | --- | --- |
| Résumés and job descriptions (personal data) | other users, a compromised parser, log or report leaks, over-retention | ownership predicates, private storage, bounded extraction, redaction, retention and deletion |
| Accounts and sessions | credential stuffing, session theft, CSRF | Argon2id, rate limits, keyed token hashes, SameSite cookies, CSRF token and Origin check |
| Model files | tampering, planted code, unsafe deserialisation | manifest checksums, `safetensors` only, no `auto_map`, human approval ([provenance](local-models.md)) |
| Availability | oversized or hostile files, expensive inputs | size and page limits, resource-limited extraction, bounded inference with a time budget, rate limits |

## Controls

**Accounts.** Passwords are hashed with Argon2id (at least 12 characters, at most 256). Login performs a
dummy hash for unknown emails so timing does not reveal which accounts exist. Sessions store only keyed
hashes of the session and CSRF tokens. Deleting an account needs the current password, and a wrong password
returns 403 so a client does not mistake it for being signed out. Administrators are created only on the
server (`python -m app.cli grant-admin`); there is no registration-time or request-time path to the role.

**Requests.** Cookies are HttpOnly (session), SameSite=Lax and Secure in production. State-changing requests
need a matching `X-CSRF-Token` and an allowed `Origin`. Bodies are size-limited as they stream. Every
response has a request id, `nosniff`, `no-store`, a `default-src 'none'` content security policy and
`no-referrer`; production adds HSTS and hides the API docs. Client addresses for rate limiting come from
`X-Forwarded-For` only when the direct peer is a configured trusted proxy, using the last untrusted hop, so
clients cannot spoof their way out of a limit. Production refuses to start with placeholder secrets, and
`APP_ENV` defaults to production.

**Uploads.** File type is decided by content and must match the extension; names never reach the
filesystem (storage keys are random 32-character hex, validated on every access). Extraction runs in a
child process with a wall-clock timeout (the whole process group is killed), CPU, memory, descriptor and
output limits, no further processes, no privilege gain and an empty environment. DOCX macros, compression
bombs and XML entity expansion are rejected; PDFs are page-limited. Failures fail closed with a stable
code and never produce invented text.

**Process-isolation limits.** It does not restrict which files the child can read, network access or
system calls, so on its own it only limits denial of service. The worker must run in a container with no
outbound network, a read-only filesystem, no secrets beyond the database credential, a seccomp profile and
no capabilities ([deployment.md](deployment.md#the-workers-container)). The worker
also sets `PR_SET_DUMPABLE=0` so the child cannot read its environment through `/proc`.

**Models.** Local only; checksum-verified; approved by a person; never downloaded by the application;
no pickle-based formats; no code shipped with a model.

**Exports and logs.** Reports neutralise spreadsheet formulas (CSV), escape Markdown, strip control and
bidirectional-override characters and remove emails and phone numbers from every text field; they are sent
as attachments. Logs are JSON, redact emails, phone numbers and tokens in messages, and withhold fields
such as `text`, `content`, `email` and `excerpt`. Metric labels are low-cardinality enumerations, never
content or identifiers.

**Prompt injection.** There is no language model that reads résumé text as instructions, so text inside a
résumé cannot redirect the system. Keyword stuffing and fabricated claims are not detected
([local-models.md](local-models.md)).

## Privacy

| Data | Why | Where |
| --- | --- | --- |
| Email, password hash | sign in | `users` |
| Session and CSRF token hashes, expiry | stay signed in | `sessions` |
| Uploaded file | re-reading the original | private store, random key |
| Extracted text and structure | review, correction, analysis | `resume_versions` |
| Job description text and requirements | analysis | `job_description_versions`, `job_requirements` |
| Analysis results and recommendations | history, comparison | `analysis_runs`, `requirement_matches` |
| Audit events | security trail: action, target id, request id, time | `audit_events`; never content |
| Idempotency keys | safe retries | purged after 24 hours |

Not collected: analytics or advertising scripts, third-party counters, fingerprinting, geolocation, or
résumé text in logs. Raw IP addresses are used in memory for rate limiting; guest quotas store only a keyed address hash.

**No third parties.** Documents are never sent to an outside service. Models run on the operator's machine
from local files. The application has no outbound calls other than to its own database.

**Training on user data.** The application does not use uploaded documents to train or tune models. Doing
so would contradict the retention and deletion described here.

| Data | Default retention | Mechanism |
| --- | --- | --- |
| Résumés, versions, files, analyses | 90 days without activity (`RETENTION_DAYS`; a placeholder, decide before launch) | `python -m app.cli maintenance`, scheduled daily |
| Sessions | until expiry (72 h) | maintenance |
| Idempotency keys | 24 h | maintenance |
| Finished jobs | 30 days | maintenance |
| Audit events | 365 days | maintenance |

**Deletion.** Deleting a résumé removes its versions, analyses and matches, flags running jobs so workers
discard their work, and unlinks the stored file after the commit. Orphaned files (a crash between write and
commit) are removed by maintenance. Deleting a job description removes the analyses that used it. Deleting an
account removes sessions, jobs and everything private, and leaves an anonymous audit row. After deletion,
old report links return 404. Reports the user already downloaded cannot be recalled. Database backups are
outside this code: define backup retention that matches what the privacy page promises.

**Data subject requests.** Export is available per analysis (JSON, Markdown, CSV) and the résumé's
normalised text is shown in the app. A complete export of everything held about an account is not
implemented.

## Not claimed

No compliance certification (GDPR, SOC 2 or similar) is claimed; operators remain responsible for their
legal basis, notices and processors. No claim of resistance to a determined attacker is made before the
container isolation and the checks in [deployment.md](deployment.md#release-checks)
have been done.

## Guest reviews

One accepted review reserves a network allowance for 24 hours. PostgreSQL advisory locks serialize
reservations; the allowance survives report deletion, cookie removal and API restarts. Failed processing
restores it. People sharing a public address share the allowance. Configure trusted proxies and sanitize
forwarded addresses before public hosting; otherwise the direct proxy peer conservatively shares a quota.

A separate non-login principal owns temporary documents. The HttpOnly, SameSite=Strict `mn_guest` cookie
is restricted to `/api/v1/guest` and authorizes only its report, never an account session. It is Secure
in production. Guest mutations require an allowed Origin. Retrying the same file, posting and request
key recovers the same work while its reservation is active.

Guest access expires after 24 hours. The hourly maintenance service removes expired documents and
results within the next cleanup interval. Manual deletion removes them sooner without resetting the
allowance. A guest who registers starts a separate workspace; their temporary report is not migrated.

## Dependency audit policy

CI rejects moderate-or-higher production advisories and high-or-critical advisories anywhere in the
frontend tree. The pinned ESLint toolchain currently inherits the moderate
[minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249). It is development-only; patterns
come from repository configuration, not résumé uploads. The patched minimatch major changes its API,
so a compatible lint-tool upgrade remains necessary.
