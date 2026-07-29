#!/usr/bin/env python3
"""Strict validation for the active UCATify seed question bank."""

from __future__ import annotations

import importlib
import itertools
import math
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import database as db
from question_visuals import VISUALS, VISUAL_MARKER_RE


FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


@dataclass(frozen=True)
class SeedItem:
    code: str
    topic: str
    stem: str
    options: tuple[str, ...]
    correct: str
    explanation: str
    difficulty: str
    question_format: str
    passage_title: str | None = None
    passage_body: str | None = None


def collect_items() -> list[SeedItem]:
    items: list[SeedItem] = []
    for code, topic, title, body, questions in db._PASSAGE_SETS:
        for raw in questions:
            stem, a, b, c, d, e, correct, explanation, difficulty = db._unpack_question(raw)
            options = tuple(value for value in (a, b, c, d, e) if value)
            if code == "SJT" and "," in correct:
                fmt = "rank"
            elif code == "DM" and title in db._DM_MULTI_PASSAGE_TITLES:
                fmt = "multi"
            else:
                fmt = "single"
            items.append(SeedItem(code, topic, stem, options, correct, explanation,
                                  difficulty, fmt, title, body))
    for row in db._STANDALONE_QUESTIONS:
        code, topic = row[:2]
        stem, a, b, c, d, e, correct, explanation, difficulty = db._unpack_question(row[2:])
        options = tuple(value for value in (a, b, c, d, e) if value)
        items.append(SeedItem(code, topic, stem, options, correct, explanation,
                              difficulty, "single"))
    for code, topic, stem, a, b, c, d, e, correct, explanation, difficulty in db._DM_YESNO_QUESTIONS:
        items.append(SeedItem(code, topic, stem, (a, b, c, d, e), correct,
                              explanation, difficulty, "multi"))
    return items


ITEMS = collect_items()


def find(fragment: str, code: str | None = None) -> SeedItem | None:
    matches = [item for item in ITEMS if fragment in item.stem and (code is None or item.code == code)]
    if len(matches) != 1:
        fail(f"[lookup] {fragment!r} matched {len(matches)} items; expected exactly one")
        return None
    return matches[0]


