# Architecture decisions

These choices describe the current implementation. Revisit them when measured operational or product
needs change, rather than adding infrastructure in anticipation of hypothetical scale.

## Modular monolith

The API and worker share domain packages and one transactional database. This keeps authorization,
versioning and deletion within clear transaction boundaries. Microservices would add deployment and
consistency costs without a demonstrated scaling need.

## PostgreSQL jobs

Jobs use `FOR UPDATE SKIP LOCKED`, bounded retries and renewable claims. Prepare/compute/commit keeps
long-running extraction and inference outside database transactions. Per-user advisory locks coordinate
worker commits with deletion. Revisit polling and worker capacity when queue measurements justify it.

## Local processing

One engine interface supports the pretrained semantic/rules hybrid, a rules-only reader and an experimental custom-trained profile. No hosted
AI service or generative rewriting is used. A failed learned reading is rerun completely with rules and
records its fallback reason. Model quality remains a separate evaluation problem.

## Server-side sessions

Opaque session tokens are stored as keyed hashes and sent in HttpOnly cookies. State-changing account
requests require a CSRF token and an allowed Origin. Sessions can be revoked immediately. Email
verification, password recovery, MFA and a multi-device session list are not implemented.

## Immutable versions

Corrections create a new version under a row lock and a `base_version_no` check. Reports retain their
exact inputs and show when newer versions exist. This adds storage and cleanup work but keeps evidence
reproducible and comparisons explainable.

## Requirement-level findings

A composite score would invite false precision and keyword stuffing. Each requirement instead has an
evidence status, reasons and verbatim passages. Descriptive assessments remain separate; probabilities
require calibration policy. Pipeline changes are versioned.

## Bounded extraction

Untrusted files are parsed in an isolated Python child process with time, memory, output and descriptor
limits. A parser failure cannot take down the API, but these limits are not a complete sandbox. The
worker container must restrict filesystem, privilege and network access; see [deployment.md](deployment.md).
