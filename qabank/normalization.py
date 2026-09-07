from __future__ import annotations

import re
import unicodedata


OPTION_PREFIX = re.compile(r"^\s*[A-DＡ-Ｄ][\.、:：\)）]\s*")
INLINE_OPTION_PREFIX = re.compile(r"\s+[A-DＡ-Ｄ][\.、:：\)）]\s+")
LEADING_NUMBER = re.compile(r"^\s*(?:第\s*)?\d+\s*(?:题|[\.、:：\)）])\s*")


def clean_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("\u00a0", " ").replace("\u3000", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def question_part(text: str) -> str:
    """Remove pasted options/answers while preserving a multiline question."""
    lines = [clean_text(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    question_lines: list[str] = []
    for line in lines:
        if OPTION_PREFIX.match(line) or re.match(r"^【?答案】?[:：]", line):
            break
        question_lines.append(line)
    value = " ".join(question_lines or lines[:1])
    inline_option = INLINE_OPTION_PREFIX.search(value)
    if inline_option and inline_option.start() >= 4:
        value = value[: inline_option.start()]
    return value


def normalize_question(text: str) -> str:
    value = question_part(text)
    value = LEADING_NUMBER.sub("", value)
    value = value.lower()
    value = re.sub(r"[\s\u200b]+", "", value)
    value = re.sub(r"[（(]\s*[）)]", "()", value)
    value = re.sub(r"[，。！？；：、,.!?;:\"'“”‘’《》〈〉【】\[\]{}]", "", value)
    return value.strip()


def searchable_text(question: str, options: dict[str, str]) -> str:
    option_text = " ".join(f"{key} {value}" for key, value in options.items())
    return clean_text(f"{question} {option_text}")
