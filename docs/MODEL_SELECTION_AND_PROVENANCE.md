# Model selection and provenance

Which models the application can run, why these, what is known about where they came from, and how a
model becomes usable. The machine-readable record is [`models/manifest.json`](../models/manifest.json);
this document explains it.

**Status.** All three entries are *candidates*. None is approved, no weights are in the repository, and
none has been downloaded, trained or evaluated. Until a person approves all three, the worker runs the
rule-based reading and says so on every analysis.

## Rules for any model

1. **Local only.** Weights are loaded from disk. Nothing is downloaded at startup, at install time or per
   request, and the Hugging Face libraries are forced offline (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`).
   There is no code path that sends text to a hosted model.
2. **Open weights with a licence that permits this use.** The licence of each entry is recorded, with
   notes on what the licence does not tell us (see below).
3. **Pinned.** Every entry names an exact base revision (a full 40-character commit id, enforced by the
   manifest schema) and, once provisioned, the SHA-256 and size of every file.
4. **Safe to deserialise.** Weights must be `safetensors`. Pickle-based formats (`.bin`, `.pt`, `.pkl`,
   `.ckpt`, `.npy`, `.joblib` and similar) are refused outright. A model directory may not contain a file
   the manifest does not list, and a `config.json` that declares `auto_map` (code shipped with the model)
   is refused. `trust_remote_code` is never used.
5. **Approved by a person.** `approved`, `approved_by`, `approved_on` are set by hand after reviewing the
   licence, the data description and the evaluation report. Tooling never sets them, and re-recording the
   files of an approved model clears its approval.
6. **Honest labels.** Each entry says whether it is `pretrained` (used as published) or `fine_tuned` (made
   by the training code in this repository from the named base). Reports and the UI repeat that.

## The candidates

| id | Base | Revision | Licence | Origin | Parameters (approx.) |
| --- | --- | --- | --- | --- | --- |
| extractor | `distilroberta-base` | `fb53ab8802853c8e4fbdbcd0529f21fc6f459b2b` | Apache-2.0 | fine-tuned here | 82 M |
| retriever | `BAAI/bge-small-en-v1.5` | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` | MIT | pretrained, unchanged | 33 M |
| verifier | `cross-encoder/nli-distilroberta-base` | `b14d131f9d32668a5e6a982729b57ff6ed5dfcbd` | Apache-2.0 | fine-tuned here | 82 M |

The revision ids were read from the model repositories when the manifest was prepared. Confirm each one
against the source when provisioning; the manifest check only proves that files match what *you* recorded.

### Why these

The choice is driven by size, licence and the interface the pipeline needs. It is **not** based on
measured accuracy on résumé text; that comparison has not been run (see Alternatives).

- **Extractor: `distilroberta-base`.** A small encoder (6 layers) with a fast tokenizer, which the
  character-offset decoding requires. Apache-2.0. Small enough to fine-tune on a single modest GPU and to
  run on CPU. The two heads on top (BIO tagging, mention role) are trained here, so this is a fine-tuned
  model, not a pretrained NER model.
- **Retriever: `bge-small-en-v1.5`.** A compact English embedding model with a retrieval-oriented training
  objective and a documented query prefix. MIT. Used as published: fine-tuning it would need real
  requirement–passage pairs, which we do not have.
- **Verifier: `cross-encoder/nli-distilroberta-base`.** A sentence-pair classifier already trained for
  natural-language inference (entailment / neutral / contradiction), which is close to the task. Its
  three-way head is replaced by a five-way head and the encoder is fine-tuned on verification data.

### Alternatives considered, and what would change the decision

| Alternative | Why not now |
| --- | --- |
| A hosted LLM or API | Excluded by requirement: no third-party AI services. |
| A local generative LLM for judging | Hard to bound for hallucination, large, slow on CPU, and its output cannot be calibrated the way a classifier's can. |
| spaCy / off-the-shelf résumé NER | Does not give mention *roles* (negated, hedged), and its training data and licence need their own review. |
| `all-MiniLM-L6-v2` for retrieval | Comparable size and Apache-2.0. A reasonable swap; retrieval evaluation (`ml.evaluate`) would show whether it does better on this data. |
| Larger encoders (base/large) | More accuracy is plausible, at several times the memory and latency. Worth testing only if the small models fail on the evaluation. |
| `deberta-v3-*` | Often strong on NLI, but its tokenizer relies on extra packages, which adds to what has to be reviewed. Not evaluated here. |

Swapping a model means changing its manifest entry, retraining or re-provisioning, re-running evaluation
and approving again. The pipeline does not change.

## What the licences cover, and what they do not

The licences above govern use of the weights. They do not settle everything:

- The base models were pretrained on large text collections (for DistilRoBERTa, web text, books and
  Wikipedia-derived corpora through its teacher; for the NLI cross-encoder, SNLI and MultiNLI on top).
  Those corpora carry their own terms, and the model cards describe them only in general terms. The
  manifest's `license_notes` field records this for each entry. Review the model cards before approving.
- BGE's authors describe its training data only in general terms.
- Fine-tuned weights derive from their base. Distributing them would carry the base licence's
  conditions (Apache-2.0: licence text and notices; MIT: copyright notice). This repository does not
  distribute weights.
- A model's licence says nothing about the résumés it will later read. Those are the operator's data and
  stay on the operator's server ([security-and-privacy.md](security-and-privacy.md)).

## Provisioning (offline)

1. On a machine with network access, fetch each base model at the exact revision and verify the commit id.
   Copy only the files you need to the server by a transfer you trust (`config.json`, tokenizer files,
   `model.safetensors`).
2. Train the two fine-tuned models ([TRAINING_AND_EVALUATION.md](TRAINING_AND_EVALUATION.md)); each run
   writes the weights, a run record (base weights hash, dataset digest, configuration, environment, code
   version) and the calibration.
3. Place each model in `models/<directory>/` and run `python -m ml.make_manifest --models-dir models
   --run <run directory> --report <evaluation report>`. This records every file's size and SHA-256, the
   calibration, and the training provenance. It never approves anything.
4. Review: licence and data notes, evaluation report against the promotion criteria
   (`python -m ml.compare`), limitations. Then edit the manifest to set `approved`, `approved_by` and
   `approved_on` for each entry.
5. Verify on the server: `python -m app.cli verify-models`. At startup the worker checks every checksum
   again before loading, and fails closed to the rule-based reading if anything differs.

## The manifest

| Field | Meaning |
| --- | --- |
| `display_policy` | `max_ece` and `min_validation_samples`: when probabilities may be shown. A policy choice, not a result. |
| `id`, `directory` | which role the entry fills and where its files live under `models/` |
| `origin` | `pretrained` or `fine_tuned` |
| `base_model`, `base_revision` | the published model and exact commit it starts from |
| `license`, `license_notes` | licence identifier and what it leaves open |
| `training` | for fine-tuned models: run id, dataset digest, code version, evaluation report path |
| `files` | path, SHA-256 and size of every file; nothing else may be in the directory |
| `calibration` | temperature, validation sample count and ECE per head (`role`, `verdict`) |
| `approved*` | the human approval |

The application's fingerprint (stored with every analysis) is a hash of the approved files and
calibrations, or `rules` when the learned models are not all in use.

## Resource estimates

*Estimates from published parameter counts, not measurements.*

| Item | Estimate |
| --- | --- |
| Weights on disk (float32) | extractor ≈ 330 MB, retriever ≈ 135 MB, verifier ≈ 330 MB; about 0.8 GB together |
| Worker memory with all three loaded (CPU) | on the order of 1.5–2 GB including the runtime; confirm with `ml.bench` |
| GPU | not required. A GPU with a few GB of memory is enough for inference and for training at small batch sizes |

Latency and throughput are deliberately not estimated here: they depend on the machine, thread count and
batch size. Measure them on the deployment hardware with `python -m ml.bench`
([INFERENCE_AND_DEPLOYMENT.md](INFERENCE_AND_DEPLOYMENT.md)).

## Third-party software

Runtime and training dependencies (`torch`, `transformers`, `safetensors`) are declared in
`backend/pyproject.toml` under the optional `ml` extra and keep their own licences. A generated licence
inventory has not been produced; do that from the resolved lockfile when you build the environment.