def check_structure_and_coverage() -> None:
    expected_counts = {"VR": 44, "DM": 35, "QR": 36, "SJT": 69}
    actual_counts = Counter(item.code for item in ITEMS)
    if actual_counts != Counter(expected_counts):
        fail(f"[coverage] subtest counts {dict(actual_counts)} != {expected_counts}")
    if len(ITEMS) != 184:
        fail(f"[coverage] total active seed count {len(ITEMS)} != 184")
    if any(item.code == "AR" for item in ITEMS):
        fail("[coverage] Abstract Reasoning content remains active")

    subject_codes = {code for code, *_ in db._SUBJECTS}
    topics_by_code: dict[str, set[str]] = defaultdict(set)
    for code, name, *_ in db._TOPICS:
        topics_by_code[code].add(name)

    seen_stems: set[str] = set()
    for index, item in enumerate(ITEMS, 1):
        prefix = f"[structure] {item.code} #{index} {item.stem[:45]!r}"
        if item.code not in subject_codes:
            fail(f"{prefix}: unknown subject")
        if item.topic not in topics_by_code[item.code]:
            fail(f"{prefix}: unknown topic {item.topic!r}")
        if item.difficulty not in {"Easy", "Medium", "Hard"}:
            fail(f"{prefix}: invalid difficulty {item.difficulty!r}")
        if not item.stem.strip() or not item.explanation.strip():
            fail(f"{prefix}: blank stem or explanation")
        if item.stem in seen_stems:
            fail(f"[dedup] duplicate stem {item.stem!r}")
        seen_stems.add(item.stem)
        if len(set(item.options)) != len(item.options):
            fail(f"{prefix}: duplicate options")
        if any(not option.strip() for option in item.options):
            fail(f"{prefix}: blank displayed option")
        if len(item.explanation.split()) < 22:
            fail(f"{prefix}: explanation is too brief to prove the key and diagnose distractors")

        letters = "ABCDE"[:len(item.options)]
        if item.question_format == "single":
            if item.correct not in letters:
                fail(f"{prefix}: single answer {item.correct!r} is outside {letters}")
        elif item.question_format == "multi":
            selected = item.correct.split(",")
            if selected != sorted(set(selected)) or not set(selected) <= set(letters):
                fail(f"{prefix}: DM multi key {item.correct!r} is invalid")
        elif item.question_format == "rank":
            selected = item.correct.split(",")
            if len(selected) != 2 or len(set(selected)) != 2 or not set(selected) <= set(letters):
                fail(f"{prefix}: SJT rank key {item.correct!r} is invalid")
        else:
            fail(f"{prefix}: unknown format {item.question_format!r}")

        is_vr_tfc = item.code == "VR" and item.options == ("True", "False", "Can't Tell")
        if not is_vr_tfc:
            for letter in letters:
                if not re.search(rf"\b{letter}\b", item.explanation):
                    fail(f"{prefix}: explanation does not address option {letter}")

    sets_by_code: dict[str, list[tuple]] = defaultdict(list)
    for passage_set in db._PASSAGE_SETS:
        sets_by_code[passage_set[0]].append(passage_set)
    if len(sets_by_code["VR"]) != 11 or any(len(group[4]) != 4 for group in sets_by_code["VR"]):
        fail("[coverage] VR must contain 11 four-question passage sets")
    qr_standalone = [item for item in ITEMS if item.code == "QR" and item.passage_title is None]
    if len(sets_by_code["QR"]) != 8 or any(len(group[4]) != 4 for group in sets_by_code["QR"]):
        fail("[coverage] QR must contain 8 four-question data sets")
    if len(qr_standalone) != 4:
        fail(f"[coverage] QR must contain 4 standalone questions; found {len(qr_standalone)}")
    if len(sets_by_code["SJT"]) != 16 or any(not 1 <= len(group[4]) <= 6 for group in sets_by_code["SJT"]):
        fail("[coverage] SJT scenarios must contain 1–6 questions across 16 groups")

    vr_items = [item for item in ITEMS if item.code == "VR"]
    tfc = [item for item in vr_items if item.options == ("True", "False", "Can't Tell")]
    mcq = [item for item in vr_items if len(item.options) == 4]
    if (len(tfc), len(mcq)) != (16, 28):
        fail(f"[format] VR T/F/CT and MCQ counts are {(len(tfc), len(mcq))}, expected (16, 28)")
    vr_sets = sets_by_code["VR"]
    tfc_sets = [group for group in vr_sets if all(
        tuple(value for value in db._unpack_question(raw)[1:6] if value)
        == ("True", "False", "Can't Tell") for raw in group[4]
    )]
    mcq_sets = [group for group in vr_sets if all(
        len(tuple(value for value in db._unpack_question(raw)[1:6] if value)) == 4
        for raw in group[4]
    )]
    if (len(tfc_sets), len(mcq_sets)) != (4, 7):
        fail(f"[format] VR must have 4 pure T/F/CT sets and 7 pure MCQ sets; "
             f"found {(len(tfc_sets), len(mcq_sets))}")
    if not any("EXCEPT" in item.stem for item in mcq):
        fail("[coverage] VR MCQs need at least one negative EXCEPT stem")
    if not any(item.stem.rstrip().endswith(":") for item in mcq):
        fail("[coverage] VR MCQs need at least one incomplete-statement stem")
    if not any(item.stem.startswith("According to") for item in mcq):
        fail("[coverage] VR MCQs need at least one direct-retrieval stem")
    if len({group[2] for group in vr_sets}) != 11:
        fail("[dedup] VR passage titles must be unique")
    for _code, _topic, title, body, questions in vr_sets:
        words = len((body or "").split())
        if not 280 <= words <= 330:
            fail(f"[density] VR passage {title!r} has {words} words; expected 280–330")
        paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if p]
        if len(paragraphs) != 4:
            fail(f"[density] VR passage {title!r} has {len(paragraphs)} paragraphs; expected exactly 4")
        paragraph_words = [len(p.split()) for p in paragraphs]
        if any(not 55 <= count <= 100 for count in paragraph_words):
            fail(f"[density] VR passage {title!r} paragraph lengths are {paragraph_words}; "
                 "each must be 55–100 words")
        unpacked = [db._unpack_question(raw) for raw in questions]
        if not any(raw[8] == "Hard" for raw in unpacked):
            fail(f"[difficulty] VR set {title!r} has no Hard question")
        if any(raw[0].lstrip().lower().startswith("passage:") for raw in unpacked):
            fail(f"[format] VR set {title!r} embeds a passage inside a question stem")
    vr_difficulties = Counter(item.difficulty for item in vr_items)
    if vr_difficulties["Hard"] < 14 or vr_difficulties["Easy"] > 8:
        fail(f"[difficulty] VR mix is too light for the target bank: {dict(vr_difficulties)}")

    dm_items = [item for item in ITEMS if item.code == "DM"]
    dm_single = [item for item in dm_items if item.question_format == "single"]
    dm_multi = [item for item in dm_items if item.question_format == "multi"]
    if (len(dm_single), len(dm_multi)) != (29, 6):
        fail(f"[format] DM single/multi counts are {(len(dm_single), len(dm_multi))}, expected (29, 6)")
    if any(len(item.options) != 4 for item in dm_single) or any(len(item.options) != 5 for item in dm_multi):
        fail("[format] DM single items need 4 options and multi items need 5 statements")
    required_dm_topics = {
        "Syllogisms & Logical Deduction", "Logic Puzzles & Arrangements",
        "Evaluating Arguments", "Venn Diagrams & Sets",
        "Probability & Statistics", "Interpreting Information",
    }
    missing_dm = required_dm_topics - {item.topic for item in dm_items}
    if missing_dm:
        fail(f"[coverage] missing DM varieties: {sorted(missing_dm)}")
    required_dm_sets = {
        "Annual Tutor Photograph", "Festival Supper Choices",
        "Community Project Volunteers", "Commuter Reliability Study",
        "Holiday Booking Survey",
    }
    dm_set_titles = {group[2] for group in sets_by_code["DM"]}
    missing_dm_sets = required_dm_sets - dm_set_titles
    if missing_dm_sets:
        fail(f"[coverage] missing official-style DM stimulus formats: {sorted(missing_dm_sets)}")
    passage_multi = [item for item in dm_multi if item.passage_title]
    if len(passage_multi) != 1 or passage_multi[0].passage_title != "Commuter Reliability Study":
        fail("[format] DM must include the table-based, passage-linked five-statement Yes/No item")
    if "| Intervention |" not in (passage_multi[0].passage_body or ""):
        fail("[format] the passage-linked DM Yes/No item is missing its data table")

    qr_items = [item for item in ITEMS if item.code == "QR"]
    if any(len(item.options) != 5 for item in qr_items):
        fail("[format] every QR item must have five options")

    sjt_items = [item for item in ITEMS if item.code == "SJT"]
    rank = [item for item in sjt_items if item.question_format == "rank"]
    rating = [item for item in sjt_items if item.question_format == "single"]
    if (len(rating), len(rank)) != (61, 8):
        fail(f"[format] SJT rating/rank counts are {(len(rating), len(rank))}, expected (61, 8)")
    app_scale = ("A very appropriate thing to do", "Appropriate, but not ideal",
                 "Inappropriate, but not awful", "A very inappropriate thing to do")
    imp_scale = ("Very important", "Important", "Of minor importance", "Not important at all")
    for item in rating:
        if item.options not in {app_scale, imp_scale}:
            fail(f"[format] SJT rating scale is invalid in {item.stem[:50]!r}")
    if any(len(item.options) != 3 for item in rank):
        fail("[format] every SJT most/least item must contain three actions")

    used_visuals: set[str] = set()
    for _code, _topic, _title, body, questions in db._PASSAGE_SETS:
        used_visuals.update(VISUAL_MARKER_RE.findall(body or ""))
        for raw in questions:
            unpacked = db._unpack_question(raw)
            for value in unpacked[:6]:
                used_visuals.update(VISUAL_MARKER_RE.findall(value or ""))
    unknown_visuals = used_visuals - set(VISUALS)
    if unknown_visuals:
        fail(f"[visual] unknown visual markers: {sorted(unknown_visuals)}")
    unused_visuals = set(VISUALS) - used_visuals
    if unused_visuals:
        fail(f"[visual] registry entries are unused: {sorted(unused_visuals)}")
    for visual_id, visual in VISUALS.items():
        if "<svg" not in visual.html or "aria-label=" not in visual.html:
            fail(f"[visual] {visual_id} is missing accessible SVG structure")
        if "<script" in visual.html.lower() or "http://" in visual.html.lower() or "https://" in visual.html.lower():
            fail(f"[visual] {visual_id} must remain self-contained and script-free")
    required_dm_visuals = {
        "dm_seating_row", "dm_shapes_a", "dm_shapes_b", "dm_shapes_c", "dm_shapes_d",
    }
    if not required_dm_visuals <= used_visuals:
        fail(f"[coverage] missing DM seating/compound-region visuals: "
             f"{sorted(required_dm_visuals - used_visuals)}")

    dm_visual_sets = [group for group in sets_by_code["DM"] if VISUAL_MARKER_RE.search(group[3] or "")
                      or any(VISUAL_MARKER_RE.search(value or "")
                             for raw in group[4] for value in db._unpack_question(raw)[:6])]
    if len(dm_visual_sets) < 2:
        fail(f"[coverage] DM has {len(dm_visual_sets)} visual set items; expected at least 2")
    qr_visual_sets = [group for group in sets_by_code["QR"] if VISUAL_MARKER_RE.search(group[3] or "")]
    if len(qr_visual_sets) < 5:
        fail(f"[coverage] QR has {len(qr_visual_sets)} chart/graph sets; expected at least 5 of 8")


