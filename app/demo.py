"""Synthetic demonstration fixtures. These are NOT model-recognition results."""
from __future__ import annotations

import io
from PIL import Image, ImageDraw

from .contracts import Recognition


QUESTIONS = (
    "Informationen verstaendlich?",
    "Ablauf gut organisiert?",
    "Zeitplanung nachvollziehbar?",
    "Unterstuetzung hilfreich?",
    "Insgesamt zufrieden?",
)


def demo_photo(values: list[int | None | str], comment: str) -> bytes:
    canvas = Image.new("RGB", (1000, 1230), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((85, 85), "NEUTRALES TESTFORMULAR / SYNTHETISCHE DATEN", fill="#17293b")
    draw.text((85, 122), "Bewertung: 1 = niedrig, 4 = hoch", fill="#333333")
    for idx, (question, value) in enumerate(zip(QUESTIONS, values)):
        y = 210 + idx * 125
        draw.text((85, y), f"{idx+1}. {question}", fill="black")
        for number in (1, 2, 3, 4):
            x = 420 + (number - 1) * 120
            draw.rectangle((x, y + 35, x + 39, y + 74), outline="black", width=2)
            draw.text((x + 12, y + 80), str(number), fill="black")
            if value == number or (value == "2+3" and number in (2, 3)):
                draw.line((x + 5, y + 50, x + 16, y + 66, x + 35, y + 39), fill="black", width=4)
    draw.text((85, 925), "Freitext:", fill="black")
    draw.text((85, 975), comment[:100], fill="black")
    for y in (1020, 1060, 1100, 1140):
        draw.line((85, y, 910, y), fill="#a7b9c8", width=1)
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


FIXTURES = [
    {
        "filename": "synthetisch_01.jpg",
        "values": [4, 3, 4, 2, 3],
        "comment": "Everything was well organized.",
        "recognition": {
            **{f"q{i}": {"value": value, "status": "answered"} for i, value in enumerate([4, 3, 4, 2, 3], 1)},
            "text": {"original_transcript": "Everything was well organized.", "source_language": "en",
                     "german_translation": "Alles war gut organisiert.", "text_status": "translated"},
            "warnings": [],
        },
    },
    {
        "filename": "synthetisch_02.jpg",
        "values": [2, None, 3, "2+3", 1],
        "comment": "",
        "recognition": {
            "q1": {"value": 2, "status": "answered"},
            "q2": {"value": None, "status": "no_answer"},
            "q3": {"value": 3, "status": "answered"},
            "q4": {"value": None, "status": "multiple"},
            "q5": {"value": 1, "status": "answered"},
            "text": {"original_transcript": "", "source_language": "unknown", "german_translation": "", "text_status": "empty"},
            "warnings": ["Frage 4 ist als Mehrfachmarkierung markiert (synthetisches Prüfszenario)."],
        },
    },
    {
        "filename": "synthetisch_03.jpg",
        "values": [4, 4, 4, 4, 4],
        "comment": "Kurz und angenehm.",
        "recognition": {
            **{f"q{i}": {"value": 4, "status": "answered"} for i in range(1, 6)},
            "text": {"original_transcript": "Kurz und angenehm.", "source_language": "de",
                     "german_translation": "Kurz und angenehm.", "text_status": "review_required"},
            "warnings": ["Bitte Freitext manuell kontrollieren (synthetisches Prüfszenario)."],
        },
    },
]


def make_demo_items() -> list[tuple[str, bytes, Recognition]]:
    return [(f["filename"], demo_photo(f["values"], f["comment"]), Recognition.model_validate(f["recognition"])) for f in FIXTURES]
