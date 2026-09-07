from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Question:
    id: int
    question_type: str
    question: str
    normalized_question: str
    options: dict[str, str]
    answer: str
    section: str
    source_file: str
    source_paragraph_start: int
    source_paragraph_end: int

    def answer_options(self) -> list[tuple[str, str]]:
        if self.question_type == "true_false":
            return []
        return [(letter, self.options.get(letter, "")) for letter in self.answer]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchHit:
    question: Question
    score: float
    match_method: str
    lexical_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["question"] = self.question.to_dict()
        return payload


@dataclass
class SearchResult:
    status: str
    query: str
    normalized_query: str
    selected: SearchHit | None = None
    candidates: list[SearchHit] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "normalized_query": self.normalized_query,
            "selected": self.selected.to_dict() if self.selected else None,
            "candidates": [item.to_dict() for item in self.candidates],
            "reason": self.reason,
        }
