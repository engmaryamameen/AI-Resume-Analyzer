# Local models

The application runs models that are stored on this machine and nothing else. It never downloads a model,
at startup or while serving a request, and it never calls a hosted inference service.

`manifest.json` lists the three models the learned analysis needs and what is known about each. The
weights themselves are not in Git (see `.gitignore`).

| id | role | origin |
| --- | --- | --- |
| `extractor` | tags skills, degrees, fields, organisations, titles and certifications in a résumé, and says how each is claimed (affirmed, listed, mentioned, negated, hedged) | base model fine-tuned in this repository |
| `retriever` | finds the résumé passages that may relate to a requirement | published model, used as is |
| `verifier` | decides whether a passage supports, only mentions, contradicts or says too little about a requirement | base model fine-tuned in this repository |

Every entry starts unapproved. While any of the three is unapproved the worker uses the rule-based reading,
and every analysis says so.

## Providing the models (offline)

1. On a machine with internet access, fetch each base model at the exact revision in `manifest.json` and
   copy the files to the server by whatever transfer you trust. Only `safetensors` weights and the tokenizer
   and config files are accepted; pickle-style files and models that ship their own code are refused.
2. Train the two fine-tuned models as described in `docs/TRAINING_AND_EVALUATION.md`. Training writes the
   weights, the calibration and an evaluation report.
3. Put each model in `models/<directory>/` and run `python -m ml.make_manifest` to record file sizes and
   SHA-256 checksums. Review the licence, the data provenance and the evaluation report.
4. Set `approved`, `approved_by` and `approved_on` on the entries you accept. The worker verifies every
   checksum when it loads a model and refuses a changed or extra file.

Details of the loading rules are in `docs/INFERENCE_AND_DEPLOYMENT.md`.
