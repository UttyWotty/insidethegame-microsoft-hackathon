"""Tests for the numeric grounding check and JSON extraction helpers.

They verify that faithful rounding passes while invented numbers are rejected.
No model or I/O is involved.
"""

from insidegame.agents.grounding import check_grounding, collect_evidence_numbers
from insidegame.agents.runner import extract_json_text

EVIDENCE = {"facts": {"xg": 0.114, "shot_speed_kmh": 92.95, "distance_m": 16.4}, "score": "Kestrel 2-1 Ironvale",
            "teams": {"Kestrel": {"pass_accuracy": 0.776}}, "minute": 68}


def test_collects_numbers_from_nested_values_and_strings() -> None:
    numbers = collect_evidence_numbers(EVIDENCE)
    assert {0.114, 92.95, 16.4, 2.0, 1.0, 0.776, 68.0} <= numbers


def test_rounded_and_percentage_forms_are_grounded() -> None:
    report = check_grounding(["A 93 km/h strike from 16 metres in the 68th minute", "78% passing, 0.11 xG"], EVIDENCE)
    assert report.grounded


def test_invented_numbers_are_rejected() -> None:
    report = check_grounding(["His 7th goal of the season at 120 km/h"], EVIDENCE)
    assert not report.grounded
    assert set(report.ungrounded) == {7.0, 120.0}


def test_text_without_numbers_is_grounded() -> None:
    assert check_grounding(["What a finish!"], EVIDENCE).grounded


def test_extract_json_text_strips_reasoning_and_fences() -> None:
    raw = '<think>\nhmm\n</think>\n```json\n{"line": "Goal!"}\n```'
    assert extract_json_text(raw) == '{"line": "Goal!"}'
