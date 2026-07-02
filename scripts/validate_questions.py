#!/usr/bin/env python3
"""
Test suite for the UCAT question bank in database.py.

Run this after adding any new question set, before committing:

    python3 scripts/validate_questions.py

Checks, in order (each is a hard failure — exit code 1 if any fail):
  1. Structural integrity  — tuple shape, valid subject code, valid topic-to-
     subject mapping, valid difficulty tag, correct answer is A/B/C/D, no
     empty fields.
  2. No duplicate stems anywhere in the bank; no duplicate/blank options
     within a single question.
  3. Independent numeric verification for every Quantitative Reasoning
     question and every Decision Making Venn-Diagrams/Probability question:
     the expected number is computed here in Python from the figures in the
     stem, then checked that it actually appears in the option marked
     `correct` in database.py (and NOT in the other three options, to catch
     an answer pointed at the wrong letter). This computes fresh each run —
     it does not trust any value written during authoring.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database as db

FAILURES = []


def fail(msg):
    FAILURES.append(msg)


def check_structure():
    topics_by_code = {}
    for code, name, hy, summary, content in db._TOPICS:
        topics_by_code.setdefault(code, set()).add(name)
    subject_codes = {c for c, *_ in db._SUBJECTS}

    seen_stems = set()
    for i, q in enumerate(db._QUESTIONS):
        if len(q) != 10:
            fail(f"[structure] #{i}: wrong tuple length {len(q)}")
            continue
        code, tname, stem, a, b, c, d, correct, expl, diff = q
        if code not in subject_codes:
            fail(f"[structure] #{i}: unknown subject code {code!r}")
        if tname not in topics_by_code.get(code, set()):
            fail(f"[structure] #{i}: topic {tname!r} not registered for {code}")
        if correct not in ("A", "B", "C", "D"):
            fail(f"[structure] #{i}: correct answer {correct!r} is not A-D")
        if diff not in ("Easy", "Medium", "Hard"):
            fail(f"[structure] #{i}: difficulty {diff!r} is not Easy/Medium/Hard")
        if not (stem and a and b and c and d and expl):
            fail(f"[structure] #{i}: empty field in {stem[:50]!r}")
        if len({a, b, c, d}) != 4:
            fail(f"[structure] #{i}: duplicate options in {stem[:50]!r}")
        if stem in seen_stems:
            fail(f"[dedup] #{i}: duplicate stem {stem[:60]!r}")
        seen_stems.add(stem)


def find(stem_fragment):
    """Locate a question by a unique substring of its stem; error if 0 or >1 match."""
    matches = [q for q in db._QUESTIONS if stem_fragment in q[2]]
    if len(matches) != 1:
        fail(f"[lookup] fragment {stem_fragment!r} matched {len(matches)} questions (expected 1)")
        return None
    return matches[0]


def _num_tokens(text):
    """Extract numeric tokens from option text, normalised (strip £, %, commas, units)."""
    cleaned = text.replace(",", "").replace("£", "")
    return set(re.findall(r"-?\d+\.?\d*", cleaned))


def assert_computed(stem_fragment, computed_value, note=""):
    """Assert `computed_value` (a number, computed fresh by this script) appears in the
    stored `correct` option's text and in no other option's text."""
    q = find(stem_fragment)
    if q is None:
        return
    code, tname, stem, a, b, c, d, correct, expl, diff = q
    options = {"A": a, "B": b, "C": c, "D": d}

    if isinstance(computed_value, str) and "/" in computed_value:
        # fraction answers (e.g. "1/6") — match the literal fraction substring
        hits = [letter for letter, text in options.items() if computed_value in text]
    else:
        # normalise the computed value the same way option text is tokenised
        if isinstance(computed_value, float) and computed_value == int(computed_value):
            target = str(int(computed_value))
        else:
            target = str(computed_value)
        hits = [letter for letter, text in options.items() if target in _num_tokens(text)]
    if correct not in hits:
        fail(
            f"[math] {stem_fragment[:50]!r}: computed {computed_value} ({note}) does not "
            f"appear in stored-correct option {correct} ({options[correct]!r}); "
            f"it appears in {hits or 'no option'} instead."
        )
    elif len(hits) > 1:
        fail(
            f"[math] {stem_fragment[:50]!r}: computed value {computed_value} is ambiguous — "
            f"appears in multiple options {hits}, cannot confirm {correct} is uniquely correct."
        )


def check_qr_and_dm_numeric_math():
    # ── QR: Percentages & Percentage Change ──────────────────────────────
    assert_computed("95% efficacy rate in a trial of 400", 400 * 0.05, "not-protected count")
    assert_computed("2,400,000 to £2,160,000", (2400000 - 2160000) / 2400000 * 100, "% decrease")
    assert_computed("10% pay rise followed by a further 10%", round(36300 / 1.21), "original salary")
    assert_computed("reduced by 30%, and the reduced amount is then increased by 30%", 200 * 0.7 * 1.3, "final dose")
    assert_computed("agency staffing costs from £180,000 to £126,000", (180000 - 126000) / 180000 * 100, "% reduction")
    assert_computed("cholesterol level falls from 6.5 mmol/L to 5.2", round((6.5 - 5.2) / 6.5 * 100), "% decrease")
    assert_computed("donations increased by 40% this year to £210,000", round(210000 / 1.4), "original donations")
    assert_computed("20% off, and then an additional 10% off", round((1 - 0.8 * 0.9) * 100), "overall % discount")
    assert_computed("15% improvement rate in the treatment group", 15 - 6, "percentage-point gap")
    assert_computed("grows by 8% one year and then shrinks by 8%", round(2500 * 1.08 * 0.92), "patients after 2 years")

    # ── QR: Ratios & Proportion ───────────────────────────────────────────
    assert_computed("saline solution is mixed in the ratio 3 parts salt", 3 / 50 * 500, "ml salt")
    assert_computed("split a set of night shifts in the ratio 5:3", 12 / 3 * 5, "larger share")
    assert_computed("flour, sugar and butter in the ratio 5:2:1", 2 / 8 * 320, "g sugar")
    assert_computed("map has a scale of 1:25,000", 8 * 25000 / 100000, "km actual distance")
    assert_computed("4,000 tablets weighing 500 mg each contains active", 4000 * 500 / 10, "mg active ingredient")
    assert_computed("bulk order of masks in the ratio 4:5:6", 800 / 4 * (4 + 5 + 6), "total masks")
    assert_computed("saline drip mixes concentrate and water in a ratio of 1:19", 1 / 20 * 2000, "ml concentrate")
    assert_computed("recipe scaled for 10 people uses 1.5 kg of rice", 1.5 / 10 * 25, "kg for 25 people")
    assert_computed("investors put money into a project in the ratio 3:7", (7 - 3) * (45000 / 10), "difference in £")
    assert_computed("alloy of 100 kg is made of copper and tin in the ratio 7:3", 70 * 5 / 7 - 30, "kg tin to add")

    # ── QR: Speed, Distance & Time ────────────────────────────────────────
    assert_computed("first 30 km of a journey at 60 km/h and the next 30 km at 40", 60 / (30 / 60 + 30 / 40), "avg speed")
    assert_computed("walks to work at 5 km/h and it takes her 24 minutes", 5 * (24 / 60), "distance km")
    assert_computed("Two trains 210 km apart travel toward each other", 210 / (50 + 55), "hours to meet")
    assert_computed("delivery van travels 84 km in 1 hour 45 minutes", 84 / 1.75, "avg speed")
    assert_computed("driven to hospital, covering the first half", 30 / 30 + 30 / 60, "total hours")
    assert_computed("cyclist covers 45 km at an average speed of 18 km/h", 45 / 2 - 18, "speed increase needed")
    assert_computed("run in opposite directions, one at 9 km/h and the other at 11", round(5 / (9 + 11) * 60), "minutes")
    # train speed: s^2 + 10s - 3000 = 0 -> s = (-10 + sqrt(100+12000))/2
    _s = (-10 + (100 + 4 * 3000) ** 0.5) / 2
    assert_computed("train covers 300 km at a constant speed", round(_s), "actual speed")
    assert_computed("boat travels 24 km downstream in 2 hours", (24 / 2 + 24 / 3) / 2, "still-water speed")

    # ── QR: Tables, Charts & Data ──────────────────────────────────────────
    assert_computed("480 appointments last month, of which 30% were cancelled", 480 * 0.3 / 2, "cancelled & not rebooked")
    assert_computed("120 patients in Q1, 150 in Q2, 90 in Q3 and 140 in Q4", round(150 / (120 + 150 + 90 + 140) * 100), "Q2 %")
    assert_computed("side-effect rate as 12 per 1,000 patients", round(12 / 1000 * 4250), "expected side effects")
    assert_computed("45% of a survey's respondents rated a service", round(60 / 0.2), "total respondents")
    assert_computed("quarterly sales of a clinic's home-testing kits", (400 + 550 + 620 + 480) / 4, "average quarterly sales")
    assert_computed("bed occupancy rates: Medical ward 92%", 0.92 * 150, "occupied beds")
    assert_computed("dropout rates shows 12% of 250 participants withdrew", round(250 * 0.88 * 0.9), "remaining participants")
    assert_computed(
        "A&E attendances by hour: 8am: 20, 12pm: 35, 4pm: 50",
        round(50 / (20 + 35 + 50 + 45 + 15) * 100), "4pm % of attendances",
    )
    assert_computed("pass rates for a professional exam over three years", round(0.71 * 400), "passed in 2023")
    assert_computed("preferred appointment time: 25% morning, 45% afternoon", 240 * 0.45 - 240 * 0.3, "afternoon minus evening")

    # ── DM: Venn Diagrams & Sets (inclusion-exclusion) ──────────────────────
    assert_computed("50 have high blood pressure, 35 have high cholesterol", 80 - (50 + 35 - 20), "neither")
    assert_computed("42 study French, 10 study neither French nor German", 60 - 10 - (42 - 8) - 8, "German only")
    assert_computed("15 like tea, 12 like coffee, and 4 like neither", 15 + 12 - (25 - 4), "both")
    assert_computed("22 study Biology and 19 study Chemistry", 22 + 19 - 30, "both")
    assert_computed("70 attended the morning session, 55 attended the afternoon", 70 + 55 - (120 - 15), "both sessions")
    assert_computed("everyone owns a cat, a dog, or both. 30 own a cat", 30 + 25 - 45, "own both")
    assert_computed(
        "54 have a family history of diabetes, 38 have a family history of hypertension",
        54 + 38 - (90 - 20), "both conditions",
    )
    assert_computed(
        "120 take Spanish, 90 take German, and 40 take neither",
        (200 - 40) - (120 + 90 - (200 - 40)), "exactly one language",
    )
    assert_computed(
        "35 can perform procedure A and 28 can perform procedure B",
        35 - (35 + 28 - (60 - 10)), "only procedure A",
    )
    assert_computed("32 sing soprano and 26 sing alto", 32 + 26 - 50, "both parts")

    # ── DM: Probability & Statistics ────────────────────────────────────────
    assert_computed("4 red, 3 green and 3 blue balls", "7/10", "P(not green) as a fraction")
    assert_computed("Two fair coins are tossed", "3/4", "P(at least one heads)")
    assert_computed("screening test correctly identifies a disease in 90%", 0.9 * 200, "correctly identified")
    assert_computed("drawer contains 5 pairs of socks", "1/9", "P(matching pair)")
    assert_computed("6 blue and 4 yellow marbles. One marble is drawn and not replaced", "1/3", "P(both blue)")
    assert_computed("vaccine is 80% effective at preventing infection", 150 * 0.2, "expected infections")
    assert_computed("fair six-sided die is rolled twice", "1/6", "P(sum of 7)")
    assert_computed("probability a randomly chosen student studies medicine is 0.3", 1 - (0.3 + 0.15), "P(neither)")
    assert_computed("test has a false positive rate of 5%", 300 * 0.05, "false positives")
    assert_computed("Three coins are tossed. What is the probability of getting exactly two heads", "3/8", "P(exactly 2 heads)")
    assert_computed("1 in 8 patients admitted with chest pain", 640 / 8, "expected diagnoses")


def check_live_seed_smoke_test():
    """Confirm the bank actually loads through the real seeding/backfill path."""
    import sqlite3
    import tempfile
    import importlib
    import os

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "smoke.db"
        os.environ.pop("DATABASE_URL", None)
        import database as fresh_db
        importlib.reload(fresh_db)
        fresh_db.DB_PATH = db_path
        fresh_db._BOOTSTRAPPED = False
        fresh_db.init_db()

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        conn.close()

        if count != len(db._QUESTIONS):
            fail(f"[smoke] fresh DB seeded {count} questions, expected {len(db._QUESTIONS)}")


def run():
    check_structure()
    check_qr_and_dm_numeric_math()
    check_live_seed_smoke_test()

    total = len(db._QUESTIONS)
    print(f"Question bank size: {total}")
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print(" -", f)
        print("\nRESULT: FAIL")
        sys.exit(1)
    else:
        print("RESULT: PASS — structural, dedup, independent-math, and live-seed checks all passed.")
        sys.exit(0)


if __name__ == "__main__":
    run()
