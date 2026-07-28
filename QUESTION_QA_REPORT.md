# UCAT Question Bank QA Report

Completed: 28 July 2026

## Outcome

The active seeded bank has been replaced with 184 original questions covering the complete current UCAT structure:

| Subtest | Active questions | Active formats | Linked structure |
|---|---:|---|---|
| Verbal Reasoning | 44 | 16 three-option True/False/Can't Tell; 28 four-option MCQ | 11 passages × 4 questions |
| Decision Making | 35 | 29 four-option single-answer; 6 five-statement Yes/No | 35 standalone screens |
| Quantitative Reasoning | 36 | 36 five-option single-answer | 9 data sets × 4 questions |
| Situational Judgement | 69 | 61 four-point ratings; 8 most/least selections from 3 actions | 16 scenarios; no scenario exceeds 6 questions |

There is no active Abstract Reasoning content.

## Files changed

- `question_bank.py` — complete original 184-item active seed bank.
- `database.py` — loads the rewritten bank, adds missing DM/SJT topics, refreshes passage bodies, and retires superseded seed rows without deleting attempts.
- `app.py` — renders SJT most/least questions, uses the corrected 22-minute VR timing, and provides format-aware DM/SJT practice scoring.
- `scripts/validate_questions.py` — strict current-bank structural, content, calculation, logic, balance, and migration validation.
- `UCAT_FORMAT.md` — corrected current response formats, scoring notes, and active-bank counts.
- `QUESTION_QUALITY_AUDIT.md` — official benchmark, baseline counts, every legacy set/topic disposition, and rewrite strategy.
- `QUESTION_QA_REPORT.md` — this completion record.

No authentication, unrelated interface, analytics, or account behaviour was intentionally changed.

## Rewrite and migration accounting

The previous seed inventory contained 204 active items. The replacement deliberately avoids deleting those rows so historical attempts retain valid foreign-key targets.

| Disposition during an existing-database upgrade | Count |
|---|---:|
| Retained unchanged | 0 |
| Rewritten active content | 184 |
| Updated in place | 1 |
| Retired but preserved for history | 203 |
| Newly inserted active rows | 183 |
| Active rows after sync | 184 |

“Rewritten active content” describes the authored bank; the following migration rows describe how that content is stored and therefore overlap with it. One generic stem occurs in both inventories and is updated in place; the remaining 203 old seed rows become inactive. On a fresh database, exactly 184 rows are inserted. All 184 active items contain newly authored stimuli, questions, options, and rationales. User-created rows whose stems are outside the known seed inventory are not updated or retired; the smoke test verifies this with a sentinel row.

## Official format evidence

Official sources accessed 28 July 2026:

