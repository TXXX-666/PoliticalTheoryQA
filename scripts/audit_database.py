from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qabank.config import Settings
from qabank.database import QuestionDatabase


def main() -> int:
    settings = Settings.from_env()
    database = QuestionDatabase(settings.database_path)
    with database.connect() as connection:
        conflicts = connection.execute(
            """SELECT normalized_question, COUNT(*) AS record_count,
            GROUP_CONCAT(id) AS question_ids,
            GROUP_CONCAT(DISTINCT answer) AS answers
            FROM questions GROUP BY normalized_question
            HAVING COUNT(DISTINCT answer) > 1
            ORDER BY record_count DESC, normalized_question"""
        ).fetchall()
    report = {
        "question_count": database.count(),
        "type_counts": database.type_counts(),
        **database.duplicate_summary(),
        "fts_enabled": database.fts_enabled(),
        "conflicts": [dict(row) for row in conflicts],
    }
    output = settings.runtime_dir / "database_audit.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["question_count"] == 4180 else 1


if __name__ == "__main__":
    raise SystemExit(main())
