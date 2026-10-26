# Dataset and labelling strategy

What data the models are trained and judged on, how it is labelled, and how leakage is prevented.

**Status.** The repository contains tooling and two kinds of data: a deterministic *synthetic* generator
and a small *hand-written challenge set* (71 records). It contains **no real résumés** and no real
annotated data. A model trained only on synthetic data has learned the shape of the task, not how real
résumés look, and must not be approved on that basis (see [Limits of what exists](#limits-of-what-exists)).

## Record kinds

One JSON object per line (`ml/schema.py`). Every record has `id`, `group`, `source`, `tags`.

| Kind | Trains / measures | Fields |
| --- | --- | --- |
| `extraction` | extractor: entity spans and mention roles | `section_kind`, `entry_header`, `text`, `spans[{start, end, type, role?}]` |
| `verification` | verifier: the judgement for a passage and a requirement | `section_kind`, `entry_header`, `text`, `requirement{type, value}`, `label` |
| `retrieval` | retriever, evaluation only | `query`, `passages[{id, text, relevant}]` |

- `source` is `synthetic`, `hand_written` or `licensed` (real data obtained with permission).
- `group` is the unit that must never be split: a template family, a person, or a job posting.
- `tags` slice the evaluation: `negation`, `hedge`, `degree_ambiguity`, `paraphrase`, `hard_negative`,
  `layout`, `domain_terms`, `list`, `mention`, `experience`.
- A requirement's hypothesis is **built from the record's `requirement`** (`ml/hypotheses.py`), the same
  function the application uses, so the verifier is trained on the wording it will be given. Skill and
  soft-skill names must be the vocabulary's canonical names (`ml.validate` rejects `k8s` for `Kubernetes`).

Hand-authored files may write extraction records with markup instead of offsets:
`Built [[Kafka|SKILL|affirmed]] pipelines at [[Acme|ORG]].` The loader converts it to text plus spans, so
offsets cannot be mistyped.

## Annotation guidelines

### Spans (extraction)

- Annotate the exact surface text of the mention, without surrounding spaces. Spans do not overlap or
  nest. A span should start and end on a word boundary.
- **SKILL** — tools, languages, frameworks, methods and domain competencies (`Python`, `Kubernetes`,
  `ICD-10 coding`, `A/B Testing`). Annotate every occurrence in the text, not only the relevant ones, so
  the model is never taught that some mentions don't count.
- **DEGREE** — the credential: `MS`, `B.S.`, `Master of Science`, `MBA`, `PhD`.
  Not a degree: `MS Office`, `MS Teams` (a SKILL), `Boston, MA` (a state), `BS EN ISO 9001` (a standard).
- **FIELD** — the subject of study (`Statistics`). **ORG** — employer or institution. **TITLE** — job
  title. **CERT** — the certification's name.

### Roles (SKILL, DEGREE, CERT spans only)

| Role | Meaning | Example |
| --- | --- | --- |
| `affirmed` | the text says the person used, did, held or completed it | "Built services in **Python**"; "**MS** in Statistics, Summit College" |
| `listed` | bare enumeration (skills list, tool list) | "Skills: **Python**, **Go**" |
| `mentioned` | named, but the person isn't claiming it | "Collaborated with the **Kubernetes** team" |
| `negated` | explicitly lacking, not done, not completed | "No experience with **Kafka**"; "Left the **PhD** programme before finishing" |
| `hedged` | weak or in progress: learning, basic familiarity, exploring, expected, pursuing | "Currently learning **Rust**"; "Pursuing an **MBA**, expected 2027" |

Rules for the hard cases:

- Negation applies to the nearest mention, not the whole sentence: "No experience with **Scala**, but
  built services in **Python**" is `negated` for Scala and `affirmed` for Python.
- A degree or certification in progress, expected, or aspirational is `hedged`. One that was started and
  not finished, failed, or never held is `negated`.
- A tool named alongside an action the person did (`Migrated to **Terraform**`) is `affirmed`; a tool
  named only as part of someone else's work is `mentioned`.
- Terse bullets that are only a list of tools in an experience entry are `listed`.

### Verdicts (verification)

For a requirement and a passage, what would a careful reader conclude about *this candidate and this
requirement*?

| Label | Meaning |
| --- | --- |
| `supports` | the passage says the person did or has it. A description of the capability counts even if it never uses the requirement's name ("ran container clusters" supports Kubernetes) |
| `mentions_only` | names it without claiming the person used it: a bare list, someone else's work, or something only being learned |
| `contradicts` | the passage says the person lacks it, did not do it, or did not complete it |
| `insufficient` | related but not enough: a different tool in the same area, or text too vague to count |
| `unrelated` | nothing about the requirement |

Consistency with the mention roles: `affirmed` → `supports`, `listed`/`mentioned`/`hedged` →
`mentions_only`, `negated` → `contradicts`. A different but related technology is `insufficient`, never
`supports`. When one passage contradicts one skill and supports another, label it per requirement.

## Sources

| Source | Status | Use |
| --- | --- | --- |
| **Synthetic** (`ml/synth.py`) | implemented | teach task shape; repeatable tests; hard negatives |
| **Hand-written challenge sets** (`ml/data/challenge/`) | implemented, small | evaluation only, never training |
| **Licensed / consented real résumés** | not available | required before any approval; see below |

### Synthetic data

17 skill-sentence templates (affirmed, mentioned, listed, negated, hedged) × 6 domains (software, data,
devops, finance, healthcare, marketing), plus hard negatives (a related tool, vague text, another domain),
paraphrases of capabilities, degree and abbreviation cases (`MA`/`MS`/`BA`/`BS` versus states and Office
products), certifications, experience-area sentences and retrieval sets with same-split distractors.
`python -m ml.synth --out <file> --per-pattern N --seed S` is deterministic: the same arguments produce the
same file. Every skill-pool term in a sentence is annotated.

What it cannot do: reflect real layouts, typos, long-tail vocabulary, multi-line bullets, or how real
people phrase negation and hedging. Sentences come from a few dozen templates, so scores on synthetic test
data overstate what real résumés will see. Every evaluation report says so when synthetic data is present.

### Challenge sets

Hand-written, never used for training, and checked against synthetic data for overlap by a test. They
cover MA/MS/BS ambiguity, negation and hedging, layout oddities (pipes, wrapped lines, all caps, two-column
fragments), domain terminology, paraphrase, contradiction, hard negatives and retrieval with low lexical
overlap. They are small (71 records) and meant to expose specific failures, not to estimate overall
accuracy.

### Real data (what is needed)

Real résumés contain personal data. Use them only with the owner's informed permission or another lawful
basis, store them outside the repository, remove or replace direct identifiers (names, contact details,
addresses, links, employer names where practical) before annotation, and keep them out of Git
(`.gitignore` excludes `ml/data/generated/` and `ml/runs/`; real data belongs outside the repository
entirely). Do not train on documents users upload to the application: retention and deletion promises
(`security-and-privacy.md`) would no longer hold. No suitable public dataset has been identified or assumed here; if you adopt one, record its licence and terms in the manifest's `license_notes` and in
`NOTICE.md` first.

Sizing is not guessed here. Two numbers are fixed by policy: at least 500 validation samples per head
before probabilities can be displayed (`display_policy.min_validation_samples`), and enough test records
per tag slice to say something about it. Decide the rest after measuring annotator agreement.

## Splits and leakage

`python -m ml.split` assigns **groups**, not records, to `train` (70%), `validation` (10%),
`calibration` (10%) and `test` (10%) by hashing the group name with a seed. Properties:

- All records of a group land in one split. Adding data later does not move existing groups.
- Records with identical normalised text are merged into one group before splitting, so they cannot sit
  on both sides.
- The calibration split fits the temperature; the validation split selects the training epoch and
  measures the ECE; the test split is read only for final evaluation.
- Retrieval records take their distractors from the same split.

`python -m ml.validate --splits <dir>` checks, and fails on:

- a group in more than one split;
- identical text in more than one split;
- a validation, calibration or test record whose 3-word shingles overlap a training record with Jaccard
  similarity ≥ 0.9;
- invalid structure: empty text, spans outside the text, overlapping spans, whitespace inside spans, text
  longer than the 700-character chunk the extractor sees, duplicate ids, a retrieval record with no
  relevant passage, a non-canonical requirement name.

It also reports counts per kind, source and label, and warns about spans that start or end inside a word.

## Quality control

Not yet done, because there is no real data. Before trusting a labelled set:

1. Double-annotate a sample (suggested 10–15%) and report agreement per entity type, role and verdict
   (Cohen's κ, plus the confusion between roles). Low agreement means the guideline is ambiguous: fix the
   guideline before labelling more.
2. Have a second person review every `contradicts` and `negated` label; those errors are the costly ones.
3. Re-run `ml.validate` after every change and keep the dataset digest (`ml.schema.dataset_digest`) with
   each model.

## Versioning

Every evaluation report and training run records the digest of the files it used. A model is traceable to
the exact data it was trained and tested on. The guideline in this document is the labelling reference;
change it deliberately and re-label affected records.

## Limits of what exists

- No real data, so no estimate of real-world accuracy exists or is implied.
- Synthetic test scores will look better than real ones. Report them as synthetic.
- The challenge sets are too small for confidence intervals. Treat them as a regression suite.
- The vocabulary-based rules baseline recognises only terms in `backend/app/lang/taxonomy.json`; many
  domain skills in the synthetic pools (for example `Excel`, `SEO`, `HL7`) are outside it. That
  disadvantages the baseline on those records. Say so when comparing.
