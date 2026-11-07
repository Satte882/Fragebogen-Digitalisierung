"""Compare a private live evaluation snapshot with independently recorded ground truth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.contracts import Answer


QUESTIONS = tuple(f"q{i}" for i in range(1, 6))


def index_cases(document: dict, key: str = "id") -> dict:
    cases = document["cases"]
    indexed = {case[key]: case for case in cases}
    if len(indexed) != len(cases) or not indexed:
        raise ValueError("Cases must have unique IDs and at least one entry.")
    return indexed


def score(reference: dict, observed: dict) -> dict:
    if reference.get("schema_version") != 1 or observed.get("source") != "live":
        raise ValueError("Expected ground-truth schema v1 and a live snapshot.")
    expected = index_cases(reference)
    actual = index_cases(observed, "filename" if reference.get("id_kind") == "filename" else "id")
    if expected.keys() != actual.keys():
        raise ValueError("Ground truth and live snapshot must cover exactly the same image IDs.")
    report = {
        "forms": len(expected), "fields": len(expected) * len(QUESTIONS), "field_hits": 0,
        "complete_hits": 0, "assessed_complete": 0, "green": 0,
        "false_green": 0, "green_fully_assessed": 0, "green_unknown": 0,
        "warnings_expected": 0, "warnings_detected": 0, "technical_failures": 0,
        "corrected": 0, "individually_reviewed": 0,
        "transcripts_exact": 0, "transcripts_assessed": 0,
        "translations_exact": 0, "translations_assessed": 0,
        "final_forms": 0, "final_field_hits": 0, "final_fields": 0,
        "final_translations_exact": 0, "final_translations_assessed": 0,
        "calls": 0, "estimated_cost": None, "seconds_by_image": {},
    }
    for case_id, truth in expected.items():
        if type(truth["requires_review"]) is not bool:
            raise ValueError("requires_review must be a boolean.")
        if truth["answers"].keys() != set(QUESTIONS):
            raise ValueError("Ground truth requires exactly q1 through q5.")
        for answer in truth["answers"].values():
            Answer.model_validate(answer)
        entry = actual[case_id]
        recognition = entry["recognition"] or {}
        hits = sum(truth["answers"][key] == recognition.get(key) for key in QUESTIONS)
        report["field_hits"] += hits
        if final := entry.get("final"):
            report["final_forms"] += 1
            report["final_fields"] += len(QUESTIONS)
            report["final_field_hits"] += sum(truth["answers"][key] == final.get(key) for key in QUESTIONS)
            if "german_translation" in truth:
                report["final_translations_assessed"] += 1
                report["final_translations_exact"] += truth["german_translation"] == final.get("text", {}).get("german_translation")
        green = entry["classification"] == "ready"
        report["green"] += green
        warning = truth["requires_review"]
        report["warnings_expected"] += warning
        report["warnings_detected"] += warning and entry["classification"] == "review_required"
        report["technical_failures"] += not recognition
        matches = hits == len(QUESTIONS)
        complete = all(key in truth for key in ("original_transcript", "german_translation", "text_status"))
        for key, label in (("original_transcript", "transcripts"), ("german_translation", "translations")):
            if key in truth:
                equal = truth[key] == recognition.get("text", {}).get(key)
                report[label + "_assessed"] += 1
                report[label + "_exact"] += equal
                matches &= equal
        if "text_status" in truth:
            matches &= truth["text_status"] == recognition.get("text", {}).get("text_status")
        report["assessed_complete"] += complete
        report["complete_hits"] += complete and matches
        report["false_green"] += green and not matches
        report["green_unknown"] += green and matches and not complete
        report["green_fully_assessed"] += green and (complete or not matches)
        report["corrected"] += entry["review_mode"] == "corrected"
        report["individually_reviewed"] += entry["confirmation_source"] in ("individual", "sample")
        report["calls"] += sum(run["calls"] for run in entry["runs"])
        report["seconds_by_image"][case_id] = round(sum(run["duration_seconds"] for run in entry["runs"]), 3)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("live_snapshot", type=Path)
    args = parser.parse_args()
    print(json.dumps(score(json.loads(args.ground_truth.read_text(encoding="utf-8")),
                           json.loads(args.live_snapshot.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
