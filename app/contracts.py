"""Strict field contract; the model response must be independently validated."""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


AnswerStatus = Literal["answered", "no_answer", "multiple", "unreadable"]
TextStatus = Literal["translated", "empty", "unreadable", "review_required"]


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int | None
    status: AnswerStatus

    @model_validator(mode="after")
    def check_consistency(self) -> "Answer":
        if self.status == "answered" and (type(self.value) is not int or self.value not in (1, 2, 3, 4)):
            raise ValueError("answered requires integer 1–4")
        if self.status != "answered" and self.value is not None:
            raise ValueError("unanswered values must be null")
        return self


class TextResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    original_transcript: str = Field(max_length=5000)
    source_language: str = Field(max_length=50)
    german_translation: str = Field(max_length=5000)
    text_status: TextStatus

    @model_validator(mode="after")
    def check_text(self) -> "TextResult":
        if self.text_status == "empty" and (self.original_transcript.strip() or self.german_translation.strip()):
            raise ValueError("empty means no text")
        if self.text_status == "translated" and not self.german_translation.strip():
            raise ValueError("translated requires text")
        return self


ReviewField = Literal["q1", "q2", "q3", "q4", "q5", "text", "image"]


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    field: ReviewField
    kind: Literal["multiple_marks", "unclear_mark", "unreadable_text", "translation", "image_quality", "other"]
    reason: str = Field(min_length=1, max_length=300)


class Recognition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    q1: Answer
    q2: Answer
    q3: Answer
    q4: Answer
    q5: Answer
    text: TextResult
    warnings: list[str] = Field(default_factory=list, max_length=10)

    findings: list[ReviewFinding] = Field(default_factory=list, max_length=10)
    regions: dict[ReviewField, list[float]] = Field(default_factory=dict, max_length=7)

    @model_validator(mode="after")
    def remove_invalid_regions(self) -> "Recognition":
        self.regions = {
            name: box for name, box in self.regions.items()
            if len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1
        }
        return self

    @property
    def recommended_status(self) -> str:
        answers = [getattr(self, f"q{i}") for i in range(1, 6)]
        if (self.findings or self.warnings or any(a.status in ("multiple", "unreadable") for a in answers)
                or self.text.text_status in ("unreadable", "review_required")):
            return "review_required"
        return "ready"


class FinalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int | None
    status: AnswerStatus

    @model_validator(mode="after")
    def validate_value(self) -> "FinalAnswer":
        Answer(value=self.value, status=self.status)
        return self


class FinalText(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    german_translation: str = Field(max_length=5000)
    text_status: Literal["translated", "empty", "unreadable"]

    @model_validator(mode="after")
    def validate_translation(self) -> "FinalText":
        if self.text_status == "empty" and self.german_translation.strip():
            raise ValueError("empty text must be blank")
        if self.text_status == "translated" and not self.german_translation.strip():
            raise ValueError("translated text must be nonempty")
        return self


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    q1: FinalAnswer
    q2: FinalAnswer
    q3: FinalAnswer
    q4: FinalAnswer
    q5: FinalAnswer
    text: FinalText
    evidence_confirmed: bool = False
    multiple_reasons: dict[Literal['q1', 'q2', 'q3', 'q4', 'q5'], Annotated[str, Field(max_length=400)]] = Field(default_factory=dict, max_length=5)


def suggestion(recognition: Recognition) -> dict:
    return {
        **{f"q{i}": getattr(recognition, f"q{i}").model_dump() for i in range(1, 6)},
        "text": {
            "german_translation": recognition.text.german_translation,
            "text_status": recognition.text.text_status,
        },
    }