def check_answer_balance() -> None:
    groups = {
        "VR-all": [item for item in ITEMS if item.code == "VR"],
        "DM-single": [item for item in ITEMS if item.code == "DM" and item.question_format == "single"],
        "QR": [item for item in ITEMS if item.code == "QR"],
        "SJT-rating": [item for item in ITEMS if item.code == "SJT" and item.question_format == "single"],
    }
    for name, items in groups.items():
        counts = Counter(item.correct for item in items)
        positions = "ABCDE"[:max(len(item.options) for item in items)]
        used = [counts[letter] for letter in positions if any(len(item.options) >= positions.index(letter) + 1 for item in items)]
        if min(used) == 0:
            fail(f"[balance] {name} leaves an available answer position unused: {dict(counts)}")
        allowed_spread = 6 if name == "VR-all" else 1
        if max(used) - min(used) > allowed_spread:
            fail(f"[balance] {name} answer positions are too uneven: {dict(counts)}")

    single = [item for item in ITEMS if item.question_format == "single"]
    correct_lengths = []
    distractor_lengths = []
    for item in single:
        for index, option in enumerate(item.options):
            length = len(option.split())
            if "ABCDE"[index] == item.correct:
                correct_lengths.append(length)
            else:
                distractor_lengths.append(length)
    ratio = (sum(correct_lengths) / len(correct_lengths)) / (sum(distractor_lengths) / len(distractor_lengths))
    if ratio > 1.30:
        fail(f"[balance] correct options average {ratio:.2f}× distractor length")


def _numbers(text: str) -> list[float]:
    cleaned = text.replace(",", "").replace("£", "").replace("€", "").replace("zł", "").replace("kr", "")
    return [float(token) for token in re.findall(r"(?<![A-Za-z])-?\d+(?:\.\d+)?", cleaned)]


def assert_numeric(fragment: str, value: float, note: str, tolerance: float = 0.011, code: str = "QR") -> None:
    item = find(fragment, code)
    if item is None:
        return
    hits = []
    for index, option in enumerate(item.options):
        if any(abs(number - value) <= tolerance for number in _numbers(option)):
            hits.append("ABCDE"[index])
    if item.correct not in hits or len(hits) != 1:
        fail(f"[math] {fragment!r}: computed {value} ({note}) matched {hits}, keyed {item.correct}")


def assert_option_text(fragment: str, required: tuple[str, ...], note: str, code: str = "QR") -> None:
    item = find(fragment, code)
    if item is None:
        return
    hits = ["ABCDE"[i] for i, option in enumerate(item.options) if all(part in option for part in required)]
    if hits != [item.correct]:
        fail(f"[proof] {fragment!r}: {note}; required {required} matched {hits}, keyed {item.correct}")


