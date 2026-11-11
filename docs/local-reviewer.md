# Local source-cited résumé review

The editorial reviewer is separate from deterministic document checks and embedding/NLI requirement matching. It reviews a résumé without a job description; an optional role supplies additional context. It critiques the document's communication, not the person's employability. There is no validated hiring prediction or real-world accuracy claim.

## Setup

The optional model weighs about 2.5 GB. Provision it with internet access before starting the private inference service:

```bash
bash backend/scripts/provision_reviewer.sh
docker compose --profile ai-review up -d --wait review-model
docker compose exec review-model ollama list
```

Set the following in the ignored repository `.env`:

```dotenv
REVIEWER_ENABLED=true
REVIEWER_MODEL=qwen3:4b-instruct
REVIEWER_MODEL_DIGEST=
REVIEWER_TIMEOUT_SECONDS=300
BILLING_REQUIRE_CREDITS=false
```

Read the full model digest from the service's `/api/tags` response and pin it in `REVIEWER_MODEL_DIGEST`. Recreate API and worker after changing settings. The model service has no published port and joins only the internal network. Its cache is mounted from ignored `models/reviewer`; deleting this folder requires provisioning again.

```bash
docker compose --profile ai-review up --build -d --wait
```

The service is bounded to 5 GB RAM and three CPUs, with one parallel inference slot and one loaded model. This is a local development configuration; CPU inference can take minutes. It is not a measured production capacity guarantee. An unavailable model fails the review explicitly; it does not silently substitute generic text presented as AI output. Disable `REVIEWER_ENABLED` to use the explicitly labeled baseline document/matching checks.

## Input and output boundaries

The worker supplies up to 16,000 characters of non-header résumé blocks (at most 1,800 per block) and up to 6,000 characters of optional role text. Contact patterns are redacted before inference. This reduces exposure but is not a guarantee that arbitrary personal information is anonymized. Upload limits and extraction uncertainties remain visible. Each report records model identity, digest, prompt version, time and reviewed/total block counts.

A strict output schema requires strengths, concerns and editing priorities. Every finding must cite an existing block and an exact substring of both the submitted text and original document. Invalid, truncated or ungrounded output fails instead of entering the report. Exact quotation validation establishes source linkage; it cannot prove that the model's interpretation is correct. The UI asks the user to verify edits and never fabricate achievements.

Document and role text are untrusted data. The model receives no tools or external retrieval. Inference runs outside database transactions; existing background heartbeats and fenced settlement protect cancellation, deletion and lease recovery. A failed charged review returns its credit transactionally, and a failed guest run restores the guest allowance. JSON, Markdown and CSV exports include redacted AI findings.

Résumé-only runs store a null job revision, not a fabricated role. Comparison allows two résumé-only runs; mixed résumé-only and targeted comparisons are rejected because the contexts differ. Migration `0005` makes this relationship nullable and refuses a downgrade while such runs exist.
