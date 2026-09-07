from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document

from .models import Question
from .normalization import clean_text, normalize_question


ANSWER_PATTERN = re.compile(r"^(?:【答案】)?([A-D]{1,4}|正确|错误)$")
TYPE_LABELS = {
    "单项选择题": "single_choice",
    "多项选择题": "multiple_choice",
    "判断题": "true_false",
}


@dataclass
class ParseIssue:
    paragraph: int
    message: str
    content: str = ""


@dataclass
class ParseReport:
    questions: list[Question] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    answer_markers: int = 0

    @property
    def valid(self) -> bool:
        return self.answer_markers == len(self.questions) and not self.issues

    def summary(self) -> dict:
        counts = {"single_choice": 0, "multiple_choice": 0, "true_false": 0}
        for item in self.questions:
            counts[item.question_type] += 1
        return {
            "question_count": len(self.questions),
            "answer_markers": self.answer_markers,
            "issue_count": len(self.issues),
            "type_counts": counts,
            "valid": self.valid,
        }


def detect_question_type(text: str) -> str | None:
    value = re.sub(r"^\s*\d+\s*[、.]\s*", "", clean_text(text))
    match = re.fullmatch(
        r"(单项选择题|多项选择题|判断题)(?:[（(][^）)]{0,40}[）)])?", value
    )
    return TYPE_LABELS.get(match.group(1)) if match else None


def _section_from_pending(pending: list[tuple[int, str, str]]) -> str:
    headings = [text for _, style, text in pending if "Heading" in style]
    if not headings:
        headings = [text for _, _, text in pending]
    return " / ".join(headings[-3:])


def _build_question(
    question_id: int,
    question_type: str,
    block: list[tuple[int, str, str]],
    answer: str,
    section: str,
    source_file: str,
) -> tuple[Question | None, str | None]:
    if not block:
        return None, "答案前没有题干"

    if question_type == "true_false":
        question_text = " ".join(text for _, _, text in block)
        options: dict[str, str] = {}
        if answer not in {"正确", "错误"}:
            return None, f"判断题答案格式错误: {answer}"
    else:
        heading2_positions = [
            index for index, (_, style, _) in enumerate(block) if style == "Heading 2"
        ]
        if heading2_positions and heading2_positions[0] > 0:
            split_at = heading2_positions[0]
            question_text = " ".join(text for _, _, text in block[:split_at])
            option_values = [text for _, _, text in block[split_at:]]
        else:
            question_text = block[0][2]
            option_values = [text for _, _, text in block[1:]]

        if not option_values:
            return None, "选择题没有选项"
        if len(option_values) > 8:
            return None, f"选择题选项过多: {len(option_values)}"
        options = {
            chr(ord("A") + index): value for index, value in enumerate(option_values)
        }
        if not re.fullmatch(r"[A-D]{1,4}", answer):
            return None, f"选择题答案格式错误: {answer}"
        missing = [letter for letter in answer if letter not in options]
        if missing:
            return None, f"答案引用了不存在的选项: {''.join(missing)}"

    normalized = normalize_question(question_text)
    if len(normalized) < 4:
        return None, "题干过短"

    return (
        Question(
            id=question_id,
            question_type=question_type,
            question=clean_text(question_text),
            normalized_question=normalized,
            options=options,
            answer=answer,
            section=section or "未分类",
            source_file=source_file,
            source_paragraph_start=block[0][0],
            source_paragraph_end=block[-1][0],
        ),
        None,
    )


def parse_docx(path: str | Path, *, expected_count: int | None = 4180) -> ParseReport:
    source = Path(path).resolve()
    document = Document(source)
    paragraphs = [
        (index, paragraph.style.name, clean_text(paragraph.text))
        for index, paragraph in enumerate(document.paragraphs)
        if clean_text(paragraph.text)
    ]

    report = ParseReport()
    current_type: str | None = None
    current_section = ""
    block: list[tuple[int, str, str]] = []

    for paragraph_index, style, text in paragraphs:
        type_heading = detect_question_type(text)
        if type_heading:
            if block:
                candidate_section = _section_from_pending(block)
                if candidate_section:
                    current_section = candidate_section
            block = []
            current_type = type_heading
            continue

        answer_match = ANSWER_PATTERN.fullmatch(text)
        if answer_match:
            report.answer_markers += 1
            if current_type is None:
                report.issues.append(
                    ParseIssue(paragraph_index, "答案出现在题型标题之前", text)
                )
                block = []
                continue
            answer = answer_match.group(1)
            question, error = _build_question(
                len(report.questions) + 1,
                current_type,
                block,
                answer,
                current_section,
                source.name,
            )
            if error:
                report.issues.append(ParseIssue(paragraph_index, error, text))
            elif question:
                report.questions.append(question)
            block = []
            continue

        block.append((paragraph_index, style, text))

    if expected_count is not None and len(report.questions) != expected_count:
        report.issues.append(
            ParseIssue(
                -1,
                f"题目总数不符合预期: {len(report.questions)} != {expected_count}",
            )
        )
    return report