def check_qr_math() -> None:
    assert_numeric("6 swims and 3 exercise classes", 28 + 6 * 3.6 + 3 * 5.2, "monthly Standard total")
    assert_numeric("8 swims and 4 classes", (28 + 8 * 3.6 + 4 * 5.2) - (42 + 4 * 2.8), "Plus saving")
    assert_numeric("each hold Plus membership for 3 months", 3 * (42 + 42 * 0.85) + 4 * 5.5, "household total")
    assert_numeric("minimum number of classes", math.floor(22 / 2.4) + 1, "strict break-even class count")

    courier_costs = {
        "Northline": (6 + 8 * 0.8 + 40 * 0.15) * 1.05,
        "Swift": (9 + 8 * 0.55 + 40 * 0.12) * 1.05,
        "ParcelGo": (4.5 + 8 * 1.1 + 40 * 0.1) * 1.05,
    }
    cheapest = min(courier_costs, key=courier_costs.get)
    assert_option_text("Which courier is cheapest", (cheapest, f"£{courier_costs[cheapest]:.2f}"), "computed cheapest courier")
    assert_numeric("12 kg parcel 60 km", round((6 + 12 * 0.8 + 60 * 0.15) * 1.2 * 1.05, 2), "weekend Northline")
    swift = (9 + 5 * 0.55 + 25 * 0.12 + 4) * 1.05
    parcelgo = (4.5 + 5 * 1.1 + 25 * 0.1 + 2.5) * 1.05
    assert_numeric("How much cheaper is ParcelGo", round(swift - parcelgo, 2), "courier difference")
    max_weight = math.floor(((25 / 1.05) - 6 - 50 * 0.15) / 0.8)
    assert_numeric("greatest whole-number weight", max_weight, "Northline weight cap")

    assert_numeric("Household C's water charge", 8 + 15 * 1.2 + 15 * 1.65 + 5 * 2.1, "tiered water bill")
    assert_numeric("Household B's use increase", (24 - 12) / 12 * 100, "percentage increase")
    assert_numeric("Household D's charge", 8 + 15 * 1.2 + 5 * 1.65 - 5, "rebated bill")
    april, june = 18 + 12 + 26 + 15, 31 + 24 + 35 + 28
    assert_numeric("Combined use by all four", round((june - april) / april * 100, 1), "combined percentage increase")

    assert_numeric("exchanging £620", round(620 * 0.985 * 1.16, 2), "euros received")
    assert_numeric("needs zł2,900", round(2900 / 5.02 + 6, 2), "sterling required")
    assert_numeric("Danish kroner", 400 * 13.4 * 0.98, "kroner after fee")
    assert_numeric("returns €250", 250 * 0.82 - 4, "returned sterling")

    b_sheets = math.ceil(1800 / 0.93)
    assert_numeric("1,800 usable sheets", b_sheets / 52 + 18, "printer B duration", tolerance=0.06)
    assert_numeric("2,200 usable sheets", math.ceil(2200 / 0.95) * 0.03, "printer C paper cost")
    printer_times = {
        "A": math.ceil(1000 / 0.96) / 38 + 12,
        "B": math.ceil(1000 / 0.93) / 52 + 18,
        "C": math.ceil(1000 / 0.95) / 44 + 8,
        "D": math.ceil(1000 / 0.97) / 40 + 6,
    }
    assert_key("completes 1,000 usable sheets fastest", min(printer_times, key=printer_times.get),
               "computed fastest printer", code="QR")
    assert_numeric("greatest number of usable whole sheets", math.floor((75 - 12) * 38 * 0.96), "printer A capacity")

    assert_numeric("average speed of the 07:35", 72 / 1.5, "ferry average speed")
    assert_option_text("reaches Harbour at 08:55", ("11:10", "12:30"), "15-minute boarding rule")
    assert_numeric("advance return cost", (31 + 27) * 0.88 + 12, "discounted fares plus bicycle")
    return_rates = {"15:15": 30 / 85, "17:05": 27 / 82, "19:10": 24 / 95}
    best_return = min(return_rates, key=return_rates.get)
    assert_option_text("lowest listed fare per minute", (best_return, f"£{return_rates[best_return]:.2f}"), "computed fare per minute")

    concert_net = 240 * 25 + 1200 - 240 * 9.5 - 1800 - 0.024 * 240 * 25
    quiz_net = 180 * 18 * 1.10 - 180 * 5 - 900 - 0.024 * 180 * 18
    walk_net = 320 * 12 * 1.10 - 320 * 3.2 - 650 - 0.024 * 320 * 12
    assert_numeric("concert's net proceeds", concert_net, "concert net")
    assert_numeric("quiz's net proceeds", quiz_net, "quiz net")
    assert_numeric("combined net proceeds", walk_net + quiz_net + concert_net, "combined net")
    assert_numeric("minimum number of concert attendees", math.ceil((1800 - 1200) / (25 - 9.5 - 25 * 0.024)), "concert break-even")

    assert_numeric("Site A's estimated summer", round(80 * 720 * 0.22 * 0.94), "site A summer")
    assert_numeric("Site B's estimated winter", round(120 * 720 * 0.10 * 0.92), "site B winter")
    assert_numeric("greater is Site C's", round(95 * 720 * 0.95 * (0.20 - 0.09)), "site C seasonal difference")
    winter_total = 80 * 720 * 0.08 * 0.94 + 120 * 720 * 0.10 * 0.92 + 95 * 720 * 0.09 * 0.95
    assert_numeric("average estimated winter output", round(winter_total / 30), "combined daily winter output")

    assert_numeric("walking route measures", round(14.8 * 25000 / 100000 * 1.08, 2), "map scale and diversion")
    assert_numeric("tank contains 480 litres", round(200 / 450 * 100, 1), "mixture replacement")
    assert_numeric("machine normally produces", 750 / 6 * 1.12 * 5 * 0.94, "upgraded usable output")
    assert_numeric("recipe uses 1.2 kg", math.ceil((54 * 1.05 * 1.2 / 8) / 2), "whole flour bags")


def assert_key(fragment: str, expected: str, note: str, code: str = "DM") -> None:
    item = find(fragment, code)
    if item is not None and item.correct != expected:
        fail(f"[proof] {fragment!r}: {note}; computed key {expected}, stored {item.correct}")


