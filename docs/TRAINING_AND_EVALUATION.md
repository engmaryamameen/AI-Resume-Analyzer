# Training and evaluation

How the two fine-tuned models are trained, calibrated and judged, and how a model earns approval. All of
this is the `ml/` package; it needs the optional `ml` dependencies and, for training, ideally a GPU.

**Status.** None of it has been run. The code was written and statically checked only; there are no
training logs, no metrics and no benchmark numbers anywhere in this repository, and none are claimed.
Treat every command below as untested until you have run it.

## What is implemented, and what is not

| Capability | State |
| --- | --- |
| Dataset schema, markup, validation, leakage checks, grouped splitting | implemented (torch-free parts unit-tested in `backend/tests/unit/test_ml_lab.py`, not yet run) |
| Deterministic synthetic data generator | implemented |
| Hand-written challenge sets | implemented (small) |
| Rule-based baseline engine and BM25 retrieval baseline | implemented |
| Extractor training (token + role heads), verifier training | implemented, never run |
| Temperature-scaling calibration, ECE | implemented (pure functions unit-tested, not yet run); calibration script never run |
| Evaluation harness, comparison against promotion criteria, benchmark script | implemented; the harness is exercised by a test against the rules engine; the rest never run |
| Manifest recording | implemented, never run |
| Real annotated data, trained weights, evaluation results, latency and memory measurements | **do not exist** |
| Zero-shot NLI baseline, hyper-parameter search, class-imbalance variants, k-fold evaluation | not implemented |

## Setup

