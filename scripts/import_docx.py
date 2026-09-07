from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qabank.config import Settings
from qabank.database import QuestionDatabase
from qabank.parser import parse_docx


def main() -> int:
    parser = argparse.ArgumentParser(description="导入政治理论 DOCX 题库")
    parser.add_argument("--source", type=Path, help="题库 DOCX 路径")
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--if-empty", action="store_true", help="数据库已有题目时跳过")
    parser.add_argument("--report", type=Path, help="解析报告 JSON 输出路径")
    args = parser.parse_args()

    settings = Settings.from_env()
    database = QuestionDatabase(settings.database_path)
    if args.if_empty and database.count() > 0:
        print(f"题库已有 {database.count()} 道题，跳过导入。")
        return 0

    source = (args.source or settings.source_docx).expanduser().resolve()
    if not source.exists():
        print(f"题库文件不存在：{source}", file=sys.stderr)
        return 2

    report = parse_docx(
        source, expected_count=args.expected_count or settings.expected_count
    )
    summary = report.summary()
    summary["source"] = str(source)
    summary["issues"] = [issue.__dict__ for issue in report.issues]
    report_path = args.report or settings.runtime_dir / "import_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not report.valid:
        print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    database.replace_questions(report.questions)
    print(json.dumps({**summary, **database.duplicate_summary()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
