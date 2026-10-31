# Local analysis models

## Default semantic profile

The worker uses published pretrained models unchanged. It has no hosted inference dependency and does
not train on uploads. Provision once with `docker compose --profile setup run --build --rm model-setup`,
then start the application with `ML_ENABLED=true`. Setup downloads roughly 420 MB; inference works offline.

| Role | Published model | Pinned revision |
| --- | --- | --- |
| Passage retrieval | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Evidence comparison | [nli-MiniLM2-L6-H768](https://huggingface.co/cross-encoder/nli-MiniLM2-L6-H768) | `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d` |

Both declare Apache-2.0 licenses. Model cards, license text, tokenizers and safetensors are downloaded
from pinned revisions. `backend/app/ml/semantic-models.json` records every file size and SHA-256.
The generated `models/semantic-manifest.json` must match that lock; the worker verifies all checksums
before loading, forbids custom code and pickle weights, and uses local-files-only loading. Weights and
the generated manifest are ignored by Git. Re-run setup to restore missing or damaged files.

Attention-masked mean pooling and normalized embeddings rank passages. The NLI model compares a passage
with the requirement hypothesis. Its internal softmax thresholds are conservative routing heuristics,
not calibrated confidence estimates. No probabilities or invented ATS score are shown. Entity roles,
requirements, dates and final evidence decisions remain deterministic. Lists of skills cannot establish
hands-on experience merely because an NLI model agrees.

Reports identify this hybrid method as `semantic`, including both model revisions. Missing artifacts,
load errors or time-budget failures produce an explicitly labeled `rules` report. Settings describes
provisioned files, not a guarantee of worker health; the completed report is the source of truth.
The `/demo` route always uses rules so it works independently of model provisioning.

These models were not fine-tuned or evaluated on representative résumé data in this repository.
They can misread negation, paraphrases, long passages or domain-specific language. This is a working
local inference system, not a claim of validated hiring accuracy. The custom training lab below is a
separate experimental profile and is not required for the semantic setup.

## Evidence pipeline

1. Extract text in the bounded parser process and normalize sections, blocks and date ranges.
2. Extract editable required/preferred job requirements with source spans.
3. Link terms through the local taxonomy and distinguish affirmed, listed, negated and hedged mentions.
4. Retrieve candidate passages with BM25 in rules mode or embeddings in learned mode.
5. Reconcile passage verdicts with mention roles; preserve support/contradiction conflicts.
6. Report source-linked findings, descriptive assessments and user-completed editing templates.

Degrees use level comparisons. Experience is computed from dated roles without counting overlapping
periods twice; it is not attributed to individual skills. Retrieval values order passages and are never
presented as probabilities. The decision table lives in `backend/app/ml/decision.py`.

## Experimental custom-trained profile

| Component | Base | Use |
| --- | --- | --- |
| Extractor | `distilroberta-base` | Repository training code adds BIO and mention-role heads |
| Retriever | `BAAI/bge-small-en-v1.5` | Published embedding model, used unchanged |
| Verifier | `cross-encoder/nli-distilroberta-base` | Repository training code adds five evidence labels |

These are candidates, not evaluated production models. The exact revisions and license declarations
are in `models/manifest.json`. Preserve Apache-2.0/MIT notices with provisioned artifacts and review the
license of each selected revision and its training data.

The worker loads only local, approved, checksum-verified files. Unlisted files, pickle weights,
`auto_map`, incompatible labels and missing provenance are rejected. The inference worker never downloads weights; only the explicit provisioning command does.
For the experimental profile, all three components must pass approval. Missing artifacts, device failure or a time-budget overrun
cause a complete, labeled fallback to rules; a result is never a silent mixture of methods.

## Data and evaluation

Records are defined in `ml/schema.py`: extraction spans with mention roles, retrieval relevance and
verification verdicts. Use the same normalization and decoding in training and inference. Label list
mentions separately from claims of use; preserve negation, uncertainty, alternative requirements and
conflicts. Audit offsets and adjudicate ambiguous labels.

Split at document/template-family level to prevent near-duplicate leakage. Keep calibration separate
from validation and the final test set. Synthetic examples and held-out challenge sets test software
behavior; real accuracy requires consented, representative labeled documents. Never train on uploads
without a separate, lawful data policy.

The lab fits temperatures on calibration data and checks ECE on validation data. Probabilities are
shown only when sample-count/ECE policy passes, the extractor and verifier agree, and no conflict is
present. The defaults (ECE <= 0.05 and at least 500 validation samples) are policy thresholds, not results.
Report per-label precision/recall, span F1, retrieval recall, calibration, failure rates and domain/error
slices. Compare against rules on identical held-out inputs and benchmark on the target hardware.

## Offline workflow

Install the optional `ml` extra and provision the exact base revisions locally first. Replace the
angle-bracket paths below with those local directories. Seeds for `ml.synth --split-seed` and
`ml.split --seed` must agree (both default to 13).

```bash
# 1. Data
python -m ml.synth --out ml/data/generated/synthetic.jsonl --per-pattern 12 --seed 7
python -m ml.split --out ml/data/generated/splits --prefix syn ml/data/generated/synthetic.jsonl
python -m ml.validate --splits ml/data/generated/splits
python -m ml.validate ml/data/challenge/*.jsonl

# 2. Baseline (no models needed)
python -m ml.evaluate --engine rules --out ml/runs/baseline/report.json \
    --data ml/data/generated/splits/test.*.jsonl ml/data/challenge/*.jsonl

# 3. Train
python -m ml.train_extractor --base-dir <distilroberta-base> --splits ml/data/generated/splits \
    --config ml/configs/extractor.json --out ml/runs/<run>
python -m ml.train_verifier  --base-dir <nli-distilroberta-base> --splits ml/data/generated/splits \
    --config ml/configs/verifier.json  --out ml/runs/<run>

# 4. Calibrate (temperature on the calibration split, ECE on the validation split)
python -m ml.calibrate --run ml/runs/<run> --splits ml/data/generated/splits
cp -r <bge-small-en-v1.5 files> ml/runs/<run>/retriever          # the retriever is used unchanged

# 5. Evaluate on the same files as the baseline, then benchmark
python -m ml.evaluate --candidate ml/runs/<run> --out ml/runs/<run>/report.json \
    --data ml/data/generated/splits/test.*.jsonl ml/data/challenge/*.jsonl
python -m ml.bench --candidate ml/runs/<run> --out ml/runs/<run>/bench.json \
    --data ml/data/generated/splits/test.*.jsonl

# 6. Decide
python -m ml.compare --candidate ml/runs/<run>/report.json --baseline ml/runs/baseline/report.json \
    --policy ml/configs/promotion.json --bench ml/runs/<run>/bench.json
python -m ml.make_manifest --models-dir models --run ml/runs/<run> --report ml/runs/<run>/report.json
```

Each run records configuration, artifact checksums, code/data digests, environment and metrics. Review
those records and the promotion policy before setting `approved`, `approved_by` and `approved_on` in
the manifest. Keep generated datasets, run directories and weights out of Git.

## Limits

Reading order can be wrong in columns or tables. Scans need OCR, which is not implemented. The English
rules can miss paraphrases, unfamiliar job domains, abbreviated dates and unusual degree names.
Keyword stuffing and fabricated claims are not detected. Calibrated estimates describe a model label,
not whether a person is qualified or likely to be hired. Use the extracted text and source passages to
review results; do not rank or screen people with this tool.

## Background

- [Greenhouse parsing limitations](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse)
  motivate visible extraction and manual corrections; this app does not emulate Greenhouse.
- [Sentence Transformers similarity](https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html)
  explains embedding comparisons; similarity alone is not evidence of a qualification.
