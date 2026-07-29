# UCATify question-type and difficulty audit

Audit date: 29 July 2026

## Executed brief

Act as a senior UCAT item writer, psychometric quality reviewer and Python developer. Use the current official UCAT test-format page and official practice banks as the primary standard. For Verbal Reasoning, Decision Making, Quantitative Reasoning and Situational Judgement:

1. Catalogue every official response format and stimulus type.
2. Compare those formats with UCATify's active question bank and identify omissions or over-represented substitutes.
3. Add original, non-copied questions for material gaps, including five-statement Decision Making syllogisms, complex overlap-region diagrams and choose-the-correct-Venn-diagram items.
4. Match official structure, option counts, multi-statement scoring conventions, set sizes and time pressure. Target upper-official-practice-test reasoning density without relying on obscurity or excessive arithmetic.
5. Independently verify every new answer, distractor and diagram; preserve the exact current live-test item counts; retire replaced seeded questions without deleting historical attempts; and test the rendered Streamlit UI.
6. Report separately on structural difficulty matching and psychometric equating. Do not claim statistical equivalence without candidate-response calibration data.

## Primary official references

- [UCAT test format and scoring](https://www.ucat.ac.uk/about-ucat/test-format-and-scoring/)
- [Official UCAT practice tests and question banks](https://www.ucat.ac.uk/prepare/practice-tests/)

The official practice materials state that their questions are representative of the live test. The audit used those materials as the content and interaction reference; no official item text or artwork was copied into UCATify.

## Coverage result

| Section | Official format checked | UCATify result after audit |
|---|---|---|
| Verbal Reasoning | 44 questions; 11 passages with four questions; True/False/Can't Tell and four-option question/incomplete-statement formats | 44 questions in 11 four-question sets: 16 T/F/CT and 28 MCQ. Direct-retrieval, inference, incomplete-statement and negative `EXCEPT` stems are enforced by validation. |
| Decision Making | 35 questions; syllogisms, logical puzzles, recognising assumptions, interpreting information, Venn diagrams, probability/statistics; four-option single answers and five-statement Yes/No items | 35 questions: 29 single-answer and six five-statement items. All six official families are represented. UCATify's “Evaluating Arguments” topic maps to the official recognising-assumptions/strongest-argument family. |
| Quantitative Reasoning | 36 questions; five options; most questions grouped in sets of four around tabular/chart/graph data, with some standalone questions | 36 questions: eight four-question data sets plus four standalone items. Five sets now use charts or graphical data displays rather than relying only on Markdown tables. |
| Situational Judgement | 69 questions; scenarios with up to six questions; appropriateness/importance scales and most/least-of-three items | 69 questions across 16 scenarios: 61 four-point ratings and eight most/least items. Scale wording and three-action structure are validated. |

## Gaps corrected

- Added an original hard five-statement Yes/No syllogism using exclusive categories, a proper subset, existence and a cardinality inference.
- Added a six-outline region-identification diagram at the complexity level of the supplied official example.
- Added a choose-the-correct-Venn-diagram item with four rendered answer diagrams, including overlap, disjoint-set and outside-set reasoning.
- Replaced a four-question QR data set with four standalone QR questions covering scale conversion, mixture replacement, rate/percentage yield and whole-unit rounding.
- Converted five QR datasets to accessible line, bar or comparison graphics.
- Added a negative `EXCEPT` VR item while retaining direct-retrieval and incomplete-statement variants.
- Added trusted, self-contained SVG rendering with accessible labels and no scripts or external assets.
- Added retirement metadata so replaced seeded questions leave the active bank without deleting historic user attempts.

## Difficulty review

| Section | Easy | Medium | Hard |
|---|---:|---:|---:|
| VR | 6 | 20 | 18 |
| DM | 1 | 17 | 17 |
| QR | 3 | 16 | 17 |
| SJT | 14 | 30 | 25 |

Difficulty was benchmarked structurally against the official practice materials: number of reasoning steps, distractor plausibility, information density, time burden, response format and the need to distinguish what must follow from what may follow. It is not valid to claim psychometric equivalence to the live UCAT from editorial review alone. Statistical equating would require representative candidate-response data, item facility, discrimination, differential-item-functioning review and calibration against an anchored form.

## Verification performed

- Exact active counts: VR 44, DM 35, QR 36, SJT 69; total 184.
- Independent QR arithmetic checks and enumerated/formal DM logic checks.
- Independent geometry/set-arithmetic checks for both new DM visual questions.
- Answer-position balance, option count, explanation completeness and duplicate-stem checks.
- Fresh-database seed and retirement migration smoke test.
- Python compilation and Git whitespace validation.
- Local Streamlit browser tests for the commit footer, both DM diagram formats, the new standalone QR flow and browser console errors.
