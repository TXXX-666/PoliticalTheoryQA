from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qabank.service import QuestionAnswerService


def main() -> int:
    service = QuestionAnswerService()
    questions = service.database.all_questions()
    exact_matches = 0
    consistent_duplicates = 0
    ambiguous_conflicts = 0
    failures: list[dict] = []
    started = time.perf_counter()

    grouped: dict[str, list] = {}
    for item in questions:
        grouped.setdefault(item.normalized_question, []).append(item)

    for normalized, items in grouped.items():
        result = service.retriever.search(items[0].question)
        variants = {(item.answer, tuple(item.options.items())) for item in items}
        if len(variants) > 1:
            if result.status == "ambiguous" and result.selected is None:
                ambiguous_conflicts += 1
            else:
                failures.append(
                    {"ids": [item.id for item in items], "expected": "ambiguous"}
                )
            continue
        if result.status != "matched" or result.selected is None:
            failures.append(
                {"ids": [item.id for item in items], "expected": "matched"}
            )
            continue
        if result.selected.question.answer != items[0].answer:
            failures.append(
                {"ids": [item.id for item in items], "expected_answer": items[0].answer}
            )
            continue
        if len(items) > 1:
            consistent_duplicates += 1
        exact_matches += 1

    summary = {
        "question_count": len(questions),
        "unique_normalized_questions": len(grouped),
        "exact_match_groups": exact_matches,
        "consistent_duplicate_groups": consistent_duplicates,
        "ambiguous_conflict_groups": ambiguous_conflicts,
        "failure_count": len(failures),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "failures": failures[:20],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures and len(questions) == 4180 else 1


if __name__ == "__main__":
    raise SystemExit(main())
