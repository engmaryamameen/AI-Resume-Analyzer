# Local verification — 2026-11-07

Scope: local portfolio use. No deployment, hosted CI run or real-world model-accuracy result is claimed.
The original uploaded review's historical validation gaps are distinct from the checks below.

| Check | Result |
|---|---|
| Full backend unit/API/PostgreSQL suite | 371 passed; one Torch-only test skipped in the local non-ML Python environment |
| ML-capable container regressions | 7 passed, including the test skipped locally |
| Frontend unit/component/query/state tests | 67 passed |
| Browser journeys | 27 passed on a fresh disposable database; upload, correction, rerun, comparison, export/deletion, pagination, error recovery, accessibility, responsive views and CSP hydration |
| Backend lint and strict typing | Ruff passed; mypy passed for 93 application source files |
| Frontend formatting, typing and lint | Passed |
| OpenAPI response contracts/static validators | Regeneration checks passed; validators require no runtime eval |
| Production frontend build | Passed |
| API and web container builds | Passed |
| npm audit, production and complete dependency tree | Zero reported vulnerabilities |
| Python runtime/dev/ML locked packages | No known vulnerabilities reported by pip-audit; CPU torch local version normalized for advisory lookup only |
| Offline semantic model smoke | Passed with network disabled, Transformers 5.22.2; pinned retrieval/support/unrelated/negation/no-probability checks |
| Process-crash fault injection | Prepare/compute/commit kills recover with one settlement; stale claim/heartbeat/cancellation/parallel-claimer regressions also pass |
| Migration round trip | Empty → 0003 → 0002 → 0003 passed on disposable DB |
| Logical backup/restore | Passed for synthetic résumé, target role, completed analysis and five evidence matches; table row counts and content digests equal |
| Real nginx exercise | Unprivileged startup, overwritten spoofed XFF, chunked 413 and slow-body timeout passed |
| Prometheus alert tests | API-down, stalled-backlog and low-storage simulated firing passed |
| Representative query plans | Owner listing uses its index with 100 owners/10,000 résumés; claim plan recorded on 5,000 jobs |
| Challenge/rules evaluation and benchmark | 71 hand-written challenge records evaluated; latency/memory recorded as local engineering measurements only |
| Secret isolation | `.env` ignored and private; worker/migration/maintenance Compose environments exclude SMTP and auth/metrics secrets; tests disable real mail |

## Container image findings — gate remains red

Trivy 0.69.3 was run against both built images after available web OS updates and removal of unused
runtime package managers. API: 49 high package/advisory matches, zero critical; web: 34 high and one
critical. These are package/advisory matches, not counts of independently exploitable application bugs.
No remaining match listed a vendor fixed version. Package dependency scans are clean; those are a
separate check from OS-image scans. Nothing is hidden by an ignore list.

The web's raw critical match is CVE-2023-45853 on bookworm `zlib1g`. Debian's tracker explains that the
vulnerable MiniZip component is not built into bookworm's zlib binary packages. The runtime also has no
MiniZip packages installed. This is a vendor-supported non-applicability assessment for that match,
not a blanket dismissal of the remaining OS findings. [Debian security tracker](https://security-tracker.debian.org/tracker/CVE-2023-45853).

A manual image-security workflow preserves the failing high/critical threshold. A future public release
requires reassessment against refreshed base images and current advisories; this local portfolio has
no production sign-off.

## Evidence and reproducibility

Machine-readable evidence is in `docs/verification.json`; raw local execution logs/reports are under
ignored `work/review-*`. The exported evidence and short synthetic walkthrough are also supplied to
the owner. Original `verification/FINAL_VERIFICATION.json` is historical evidence from another snapshot
and is not the current acceptance record.

The local backend environment is Python 3.14.4 with PostgreSQL 18.6; the ML smoke/regressions use a
Python 3.12 Linux container. CI targets Python 3.12, Node 22 and PostgreSQL 17, but has not been run
remotely for this change. Node 24.21.0 performed the host frontend checks; the Docker web build uses
Node 22. SMTP settings load, but no real email delivery is claimed or attempted. The new migration must
be applied when the owner next restarts their normal local application.

Real-world holdout collection, public staging/load tests, hosted notifications, encrypted volume/WAL
recovery and public deployment were explicitly excluded by the owner. The provenance gate intentionally
rejects absent or synthetic holdouts; no benchmark evidence was invented to satisfy the review.