def check_dm_numeric_and_arrangements() -> None:
    assert_numeric("exactly two of the services", (28 - 11) + (24 - 11) + (19 - 11), "exactly two sets", code="DM")
    chess_only = 47 - 19
    assert_numeric("How many play tennis", chess_only + 13 + 19, "tennis total", code="DM")
    assert_option_text("both are the same colour", ("19/66",), "combination probability", code="DM")
    assert_numeric("one positive result", round(180 / (180 + 80) * 100, 1), "conditional probability", code="DM")
    assert_numeric("overall probability of winning", 0.4 * 0.75 + 0.6 * 0.20, "total probability", code="DM")
    assert_numeric("highest percentage resolved", 442 / 520 * 100, "best target rate", code="DM")
    assert_numeric("present after Wednesday's returns", (240 * 0.75 + 45) * (2 / 3) + 12, "inventory sequence", code="DM")
    assert_numeric("12 of 300 people", (18 / 300 - 12 / 300) * 100, "percentage-point difference", code="DM")

    seating_models = []
    for order in itertools.permutations("ABCDEFGH"):
        pos = {name: order.index(name) for name in order}
        if pos["E"] != 4 or {pos["B"], pos["H"]} != {3, 5}:
            continue
        if pos["A"] not in ({0} if pos["B"] > 3 else {7}):
            continue
        if abs(pos["C"] - pos["H"]) != 1 or abs(pos["G"] - pos["H"]) != 3:
            continue
        if abs(pos["D"] - pos["B"]) == 1 or abs(pos["D"] - pos["F"]) == 1:
            continue
        seating_models.append(pos)
    seating_claims = (
        lambda m: m["A"] == 0,
        lambda m: abs(m["D"] - m["F"]) == 1,
        lambda m: abs(m["G"] - m["H"]) == 1,
        lambda m: m["F"] == 7,
    )
    seating_must = ["ABCD"[i] for i, claim in enumerate(seating_claims)
                    if seating_models and all(claim(model) for model in seating_models)]
    if len(seating_models) != 2 or seating_must != ["A"]:
        fail(f"[logic] seating produced {len(seating_models)} models and MUST options {seating_must}")
    assert_key("Which one of the following statements MUST", "A", "enumerated tutor seating")

    recorded_mains = Counter(("pasta", "fish", "fish", "pasta"))
    recorded_drinks = Counter(("tea", "juice", "tea", "juice"))
    remaining_main = Counter({"pasta": 2, "fish": 2, "curry": 1}) - recorded_mains
    remaining_drink = Counter({"coffee": 1, "tea": 2, "juice": 2}) - recorded_drinks
    if remaining_main != Counter({"curry": 1}) or remaining_drink != Counter({"coffee": 1}):
        fail(f"[logic] supper remainders are {remaining_main} and {remaining_drink}")
    assert_key("Which combination of main course", "D", "independent inventory subtraction")

    departments = {
        "Outreach": (2, 2), "Research": (2, 2), "Logistics": (2, 2),
        "Design": (2, 2), "Administration": (2, 3),
    }
    fixed_men = sum(men for name, (men, _women) in departments.items() if name != "Administration")
    fixed_women = sum(women for name, (_men, women) in departments.items() if name != "Administration")
    if (10 - fixed_men, 10 - fixed_women) != (2, 2):
        fail("[logic] volunteer totals do not force two men and two women from Administration")
    assert_key("Which volunteers must take the selection task", "C", "department and gender totals")

    commuter_truths = {"A", "C", "E"}
    commuter_matches = [item for item in ITEMS if item.passage_title == "Commuter Reliability Study"]
    if len(commuter_matches) != 1 or set(commuter_matches[0].correct.split(",")) != commuter_truths:
        fail("[logic] commuter table conclusions are not keyed A, C and E")

    colours = ("blue", "green", "red", "white")
    delivery_models = []
    for perm in itertools.permutations(colours):
        model = dict(zip("PQRS", perm))
        if model["P"] not in {"blue", "white"} and model["Q"] in {"green", "white"} and model["R"] != "red" and model["S"] == "blue":
            delivery_models.append(model)
    delivery_claims = [
        lambda m: m["P"] == "green", lambda m: m["Q"] == "white",
        lambda m: m["R"] == "red", lambda m: m["P"] == "red",
    ]
    must = ["ABCD"[i] for i, claim in enumerate(delivery_claims) if all(claim(m) for m in delivery_models)]
    if must != ["D"]:
        fail(f"[logic] delivery models imply {must}, expected D")
    assert_key("Four deliveries—P", "D", "enumerated colour assignments")

    clinic_orders = [p for p in itertools.permutations("ABCD")
                     if p.index("B") < p.index("A") < p.index("C") and p.index("A") == p.index("D") + 1]
    final_people = {order[-1] for order in clinic_orders}
    if final_people != {"C"}:
        fail(f"[logic] clinic final people {final_people}, expected C")
    assert_key("assigns Ana, Bilal", "C", "enumerated shift orders")

    book_options = [tuple(text.split(", ")) for text in [
        "G, J, K, H, L, F", "F, H, J, K, L, G", "G, H, F, J, K, L", "L, F, H, K, J, G"]]
    def valid_books(order: tuple[str, ...]) -> bool:
        pos = {name: order.index(name) for name in order}
        return pos["F"] < pos["H"] and pos["K"] == pos["J"] + 1 and pos["G"] in {0, 5} and abs(pos["L"] - pos["H"]) != 1
    valid_books_letters = ["ABCD"[i] for i, order in enumerate(book_options) if valid_books(order)]
    if valid_books_letters != ["B"]:
        fail(f"[logic] book arrangements have valid options {valid_books_letters}, expected B")
    assert_key("Six books—F", "B", "enumerated book arrangements")



