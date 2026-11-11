# Threat model and deployment boundaries

Assets: résumé originals and extracted text; job descriptions; evidence reports; password hashes;
session/CSRF and account-link tokens; private storage and PostgreSQL. Trusted operators can access
stored data and backups. Reports support document editing rather than automated hiring decisions.

| Boundary / attacker | Controls | Remaining scope |
|---|---|---|
| Anonymous browser → ingress | body/time caps, aggregate throttles, XFF replacement, CSP nonce, security headers | configure HTTPS and DNS at the deployment boundary |
| Browser → API | backend authentication/ownership, CSRF for session mutations, Origin checks, input schemas and pagination bounds | mailbox delivery requires operator-configured SMTP |
| Account recovery attacker | explicit missing-account recovery response, per-IP/identity throttles, random hashed tokens, expiry/reissue/single use, reset revokes sessions | recovery reveals whether an email is registered; mailbox compromise is not solved by email recovery; MFA is not implemented |
| Malicious document → extractor | signature/ZIP/PDF validation, resource-limited child, private file modes, bounded output, worker isolation | resource limits are not a complete syscall/filesystem sandbox |
| Competing/crashed workers | DB leases, heartbeat, SKIP LOCKED, attempt fencing, atomic settlement, deletion ordering | measure recovery and capacity under the deployed workload |
| Model artifact supply chain | immutable upstream revisions, SHA-256/size checks, safetensors only, no remote code, offline runtime | independent model accuracy is unmeasured |
| Logs/backups/operator | content-free bounded logging, pseudonymous quota keys, live deletion and retention | backups/WAL/downloads require separate retention and encryption policies |

No résumé or password is used in metric labels. Account email failure logs contain only exception type.
Recovery tokens use URL fragments so access logs/Referer do not receive them, and the UI removes the
fragment after loading. Link scanners cannot consume a token without submitting the confirmation form.
SMTP delivery and notification are external side effects; local tests mock them and never send mail.

Public mode requires email ownership before workspace access. Local development/test mode allows the
synthetic demo account workflow without email; that bypass must not be confused with public policy.
Existing accounts become unverified on migration and need to request verification if public mode is
chosen. Verification is not MFA. Session entries expose creation/expiry and current-session identity;
there is no device fingerprint collection. Compromised-session recovery revokes every session.

The project uses synthetic/challenge examples and pretrained local models. It makes no independently
measured accuracy, fairness, calibration or generalization claim for real applicants. Missing evidence
means only that this document did not establish the requirement; it is not proof that a person lacks a
skill. Reports are editing aids and are not suitable for automated hiring or applicant ranking.

Mailbox verification requires choosing a password and revokes every session/token. This prevents a
pre-registered account from retaining an attacker-chosen credential after its real owner verifies.