Run these in a separate, authorised environment, from the repository root.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e "backend[ml,dev]"          # review and lock dependencies first
export PYTHONPATH=backend                 # the lab imports the application's contracts
```

Base models must already be on disk (see [MODEL_SELECTION_AND_PROVENANCE.md](MODEL_SELECTION_AND_PROVENANCE.md)).
The training and evaluation code sets the Hugging Face libraries offline and passes
`local_files_only=True`; it will fail rather than download.

## Workflow

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

`ml/runs/` and `ml/data/generated/` are git-ignored. A run directory holds `extractor/`, `verifier/` and
`retriever/` (each loadable by the engine), `extractor-run.json` and `verifier-run.json` (see below),
`calibration.json` and the reports. `ml.synth --split-seed` must equal `ml.split --seed` (both default to 13), because retrieval
distractors are chosen within a split.

## Training

**Extractor** (`ml/train_extractor.py`). The base encoder with two heads (`app/ml/models.py`). Input is
the context line paired with the text, exactly as in inference. Loss is token cross-entropy over BIO
labels (ignoring non-text tokens) plus `head_loss_weight` × cross-entropy of the role head, computed at
the first token of each SKILL, DEGREE and CERT span with teacher forcing. The epoch with the best
validation score is kept, where the score is the mean of span micro-F1 and role accuracy on gold spans,
both computed with the *same decoder the application uses* (`extract_batch`), so validation measures what
production will do.

**Verifier** (`ml/train_verifier.py`). `AutoModelForSequenceClassification` loaded from the NLI base with
a new five-way head (`ignore_mismatched_sizes`), label order from `VERDICT_LABELS`. Loss is cross-entropy
with inverse-frequency class weights. The epoch with the best validation macro-F1 is kept.

**Shared mechanics** (`ml/trainer.py`): seeded Python and PyTorch RNGs, deterministic algorithms where
available (with warnings, not errors, for operations that have none), AdamW with weight decay excluded for
biases and norms, linear warm-up and decay, gradient clipping, early stopping on the validation score.
Hyper-parameters are in `ml/configs/*.json` and are starting points; they have not been tuned.

**Run record.** Each training run writes `<model>-run.json`: base directory name and the SHA-256 of the
base weights, the configuration, Python / torch / transformers / CUDA versions, the git commit, the
per-epoch history, and the dataset digest with record counts. `ml.make_manifest` copies the run id,
dataset digest and code version into the model's manifest entry.

**Weights** are exported as `safetensors` only (`save_pretrained(safe_serialization=True)`; the extractor
via `safetensors.torch.save_file` with a `head_config.json` recording the label sets).

**Reproducibility.** The same data, configuration, seed, library versions and hardware should reproduce a
run; GPU non-determinism can still cause small differences. Nothing here has been checked.

## Calibration

`ml.calibrate` fits one temperature per head by minimising negative log-likelihood on the *calibration*
split (golden-section search over log T), then reports expected calibration error (10 equal-width
confidence bins) on the *validation* split, which the temperature never saw. The role head is calibrated
on gold spans so that its calibration does not depend on span detection. The output
(`calibration.json`) is recorded in the manifest. Whether probabilities are shown is then decided by the
manifest's display policy ([LOCAL_ML_ARCHITECTURE.md](LOCAL_ML_ARCHITECTURE.md)). Temperature scaling
fixes over- or under-confidence on data like the calibration split; it does not make a model right, and
it says nothing about data unlike what it was fitted on.

## Evaluation design

`ml.evaluate` takes labelled files and one engine and writes a JSON report that names the engine, the
data files, their digest and counts per source. It measures the pipeline stages **separately**:

| Stage | Measured how | Reported |
| --- | --- | --- |
| Extraction (spans) | exact match of (start, end, type) against gold | precision, recall, F1 per entity type and micro; F1 per tag slice |
| Extraction (roles) | on gold spans: the predicted role of the exactly matching predicted span; an unmatched span counts as `missed` | accuracy, macro-F1, per-class metrics, confusion matrix; accuracy per tag; role ECE when probabilities exist |
| Retrieval | rank of the relevant passage among each record's passages | hit@1, hit@3, MRR; per tag |
| Verification | the verdict for a passage already in front of the verifier | accuracy, macro-F1, per-class metrics, confusion matrix, accuracy per tag and per requirement type, ECE when probabilities exist |
| Safety-relevant rates | from the verification confusion matrix | **false-support rate** (predicted `supports` that were not), **contradiction recall**, **contradictions read as support** |

Tag slices cover the cases the product most needs to get right: `degree_ambiguity` (MA/MS/BS vs states
and Office), `negation`, `hedge`, `paraphrase`, `hard_negative`, `layout`, `domain_terms`. Missing
requirements show up as `unrelated`/`insufficient` rows in the confusion matrix; unsupported claims as
false supports; contradictions as the contradiction rates.

Not measured by this harness: end-to-end requirement statuses on whole résumés (that needs fully
annotated résumé/posting pairs, which do not exist yet), and the effect of file-parsing errors, which
affect inputs before any model runs. Both need real data.

### Error analysis

After each run, read the confusion matrices and the per-tag tables, then look at actual errors. The
report lists up to 200 misclassified verification records (`errors`: id, gold, predicted, tags) and the
extraction records whose spans differ from gold (`span_errors`: missing and extra spans), by id and
without text; look the records up in the data files, group them by tag and by source, and ask whether the
label, the guideline or the model is at fault. Fix labels and guidelines first; retrain
only after the data is right. Record false supports and false contradictions with the highest priority:
they are the errors that mislead a user.

### Comparing models

`ml.compare` applies the criteria in `ml/configs/promotion.json` to a candidate report and a baseline
report produced from the *same data digest*:

- verification macro-F1 gain over the baseline ≥ a margin;
- false-support rate ≤ a ceiling and not above the baseline's;
- contradictions read as support ≤ a ceiling;
- extraction micro-F1 not below the baseline, and no tag slice more than a tolerance worse;
- retrieval MRR not below the baseline's (BM25);
- ECE of both heads ≤ the display-policy limit;
- measured latency per passage / per pair under a limit, if a benchmark is supplied.

A missing metric fails its check. **The thresholds in the file are placeholders for the people who own the
product to set**, not results. Passing is necessary, not sufficient: a person still reads the report.
Use the same mechanism for regression testing: a retrained or swapped model is judged against the
approved model's report in the same way.

### Benchmarks

`ml.bench` reports load time, per-stage latency (p50, p95, per item) over repeated runs, peak resident
memory and, on GPU, peak allocated CUDA memory, for the machine and settings it ran on. No numbers are
recorded in this repository. Measure on the deployment hardware with the batch size and thread count you
will use.

## Approval checklist

Before editing `approved` in the manifest:

1. Data: validated, split without leakage, and — for approval — including real, lawfully obtained,
   annotated data (see [DATASET_AND_LABELING_STRATEGY.md](DATASET_AND_LABELING_STRATEGY.md)).
2. Evaluation report on the test split and the challenge sets, for the candidate and the baseline, same
   digest; `ml.compare` outputs read and understood; error analysis done.
3. Calibration measured on a split other than the one used to fit it; sample counts meet the display
   policy, or the probabilities stay hidden.
4. Licence and data notes reviewed; benchmark taken on the target hardware.
5. `python -m app.cli verify-models` passes on the server.

The result of every step above is currently *unknown*: nothing has been run.