def _all(model: dict[str, tuple[bool, ...]], left: str, right: str) -> bool:
    return all(not a or b for a, b in zip(model[left], model[right]))


def _none(model: dict[str, tuple[bool, ...]], left: str, right: str) -> bool:
    return all(not (a and b) for a, b in zip(model[left], model[right]))


def _exists(model: dict[str, tuple[bool, ...]], *positive: str, negative: tuple[str, ...] = ()) -> bool:
    size = len(next(iter(model.values())))
    return any(all(model[name][i] for name in positive) and all(not model[name][i] for name in negative)
               for i in range(size))


def verify_models(fragment: str, predicates: tuple[str, ...], premise, conclusions: tuple, expected: set[str]) -> None:
    models = []
    size = 3
    for bits in itertools.product((False, True), repeat=len(predicates) * size):
        model = {name: tuple(bits[(i * size):((i + 1) * size)]) for i, name in enumerate(predicates)}
        if premise(model):
            models.append(model)
    if not models:
        fail(f"[logic-model] {fragment!r} has no satisfying model")
        return
    entailed = {"ABCDE"[i] for i, conclusion in enumerate(conclusions) if all(conclusion(model) for model in models)}
    if entailed != expected:
        fail(f"[logic-model] {fragment!r} entails {sorted(entailed)}, expected {sorted(expected)}")
    item = find(fragment, "DM")
    if item is not None:
        stored = set(item.correct.split(","))
        if stored != expected:
            fail(f"[logic-model] {fragment!r} stored {sorted(stored)}, expected {sorted(expected)}")


def check_dm_syllogism_models() -> None:
    verify_models(
        "Every amber file", ("amber", "archived", "editable", "report"),
        lambda m: _all(m, "amber", "archived") and _none(m, "archived", "editable") and _exists(m, "report", "editable"),
        (
            lambda m: _exists(m, "report", negative=("amber",)),
            lambda m: _none(m, "report", "archived"),
            lambda m: _exists(m, "amber", "editable"),
            lambda m: all(m["editable"][i] for i in range(len(m["amber"])) if not m["amber"][i]),
        ), {"A"})
    verify_models(
        "No untrained employee", ("untrained", "supervises", "assistant", "fellow"),
        lambda m: _none(m, "untrained", "supervises") and _exists(m, "assistant", "untrained") and _all(m, "fellow", "assistant"),
        (
            lambda m: _none(m, "assistant", "supervises"),
            lambda m: _exists(m, "assistant", negative=("supervises",)),
            lambda m: all(not m["assistant"][i] or m["fellow"][i] for i in range(len(m["assistant"])) if not m["untrained"][i]),
            lambda m: _exists(m, "fellow", "untrained"),
        ), {"B"})
    verify_models(
        "No metal token", ("metal", "glows", "green", "square"),
        lambda m: _none(m, "metal", "glows") and _all(m, "green", "glows") and _exists(m, "square", "green"),
        (
            lambda m: _all(m, "square", "glows"),
            lambda m: _none(m, "square", "metal"),
            lambda m: _exists(m, "square", negative=("metal",)),
            lambda m: _all(m, "metal", "green"),
        ), {"C"})

    verify_models(
        "Every instrument in a rehearsal cabinet", ("tuned", "repair", "labelled", "insured", "top"),
        lambda m: (all(m["tuned"][i] != m["repair"][i] for i in range(len(m["tuned"])))
                   and _all(m, "tuned", "labelled")
                   and _exists(m, "labelled", negative=("tuned",))
                   and _exists(m, "repair", "insured")
                   and _none(m, "insured", "top")),
        (
            lambda m: sum(m["tuned"]) < sum(m["labelled"]),
            lambda m: _exists(m, "insured", "labelled"),
            lambda m: _none(m, "insured", "top"),
            lambda m: _exists(m, "labelled", "repair"),
            lambda m: sum(m["insured"]) > len(m["insured"]) / 2,
        ), {"A", "C", "D"})
    verify_models(
        "All bronze passes", ("bronze", "h1", "h2", "temporary"),
        lambda m: _all(m, "bronze", "h1") and _exists(m, "h1", "h2") and _none(m, "temporary", "h2"),
        (
            lambda m: _exists(m, "h1", "h2"),
            lambda m: _none(m, "bronze", "temporary"),
            lambda m: _exists(m, "h1", negative=("temporary",)),
            lambda m: _all(m, "h2", "bronze"),
            lambda m: _exists(m, "temporary", "h1"),
        ), {"A", "C"})
    verify_models(
        "Every oak in the reserve", ("oak", "tagged", "diseased", "open"),
        lambda m: _all(m, "oak", "tagged") and _exists(m, "tagged", "diseased") and _none(m, "diseased", "open") and _exists(m, "oak", "open"),
        (
            lambda m: _exists(m, "tagged", negative=("diseased",)),
            lambda m: _none(m, "oak", "diseased"),
            lambda m: _exists(m, "open", "tagged"),
            lambda m: all(m["open"][i] for i in range(len(m["tagged"])) if not m["tagged"][i]),
            lambda m: _exists(m, "diseased", negative=("oak",)),
        ), {"A", "C"})
    verify_models(
        "No silver ticket", ("silver", "refundable", "weekend", "discounted", "complimentary"),
        lambda m: _none(m, "silver", "refundable") and _all(m, "weekend", "refundable") and _exists(m, "discounted", "silver") and _none(m, "complimentary", "discounted"),
        (
            lambda m: _none(m, "weekend", "silver"),
            lambda m: _exists(m, "discounted", negative=("refundable",)),
            lambda m: _all(m, "refundable", "weekend"),
            lambda m: _exists(m, "silver", negative=("complimentary",)),
            lambda m: _none(m, "complimentary", "silver"),
        ), {"A", "B", "D"})
    verify_models(
        "All evening workshops", ("evening", "booking", "free", "music", "outdoor"),
        lambda m: _all(m, "evening", "booking") and _none(m, "free", "booking") and _exists(m, "music", "evening") and _all(m, "outdoor", "free"),
        (
            lambda m: _exists(m, "music", "booking"),
            lambda m: _none(m, "evening", "free"),
            lambda m: _exists(m, "music", negative=("outdoor",)),
            lambda m: _all(m, "booking", "evening"),
            lambda m: _none(m, "outdoor", "evening"),
        ), {"A", "B", "C", "E"})
    parcel_valid = []
    for courier_x, courier_y, after_tuesday in itertools.product((False, True), repeat=3):
        if courier_x != courier_y and (not courier_y or after_tuesday) and not after_tuesday:
            parcel_valid.append((courier_x, courier_y, after_tuesday))
    if not parcel_valid or not all(model[0] for model in parcel_valid):
        fail("[logic-model] courier parcel premises do not force courier X")
    assert_key("A parcel is sent", "B", "enumerated propositional courier models")

    grant_models = []
    for renewed, review, audit, late in itertools.product((False, True), repeat=4):
        valid = ((not renewed or review or audit) and (not (audit and renewed) or not late)
                 and renewed and not review and late)
        if valid:
            grant_models.append((renewed, review, audit, late))
    if grant_models:
        fail("[logic-model] contradictory grant facts unexpectedly have a satisfying model")
    assert_key("Every grant that is renewed", "D", "enumerated contradiction")


