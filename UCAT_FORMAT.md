# UCAT Format Reference

The authoritative source for UCAT's format is the UCAT Consortium's own site,
not memory or any third-party guide:

- https://www.ucat.ac.uk/about-ucat/test-format-and-scoring/
- https://www.ucat.ac.uk/about-ucat/test-format/

Whenever content or scoring logic changes, re-check against those pages (or a
fresh web search citing them) rather than assuming this file is still
current — UCAT has changed format before (Abstract Reasoning was dropped from
the 2025+ test) and may again.

This file exists so future changes can be checked against a fixed reference
instead of re-deriving the facts from scratch each time. Last verified: 2026-07.

## Overview

| Subtest | Questions | Time | Answer format |
|---|---|---|---|
| Verbal Reasoning (VR) | 44 | 22 min | 11 passages × 4 questions; 3-option True/False/Can't Tell (16 Q) or 4-option MCQ (28 Q) |
| Decision Making (DM) | 35 | 37 min | 4-option single-best-answer MCQ, **and** a "Yes/No statements" task (5 statements, each independently Yes/No, worth up to 2 marks, 1–3 correct — most commonly 2) |
| Quantitative Reasoning (QR) | 36 | 26 min | 9 data sets (table/scenario) × 4 questions; always 5 options (A–E). Occasionally option E is literally "Can't tell" |
| Situational Judgement (SJT) | 69 | 26 min | ~20 scenarios, each with **up to 6** linked questions, rated on a 4-point scale (Appropriateness or Importance) |

Total: 184 questions, 111 minutes (excluding instruction screens).

## Scoring

- VR, DM, QR (the three "cognitive" subtests) are each scaled to **300–900**
  and commonly summed to a **cognitive total out of 2700**.
- SJT is reported separately as a **Band (1–4)**, not a scaled score. Band 1
  is the strongest band.
- No subtest uses negative marking.

## SJT rating scales (exact wording)

**Appropriateness:**
1. A very appropriate thing to do
2. Appropriate, but not ideal
3. Inappropriate, but not awful
4. A very inappropriate thing to do

**Importance:**
1. Very important
2. Important
3. Of minor importance
4. Not important at all

## DM's "Yes/No statements" task

A set of premises, followed by 5 independent statements. For each, answer
**Yes** if it necessarily follows from the premises, or **No** if it does not
necessarily follow (this collapses VR's separate False/Can't-Tell distinction
into a single "No" — DM's Yes/No is about logical necessity only, not truth).
More than one statement can be Yes; per the Consortium's own guidance, 1–3 is
typical and 2 is most common. The whole 5-statement set counts as one
question, worth up to 2 marks.

## This app's implementation

- `questions.question_format`: `'single'` (one correct letter) or `'multi'`
  (DM's Yes/No task — `correct` is a sorted comma-separated set of letters
  that are "Yes", e.g. `'B,E'`).
- `passages` table: a shared stimulus (VR passage, QR data set, or SJT
  scenario) linked to several `questions` rows via `passage_id`, so a
  passage's questions stay grouped and in order in Practice and Mock.
- `questions.active`: format-nonconforming legacy content is retired (hidden
  from quizzes/mocks) rather than deleted, to preserve users' attempt history.

## Current bank size vs. spec

| Subtest | Bank | Official |
|---|---|---|
| VR | 44 | 44 ✅ |
| QR | 36 | 36 ✅ |
| DM | 63 (57 single + 6 Yes/No) | 35 (bank exceeds target) |
| SJT | 61 (100% scenario-grouped) | 69 |

Check `database.get_questions()` counts by subject to keep this table current.
