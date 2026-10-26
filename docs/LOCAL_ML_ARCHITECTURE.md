# Local ML architecture

How the résumé analysis reads, matches and judges text, what each model is responsible for, and what
happens when a model is missing or fails. Everything runs on the operator's own machine. No hosted
inference service is called, at any point, for any reason.

**Status of this document.** It describes what the code in this repository does. The code has not been
executed, and no model has been trained, downloaded or evaluated yet. Statements about how well a model
works are therefore absent on purpose; the tests and evaluation that would produce them are described in
[TRAINING_AND_EVALUATION.md](TRAINING_AND_EVALUATION.md).

## Pipeline

```
 PDF / DOCX                                       job description text
     │                                                     │
     ▼                                                     ▼
┌─────────────────────┐                         ┌─────────────────────┐
│ 1 Document parsing  │  rules, no ML           │ 2 Requirement       │  rules, no ML
│  sandboxed extract, │                         │   extraction        │
│  sections, dates    │                         │  headings, cues,    │
└─────────┬───────────┘                         │  vocabulary, spans  │
          │ passages (one per résumé block,     └──────────┬──────────┘
          │ with section + role as context)                │ requirements
          ▼                                                │
┌─────────────────────┐                                    │
│ 3 Extractor (DL)    │ spans: SKILL DEGREE FIELD ORG      │
│  token tags + role  │ TITLE CERT; role per skill/degree/ │
│  per mention        │ certification mention              │
└─────────┬───────────┘                                    │
          │ mentions                                       │
          ▼                                                ▼
┌──────────────────────────────────────────────────────────────┐
│ 4 Retriever (pretrained embeddings)  top passages per        │
│   requirement + passages whose mentions link to it           │
└──────────────────────────────┬───────────────────────────────┘
                               │ (requirement, passage) pairs
                               ▼
                  ┌─────────────────────────┐
                  │ 5 Verifier (DL)         │ supports / mentions_only /
                  │  cross-encoder          │ contradicts / insufficient /
                  └────────────┬────────────┘ unrelated
                               ▼
                  ┌─────────────────────────┐
                  │ 6 Decision table        │ no models: combines verdict and
                  │  + calibration display  │ mention role; one status per
                  └────────────┬────────────┘ requirement
                               ▼
         per requirement: status, evidence excerpts, reasons, explanation,
         optional calibrated probability · descriptive assessments · recommendations
```

Stages 1, 2 and 6 are ordinary code and are tested as such. Stages 3, 4 and 5 are the models.

## Responsibilities

| Stage | Question it answers | Why a model, or why not |
| --- | --- | --- |
| Parsing | What text is in the file, and where? | Deterministic extraction is auditable and safe to sandbox. |
| Requirement extraction | What does the posting ask for? | Postings have headings and cue words; spans back to the original text matter more than recall on odd phrasing. Users can correct the list. |
| Extractor | Which words in the résumé are skills, degrees, certifications, employers, titles? How is each one *claimed*? | Context decides this: "MS" is a degree in an education entry and not in "MS Office"; "no experience with Kafka" names Kafka without claiming it. |
| Retriever | Which passages could be about this requirement, even if they use other words? | Embeddings find paraphrases that word matching misses. |
| Verifier | Given this passage and this requirement, does the passage support it, merely mention it, contradict it, or say too little? | Retrieval similarity is not evidence. A separate model judges the pair. |
| Decision table | One status per requirement. | Combining two signals by fixed, documented rules keeps the result explainable and unit-testable. |

Retrieval and verification are separate on purpose and are evaluated separately. A passage can be very
similar to a requirement and still contradict it ("No experience with Kubernetes").

## The three models

| id | Role | Origin | Base | Output |
| --- | --- | --- | --- | --- |
| `extractor` | token tagging + mention role | fine-tuned in this repository | `distilroberta-base` | BIO tags over 6 entity types; role ∈ affirmed, listed, mentioned, negated, hedged |
| `retriever` | passage ranking | pretrained, used as published | `BAAI/bge-small-en-v1.5` | unit-length vectors; cosine similarity (ordering only) |
| `verifier` | requirement–passage judgement | fine-tuned in this repository | `cross-encoder/nli-distilroberta-base` | 5-way label |

"Fine-tuned in this repository" means the weights come from the training code in `ml/`, starting from the
published base. A pretrained model is never described as trained here. Provenance, licences and the
approval process are in [MODEL_SELECTION_AND_PROVENANCE.md](MODEL_SELECTION_AND_PROVENANCE.md).

**Extractor.** One encoder, two heads. The token head tags entity spans. The role head reads the first
token of each SKILL, DEGREE and CERT span together with the sequence summary and says how the mention is
used. Input is the context line (`section | entry header`) paired with the text, so the model knows it
is reading an education entry or a role at a given employer. Long passages are split at sentence
boundaries into chunks of at most 700 characters.

**Retriever.** Queries get the model's documented query prefix; passages do not. Vectors are normalised.
Scores order candidates and are never displayed as percentages or treated as probabilities.

**Verifier.** Input pair: `"<context> | <passage>"` and a hypothesis written from the requirement
(`ml/hypotheses.py`; the training data builds the same sentences). Hypotheses exist for skills, soft
skills, certifications, experience areas and free-text responsibilities.

Degrees and years of experience are *not* judged by the verifier. Degree requirements are checked against
the extractor's DEGREE mentions and their roles; years are computed from dated roles and are never
attributed to a single skill.

## Decision table