def check_visual_logic() -> None:
    """Independently verify the visual DM keys, geometry and set arithmetic."""
    points = {"G": (120, 205), "M": (250, 160), "R": (330, 140), "P": (220, 265)}

    def in_triangle(point, a=(240, 35), b=(430, 285), c=(90, 285)):
        def sign(p1, p2, p3):
            return ((p1[0] - p3[0]) * (p2[1] - p3[1])
                    - (p2[0] - p3[0]) * (p1[1] - p3[1]))
        d1, d2, d3 = sign(point, a, b), sign(point, b, c), sign(point, c, a)
        has_negative = d1 < 0 or d2 < 0 or d3 < 0
        has_positive = d1 > 0 or d2 > 0 or d3 > 0
        return not (has_negative and has_positive)

    triple = []
    for label, (x, y) in points.items():
        in_robotics = 35 <= x <= 270 and 85 <= y <= 235
        in_orchestra = ((x - 290) / 150) ** 2 + ((y - 160) / 95) ** 2 <= 1
        if in_robotics and in_orchestra and in_triangle((x, y)):
            triple.append(label)
    if triple != ["M"]:
        fail(f"[visual-logic] workshop triple-overlap labels are {triple}, expected ['M']")
    assert_key("Which labelled group attended robotics", "B", "independent shape-membership test")

    ceramics_total, print_total, overlap, photography, neither = 11, 14, 5, 8, 6
    regions = (ceramics_total - overlap, overlap, print_total - overlap, photography, neither)
    if regions != (6, 5, 9, 8, 6):
        fail(f"[visual-logic] makers' evening regions are {regions}")
    venn_item = find("Which diagram correctly represents", "DM")
    if venn_item is not None:
        if venn_item.correct != "D":
            fail(f"[visual-logic] makers' evening key is {venn_item.correct}, expected D")
        if "[[VISUAL:dm_venn_d]]" not in venn_item.options[3]:
            fail("[visual-logic] correct makers' evening option is not linked to diagram D")

    shape_regions = {
        "A": (7, 3, 4, 0, 4, 2, 6, 4),
        "B": (4, 3, 5, 1, 6, 2, 6, 3),
        "C": (6, 1, 5, 3, 4, 2, 6, 3),
        "D": (6, 3, 5, 1, 4, 2, 6, 3),
    }
    valid_shape_options = []
    for letter, (p_only, t_only, c_only, pt, pc, tc, triple, outside) in shape_regions.items():
        total = p_only + t_only + c_only + pt + pc + tc + triple + outside
        planning_total = p_only + pt + pc + triple
        planning_not_triangle = p_only + pc
        ratio_matches = planning_not_triangle > 0 and pc * 5 == planning_not_triangle * 2
        if total == 30 and planning_total == 17 and triple == 6 and ratio_matches:
            valid_shape_options.append(letter)
    if valid_shape_options != ["D"]:
        fail(f"[visual-logic] compound survey diagrams valid options are {valid_shape_options}")
    survey_item = find("Which diagram could correctly represent all", "DM")
    if survey_item is not None:
        if survey_item.correct != "D":
            fail(f"[visual-logic] holiday survey key is {survey_item.correct}, expected D")
        for index, letter in enumerate("ABCD"):
            if f"[[VISUAL:dm_shapes_{letter.lower()}]]" not in survey_item.options[index]:
                fail(f"[visual-logic] holiday survey option {letter} has the wrong diagram marker")


def check_yes_no_component() -> None:
    """Guard the interaction contract used by all five-statement DM items."""
    component_path = ROOT / "components" / "yes_no_drop" / "index.html"
    if not component_path.is_file():
        fail("[component] the DM Yes/No placement component is missing")
        return
    source = component_path.read_text(encoding="utf-8")
    required_contracts = {
        'draggable="true"': "draggable Yes/No source tiles",
        'addEventListener("drop"': "native drag-and-drop handling",
        'addEventListener("pointerdown"': "pointer/touch drag handling",
        'addEventListener("mouseup"': "mouse drag fallback",
        'streamlit:setComponentValue': "Streamlit answer-value reporting",
        'state.statements.every': "all-five-statements completion gating",
        'aria-label': "accessible answer controls",
    }
    for token, purpose in required_contracts.items():
        if token not in source:
            fail(f"[component] Yes/No widget is missing {purpose}")


