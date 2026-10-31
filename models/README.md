# Local models

Run `docker compose --profile setup run --build --rm model-setup` once to provision the default
semantic profile. It fetches two published pretrained models at pinned revisions, verifies file sizes
and SHA-256, and retains their cards and Apache-2.0 licenses. The lock is
`backend/app/ml/semantic-models.json`; generated `semantic-manifest.json` and weights stay outside Git.

The worker loads these local files with `ML_ENABLED=true`, without outbound network access or a hosted
AI service. Rules handle entity roles and dates. `python -m app.ml.check` tests real inference and fails
on fallback. See [model details](../docs/local-models.md) for provenance and limits.

## Experimental custom-trained profile

`manifest.json` lists the three models the learned analysis needs and what is known about each. The
weights themselves are not in Git (see `.gitignore`).

| id | role | origin |
| --- | --- | --- |
| `extractor` | tags skills, degrees, fields, organisations, titles and certifications in a résumé, and says how each is claimed (affirmed, listed, mentioned, negated, hedged) | fine-tuning workflow in `ml/`; artifacts not bundled |
| `retriever` | finds the résumé passages that may relate to a requirement | published model, used as is |
| `verifier` | decides whether a passage supports, only mentions, contradicts or says too little about a requirement | fine-tuning workflow in `ml/`; artifacts not bundled |

Every entry starts unapproved. While any of the three is unapproved the worker uses the rule-based reading,
and every analysis says so.

## Providing the models (offline)

1. On a machine with internet access, fetch each base model at the exact revision in `manifest.json` and
   copy the files to the server by whatever transfer you trust. Only `safetensors` weights and the tokenizer
   and config files are accepted; pickle-style files and models that ship their own code are refused.
2. Train the two fine-tuned models as described in `docs/local-models.md`. Training writes the
   weights, the calibration and an evaluation report.
3. Put each model in `models/<directory>/` and run `python -m ml.make_manifest` to record file sizes and
   SHA-256 checksums. Review the licence, the data provenance and the evaluation report.
4. Set `approved`, `approved_by` and `approved_on` on the entries you accept. The worker verifies every
   checksum when it loads a model and refuses a changed or extra file.

Details of the loading rules are in `docs/deployment.md`.
