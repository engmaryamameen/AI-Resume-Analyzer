# AI limitations

What the analysis can and cannot be trusted to do. The same points, shortened, appear in the product
(each assessment lists its own limitations, and every analysis names the engine that produced it).

**Nothing in this repository has been measured.** No model has been trained or evaluated, so there are no
accuracy figures to quote and none are implied. Where this document says a model "may" fail, it is
describing a risk the evaluation in [TRAINING_AND_EVALUATION.md](TRAINING_AND_EVALUATION.md) is designed
to measure, not a measured rate.

## Intended use

- A person checks their own résumé against a posting and sees which requirements the text backs up, which
  it only names, and which it does not touch, each with the exact lines relied on.
- A reviewer uses that as a starting point and reads the evidence.

## Not intended, and not supported

- **Ranking, scoring, screening or rejecting candidates.** There is deliberately no overall score. Using
  the statuses to filter people automatically would be a misuse: the system is wrong in ways that have
  not been measured, and it has not been evaluated for fairness across groups.
- **Verifying that a claim is true.** `supported` means the résumé's text claims the thing in context,
  not that the claim is accurate.
- **Predicting interviews, offers or performance.** It compares wording; it knows nothing about the person.
- **Applicant-tracking-system compatibility.** It does not emulate any such system.
- **Non-English résumés.** Models, vocabulary and rules are English-only.

## What can go wrong

| Area | Limitation |
| --- | --- |
| **File reading** | Text comes from the PDF or DOCX text layer. Scans and images produce almost nothing, and the file is then marked unreliable instead of guessed at. Multi-column layouts, tables, text boxes, headers/footers and unusual fonts can scramble reading order or drop text, which can turn a present skill into "no evidence". Hidden text (white-on-white, tiny fonts) **is** extracted and is read like any other text, so keyword stuffing counts as evidence of mention. |
| **Sections and dates** | Section detection and date parsing are rule-based. Odd headings, creative layouts, ranges without months and non-Gregorian or non-English dates may be misread; uncertain results are reported as uncertainties, and total experience is only as good as the dates found. |
| **Vocabulary** | Requirement extraction and the rule-based reading recognise skills only from a fixed vocabulary (`backend/app/lang/taxonomy.json`). New, niche or non-technical terms are invisible to them. The learned extractor is meant to generalise beyond it, but only to the extent its training data did. |
| **Context and negation** | Roles (affirmed, listed, mentioned, negated, hedged) depend on local wording. Long-range negation, irony, comparatives ("more experience with X than Y"), and conditionals can be misread. The rule-based reading uses short word windows and will miss anything outside them. |
| **Paraphrase** | Retrieval and verification may miss unusual descriptions of a skill, and may also treat a related tool as support. Wrong "supports" is the error that misleads most; it is tracked separately (false-support rate). |
| **Degrees** | Abbreviations (MA, MS, BA, BS) are disambiguated from context. Unusual or non-US degree names, combined degrees and honours classifications may be missed or mis-levelled. Degree *level* is judged; equivalence between qualifications is not. |
| **Experience** | Years are computed from dated roles and cannot be attributed to a single skill. A requirement such as "5 years of Python" is checked for total experience and for evidence of Python separately. |
| **Training data** | The only data in the repository is synthetic or small hand-written sets. A model trained on it is expected to do better on similar text than on real résumés, and may fail on layouts, vocabulary and phrasing it never saw. No real annotated data exists yet. |
| **Calibration** | A calibrated probability is calibrated on data like the calibration split. On different data (another industry, language style or layout) it can be badly wrong. It is estimated for one label of one passage, not the chance that the person has the skill. Probabilities are hidden unless calibration meets the display policy. |
| **Model errors** | Transformer models can be confidently wrong, especially on short text with little context, and are sensitive to wording. Two equivalent phrasings can get different labels. |
| **Retrieval depth** | Only the most similar passages and passages with linked mentions are verified. Evidence phrased very differently from the requirement may never be considered. |
| **Posting quality** | Requirements are extracted from the posting's structure. Vague, marketing-heavy or badly formatted postings produce incomplete lists. Users can correct the list, and every requirement shows its source span. |
| **Rules mode** | When models are unavailable the rule-based reading is more literal: it misses paraphrases and relies on cue words. It reports no probabilities. Results from the two modes are not directly comparable, and the product says which one ran. |
| **Language and fairness** | Pretrained models carry the biases of their training text. Writing style, non-native English, unfamiliar institution names, career gaps and non-traditional titles may be handled less well. The system does not use names, photos, ages or addresses as inputs, but the text itself can correlate with them. Fairness has not been evaluated. |
| **Adversarial text** | There is no language model to take instructions from a résumé, so instruction-injection does nothing, but keyword stuffing and fabricated claims are indistinguishable from honest text. |

## How the product handles uncertainty

- Every requirement result carries a status, its reasons, the verbatim excerpts used, and an explanation
  for anything other than `supported`.
- Disagreement between signals is surfaced ("the verifier and the extractor read the strongest passage
  differently; the more cautious reading was used"), and supporting plus contradicting passages are shown
  as a conflict, not as support.
- Parse problems are shown as warnings, and "no evidence" is qualified when the file was hard to read.
- Probabilities appear only when calibrated and only with an explanation of what they mean.
- Recommendations quote the résumé and never write new claims; their fill-in blanks are for the user.
- The engine, its models (revision, origin, licence) and any reason the learned models were not used are
  recorded with every analysis and shown with it.

## What would reduce these limits

Real annotated data and a proper evaluation; annotator-agreement measurement; evaluation sliced by
layout, industry and language style; a fairness review; a larger or better-chosen model if the small ones
fail evaluation; and OCR for scans (not included, to keep the parsing path small and auditable).