Two independent signals describe each candidate passage: the verifier's label, and the role the extractor
gave to mentions of the requirement's term in that passage. When they agree, that label stands. When they
disagree the weaker claim wins and the disagreement is reported, except that an explicit negation
outranks a mere mention.

| Role from the extractor | implied label |
| --- | --- |
| affirmed | supports |
| listed, mentioned | mentions_only |
| negated | contradicts |
| hedged | insufficient |

| Verifier \ roles | supports | mentions_only | insufficient | contradicts |
| --- | --- | --- | --- | --- |
| **supports** | supports | mentions_only | insufficient | insufficient |
| **mentions_only** | mentions_only | mentions_only | insufficient | contradicts |
| **insufficient** | insufficient | insufficient | insufficient | contradicts |
| **contradicts** | insufficient | contradicts | contradicts | contradicts |

`unrelated` from the verifier defers to the extractor when a linked mention exists (the passage is related
by construction), and otherwise leaves the passage out.

Across passages the strongest label wins in the order supports, contradicts, mentions_only, insufficient —
except that supporting and contradicting passages together are a **conflict**, reported as `insufficient`
with the conflict flag and a reason, never as support. A requirement with no related passage is
`no_evidence`.

Final statuses: `supported`, `mentioned_only`, `contradicted`, `insufficient`, `no_evidence`. There is no
overall score. The four assessments (requirement evidence, document structure, writing style, extraction
reliability) are counts, shares and durations, each with its definition.

## Probabilities

A probability appears next to a status only when all of these hold:

1. the verifier's verdict head has a temperature fitted on one split (`calibration`) and an expected
   calibration error measured on a different split (`validation`), recorded in the manifest (the
   extractor's role head is calibrated the same way and its probabilities appear on individual mentions,
   not on requirement statuses);
2. that ECE and sample count satisfy the manifest's display policy (`max_ece`, `min_validation_samples`;
   defaults 0.05 and 500, a policy choice rather than a result);
3. the verifier and the extractor agreed on the strongest passage and there is no conflict.

Otherwise the status is shown without any probability. The number shown is described as an *estimated,
calibrated* probability for that label, not as the chance that the candidate has the skill. Raw softmax
values and cosine similarities are never displayed as probabilities.

## Engine modes and degradation

The analysis pipeline talks to an `Engine` interface with two implementations.

| Mode | Used when | Behaviour |
| --- | --- | --- |
| `learned` | all three models are approved, their files match the recorded checksums, and they load | the pipeline above |
| `rules` | anything else | a deterministic baseline built on the vocabulary and cue lists. **It is not machine learning**, reports no probabilities, and every analysis it produces says so |

Choices that follow from this:

- The mode is all-or-nothing. Mixing a learned verifier with rule-based extraction would make results
  hard to interpret.
- If the learned engine runs out of its time budget or cannot run (out of memory, a device error) in the
  middle of an analysis, the whole analysis is redone with the rules engine and records why. Results are
  never a silent mixture.
- Every stored analysis records the engine info (mode, models with revision and licence, calibration,
  notes) and a fingerprint of the approved files. When the fingerprint of the models in use changes, older
  analyses are shown as produced by a different method.
- The public demo always uses the rules engine. The web process never loads models; only the worker does.
- The rules engine exists so the application stays useful without model files and so the models have an
  honest baseline to beat. It is not presented as AI anywhere.

## Contracts

All shared types are in `backend/app/ml/contracts.py` and import no ML libraries.

- `Passage(id, text, context, section_kind)` — a résumé block with where it sits.
- `Mention(passage_id, start, end, text, type, role?, role_probs?, source)` — offsets are character
  offsets into the passage text.
- `Query(id, retrieval_query, hypothesis, term_ids, surface_forms)` — a requirement as a retrieval query
  and a hypothesis to verify.
- `Candidate(passage_id, score, method)` — retrieval result; `score` orders only.
- `Verdict(label, probs?, source)` — `probs` present only when calibrated.
- `EngineInfo(mode, models, calibrated, fingerprint, notes)`.
- Label vocabularies (`TOKEN_LABELS`, `ROLES`, `VERDICT_LABELS`) are defined once. A model whose stored
  label set differs from these is refused at load time, so label order can never silently drift between
  training and inference.

The `Engine` protocol (`extract`, `retrieve`, `verify`, `info`) is the only thing the analysis code
depends on. Inference is a logical module inside the worker process, not a separate service.

## Where things live

| Path | Contents |
| --- | --- |
| `backend/app/ml/` | contracts, decision table, calibration maths, manifest and artifact verification, rules engine, learned engine, BIO decoding |
| `backend/app/analysis/` | requirement extraction, candidate selection, evidence building, summaries, recommendations |
| `ml/` | the ML lab: dataset schema, validation, splitting, synthetic data, training, calibration, evaluation, comparison, benchmarking |
| `models/` | `manifest.json` and, once provisioned, the weights (never committed) |

## What this design does not do

- It does not generate text. Recommendations are built from the evidence statuses and quote the résumé
  verbatim; their fill-in blanks are for the user. Generative rewriting was left out because a local
  generator could not be validated to avoid invented claims.
- It does not use a vector database, an agent framework or a second model to "double check" the first.
- It does not verify that a résumé's claims are true. "Supported" means the text claims it in context.
- It does not rank candidates or predict hiring outcomes.

Known limits of the models and the data are in [AI_LIMITATIONS.md](AI_LIMITATIONS.md).