def check_live_seed_smoke_test() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ.pop("DATABASE_URL", None)
        fresh = importlib.reload(db)
        fresh.DB_PATH = Path(temp_dir) / "question-smoke.db"
        fresh._USE_PG = False
        fresh._DB_URL = ""
        fresh._BOOTSTRAPPED = False
        fresh.init_db()

        conn = sqlite3.connect(fresh.DB_PATH)
        counts = dict(conn.execute("""
            SELECT s.code, COUNT(*) FROM questions q
            JOIN subjects s ON s.id=q.subject_id
            WHERE q.active=1 OR q.active IS NULL
            GROUP BY s.code
        """).fetchall())
        if counts != {"DM": 35, "QR": 36, "SJT": 69, "VR": 44}:
            fail(f"[smoke] active seeded counts are {counts}")
        before = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        custom_subject = conn.execute("SELECT id FROM subjects WHERE code='DM'").fetchone()[0]
        custom_id = conn.execute("""
            INSERT INTO questions(subject_id, stem, option_a, option_b, option_c, option_d,
                                  correct, explanation, difficulty, question_format, active)
            VALUES(?, 'User-created sentinel question', 'A', 'B', 'C', 'D', 'A',
                   'User-created sentinel explanation.', 'Medium', 'single', 1)
        """, (custom_subject,)).lastrowid
        vr_subject = conn.execute("SELECT id FROM subjects WHERE code='VR'").fetchone()[0]
        short_vr_id = conn.execute("""
            INSERT INTO questions(subject_id, stem, option_a, option_b, option_c, option_d,
                                  correct, explanation, difficulty, question_format, active)
            VALUES(?, 'Passage: A one-sentence user-created VR sentinel.',
                   'True', 'False', 'Can''t Tell', 'Partly true', 'A',
                   'Short standalone VR sentinel explanation.', 'Medium', 'single', 1)
        """, (vr_subject,)).lastrowid
        retired_stem = sorted(fresh._RETIRED_SEEDED_STEMS)[0]
        retired_id = conn.execute("""
            INSERT INTO questions(subject_id, stem, option_a, option_b, option_c, option_d,
                                  correct, explanation, difficulty, question_format, active)
            VALUES(?, ?, 'A', 'B', 'C', 'D', 'A', 'Retired seed sentinel.', 'Medium', 'single', 1)
        """, (custom_subject, retired_stem)).lastrowid
        user_id = conn.execute("""
            INSERT INTO users(username,password_hash,salt,hash_iterations,created_at)
            VALUES('validator-user','x','y',100000,'now')
        """).lastrowid
        conn.execute("""
            INSERT INTO attempts(user_id,question_id,subject_id,chosen,is_correct,seconds,created_at)
            VALUES(?,?,?,?,?,?,?)
        """, (user_id, retired_id, custom_subject, "A", 1, 1.0, "now"))
        conn.execute("""
            INSERT INTO attempts(user_id,question_id,subject_id,chosen,is_correct,seconds,created_at)
            VALUES(?,?,?,?,?,?,?)
        """, (user_id, short_vr_id, vr_subject, "A", 1, 1.0, "now"))
        conn.commit()
        conn.close()

        first = fresh.backfill_content()
        second = fresh.backfill_content()
        conn = sqlite3.connect(fresh.DB_PATH)
        after = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        custom_active = conn.execute("SELECT active FROM questions WHERE id=?", (custom_id,)).fetchone()[0]
        short_vr_active = conn.execute("SELECT active FROM questions WHERE id=?", (short_vr_id,)).fetchone()[0]
        retired_active = conn.execute("SELECT active FROM questions WHERE id=?", (retired_id,)).fetchone()[0]
        attempt_count = conn.execute("SELECT COUNT(*) FROM attempts WHERE question_id=?", (retired_id,)).fetchone()[0]
        short_vr_attempts = conn.execute("SELECT COUNT(*) FROM attempts WHERE question_id=?", (short_vr_id,)).fetchone()[0]
        conn.close()
        served_vr = fresh.get_questions(subject_id=vr_subject)
        if first != {"topics_added": 0, "questions_added": 0, "flashcards_added": 0}:
            fail(f"[smoke] first idempotent backfill reported {first}")
        if second != {"topics_added": 0, "questions_added": 0, "flashcards_added": 0}:
            fail(f"[smoke] second idempotent backfill reported {second}")
        if after != before + 3:
            fail(f"[smoke] backfill changed row count from {before + 3} to {after}")
        if custom_active != 1:
            fail("[smoke] user-created sentinel was modified or retired")
        if retired_active != 0 or attempt_count != 1:
            fail("[smoke] superseded seed was not retired while preserving its attempt")
        if short_vr_active != 0 or short_vr_attempts != 1:
            fail("[smoke] standalone VR was not retired while preserving its attempt")
        if len(served_vr) != 44 or any(not row.get("passage_id") for row in served_vr):
            fail(f"[smoke] serving query exposed invalid VR rows; returned {len(served_vr)} items")


def run() -> None:
    check_structure_and_coverage()
    check_answer_balance()
    check_qr_math()
    check_dm_numeric_and_arrangements()
    check_dm_syllogism_models()
    check_visual_logic()
    check_yes_no_component()
    check_live_seed_smoke_test()

    print(f"Active seed bank size: {len(ITEMS)}")
    print("Counts:", dict(Counter(item.code for item in ITEMS)))
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for failure in FAILURES:
            print(" -", failure)
        print("\nRESULT: FAIL")
        raise SystemExit(1)
    print("RESULT: PASS — format, structure, visual coverage, independent math, logic models, and seed migration checks passed.")


if __name__ == "__main__":
    run()