- [UCAT Test Format and Scoring](https://www.ucat.ac.uk/about-ucat/test-format-and-scoring/)
- [UCAT Question Tutorials](https://www.ucat.ac.uk/prepare/question-tutorials/)
- [Official Question Banks and Practice Tests](https://www.ucat.ac.uk/prepare/practice-tests/)

The Consortium confirms 44 VR questions in 22 minutes, 35 DM in 37 minutes, 36 QR in 26 minutes, and 69 SJT in 26 minutes. It confirms 1-mark VR/QR/DM single questions, 2-mark DM multi-statement questions with partial credit, and partial credit for SJT responses close to the key.

The interactive official banks were inspected directly. They confirmed:

- VR uses four-question passages with four-option MCQ and three-option T/F/CT.
- DM identifies syllogisms, logical puzzles, recognising assumptions, interpreting information, Venn diagrams, and probabilistic/statistical reasoning; five-statement Yes/No is also present.
- QR uses five options and mostly four-question shared data sets.
- SJT uses four-point appropriateness/importance scales and most/least-appropriate selection from three actions.

No official or commercial passage, scenario, question, explanation, or distinctive fact pattern was copied or lightly rewritten.

## Coverage by question type

### Verbal Reasoning

- Main idea and purpose
- Scope and qualification
- Causation versus association
- Chronology and comparison
- Author position and inference
- Three-option True/False/Can't Tell
- Cross-paragraph synthesis

New passages are 240–360 words under the validator's gate. Four questions in a set do not repeatedly target one sentence or one reasoning operation.

### Decision Making

| Type | Active questions |
|---|---:|
| Single-answer syllogism/logical deduction | 5 |
| Five-statement Yes/No syllogism | 6 |
| Logic puzzles and arrangements | 5 |
| Evaluating arguments | 5 |
| Venn diagrams and sets | 5 |
| Probability and statistics | 4 |
| Interpreting information/evidence | 5 |

Finite arrangements are exhaustively enumerated by the validator. Monadic syllogisms are checked over exhaustive small logical models; this both proves credited entailments and searches for countermodels to distractors.

### Quantitative Reasoning

All 36 questions use five options and belong to original four-question sets covering:

- membership pricing and break-even decisions;
- courier tariffs and surcharges;
- tiered water charges;
- currency conversion and fees;
- capacity, waste, time and production cost;
- timetables, boarding constraints and average speed;
- event income, sponsorship and costs;
- energy output, percentage factors and losses;
- supplier discounts, wastage and whole-unit ordering.

Every numerical answer is recalculated independently in `scripts/validate_questions.py` rather than trusted from the authored key.

### Situational Judgement

The 16 original scenarios cover patient safety, working within competence, confidentiality, honesty, assessment integrity, research integrity, communication, discrimination, teamwork, raising concerns, gifts, professional boundaries, language support, fatigue and informed choice. Eight questions exercise the current most/least response format.

Rating explanations identify the principle, affected stakeholder, immediate or plausible risk, and why the neighbouring rating is too strong or weak. Most/least explanations compare all three actions.

## Difficulty distribution

Difficulty labels are a deliberate practice-bank design choice, not an official UCAT distribution and not a psychometrically calibrated claim.

| Subtest | Easy | Medium | Hard |
|---|---:|---:|---:|
| VR | 6 | 20 | 18 |
| DM | 1 | 19 | 15 |
| QR | 3 | 16 | 17 |
| SJT | 14 | 30 | 25 |
| **Total** | **24** | **85** | **75** |

The bank intentionally emphasises medium and hard reasoning. Difficulty comes from integration, selection, constraints, baselines, competing duties, and plausible errors—not obscure knowledge or deliberately confusing wording.

## Answer-position balance

| Group | Distribution |
|---|---|
| VR | A 12 / B 12 / C 13 / D 7 (D is unavailable in the 16 T/F/CT items) |
| DM single-answer | A 8 / B 7 / C 7 / D 7 |
| QR | A 8 / B 7 / C 7 / D 7 / E 7 |
| SJT four-point ratings | A 16 / B 15 / C 15 / D 15 |

The validator also compares average correct-option length with distractor length and fails if the key becomes systematically conspicuous.

## Representative reasoning improvements

These examples refer only to newly written material:

- **VR — Restoring the Fenmere Peatlands:** a linked set separates local water-table effects, uncertain bird causation, two-stream flood evidence, and the inability to isolate two simultaneous interventions. A reader must distinguish contradiction from missing evidence across different paragraphs.
- **DM — Parcel delivery assignment:** four colour constraints require a short proof by contradiction; the validator enumerates all assignments and confirms that only one conclusion is necessary.
- **QR — Print Workshop Capacity:** students combine setup time, production speed, waste, whole-sheet rounding, and cost. Distractors map to omitting waste, rounding at the wrong stage, or comparing speed without setup.
- **SJT — Too Tired to Work Safely:** the scenario balances attendance, burden on colleagues, student welfare and patient risk. Rating and most/least questions distinguish supportive escalation from concealment, public humiliation, and transferring monitoring responsibility to a patient.

## Scoring implementation

- Cognitive single-answer items: 1 mark for an exact answer.
- DM five-statement items: 2 marks when all five judgements match; 1 mark when four match.
- SJT ratings: exact response receives full practice credit; an adjacent rating receives half practice credit.
- SJT most/least: each correctly placed component receives one of two practice marks.

The SJT partial-credit calculation is explicitly a practice approximation. The Consortium confirms partial credit but does not publish the live item weights or band conversion. The app continues to label its SJT band estimate as indicative.

## Verification results

### Strict validator

Command: `python scripts\validate_questions.py`

Result:

```text
Active seed bank size: 184
Counts: {'VR': 44, 'QR': 36, 'SJT': 69, 'DM': 35}
RESULT: PASS — format, structure, balance, independent math, logic models, and seed migration checks passed.
```

The validator covers:

- exact subtest and format counts;
- passage/scenario grouping and limits;
- option counts and exact rating scales;
- topic mapping, tuple integrity, duplicate stems/options and explanation depth;
- answer-position and option-length balance;
- all 36 QR calculations;
- DM Venn, probability, schedule and data calculations;
- exhaustive arrangement checks and logical model enumeration;
- fresh seeding, repeated idempotent backfill, retirement of an old seed, preservation of its attached attempt, and non-modification of a user-created sentinel.

### Application checks

- UTF-8 syntax compilation of `app.py`, `database.py`, `question_bank.py`, and the validator: **PASS**.
- Real app import with temporary database: **PASS**.
- DM full/partial mark behavior: **PASS**.
- SJT adjacent-rating partial mark behavior: **PASS**.
- SJT most/least exact and one-component partial behavior: **PASS**.
- Existing repository test files: none were present.

## Remaining limitations and uncertainty

- No practice bank can claim psychometric equivalence to live UCAT items without candidate-response data, item calibration, equating, and statistical screening. These questions were compared with current official examples for structure and reasoning characteristics, but they are not UCAT Consortium items.
- Official examples provide a strong qualitative benchmark, not a public specification for exact live difficulty distribution.
- The live SJT weighting and band conversion are not public; the app's partial-credit and band display are practice approximations.
- The full-bank timing burden can only be validated reliably through candidate trials. The content is designed for official pacing, but empirical completion-time and discrimination data remain to be collected.
