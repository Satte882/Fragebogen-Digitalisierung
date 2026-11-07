"""CSV export of confirmed records only; raw recognition must never leak here."""
from __future__ import annotations

import csv
import io


COLUMNS = [
    "batch_id", "batch_name", "image_id", "image_number", "filename",
    *[f"q{n}_{part}" for n in range(1, 6) for part in ("value", "status")],
    "text_de", "text_status", "review_mode", "review_status",
]


def safe_cell(value: object) -> str:
    """Prevent accidental spreadsheet formulas; keep internal values unchanged."""
    if value is None:
        return ""
    s = str(value)
    if s.startswith(("\t", "\r", "\n")) or s.lstrip().startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠")):
        return "'" + s
    return s


def batch_csv(batch: dict) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, COLUMNS, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for item in batch["items"].values():
        if item["status"] != "confirmed" or item["final"] is None:
            continue
        final = item["final"]
        record = {
            "batch_id": batch["id"],
            "batch_name": batch["name"],
            "image_id": item["id"],
            "image_number": item["sequence"],
            "filename": item["filename"],
            "text_de": final["text"]["german_translation"],
            "text_status": final["text"]["text_status"],
            "review_mode": item["review_mode"],
            "review_status": "confirmed",
        }
        for number in range(1, 6):
            question = final[f"q{number}"]
            record[f"q{number}_value"] = question["value"]
            record[f"q{number}_status"] = question["status"]
        writer.writerow({col: safe_cell(record.get(col, "")) for col in COLUMNS})
    return out.getvalue().encode("utf-8-sig")
