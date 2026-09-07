from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Question
from .normalization import searchable_text


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    question_type TEXT NOT NULL,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    options_json TEXT NOT NULL,
    answer TEXT NOT NULL,
    section TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_paragraph_start INTEGER NOT NULL,
    source_paragraph_end INTEGER NOT NULL,
    search_text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_normalized
ON questions(normalized_question);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

"""


class QuestionDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            try:
                connection.execute(
                    """CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts
                    USING fts5(question, search_text, section, content='questions',
                    content_rowid='id', tokenize='trigram')"""
                )
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key,value) VALUES('fts_enabled','1')"
                )
            except sqlite3.OperationalError:
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key,value) VALUES('fts_enabled','0')"
                )
            connection.commit()

    def replace_questions(self, questions: list[Question]) -> None:
        rows = [
            (
                item.id,
                item.question_type,
                item.question,
                item.normalized_question,
                json.dumps(item.options, ensure_ascii=False),
                item.answer,
                item.section,
                item.source_file,
                item.source_paragraph_start,
                item.source_paragraph_end,
                searchable_text(item.question, item.options),
            )
            for item in questions
        ]
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM questions")
            connection.executemany(
                """INSERT INTO questions(
                    id,question_type,question,normalized_question,options_json,answer,
                    section,source_file,source_paragraph_start,source_paragraph_end,search_text
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            if self.fts_enabled(connection):
                connection.execute(
                    "INSERT INTO questions_fts(questions_fts) VALUES('rebuild')"
                )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES('question_count',?)",
                (str(len(rows)),),
            )
            connection.commit()

    def fts_enabled(self, connection: sqlite3.Connection | None = None) -> bool:
        if connection is not None:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='fts_enabled'"
            ).fetchone()
            return bool(row and row[0] == "1")
        with self.connect() as own_connection:
            return self.fts_enabled(own_connection)

    @staticmethod
    def _row_to_question(row: sqlite3.Row) -> Question:
        return Question(
            id=int(row["id"]),
            question_type=row["question_type"],
            question=row["question"],
            normalized_question=row["normalized_question"],
            options=json.loads(row["options_json"]),
            answer=row["answer"],
            section=row["section"],
            source_file=row["source_file"],
            source_paragraph_start=int(row["source_paragraph_start"]),
            source_paragraph_end=int(row["source_paragraph_end"]),
        )

    def count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0])

    def all_questions(self) -> list[Question]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM questions ORDER BY id").fetchall()
        return [self._row_to_question(row) for row in rows]

    def question(self, question_id: int) -> Question | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM questions WHERE id=?", (question_id,)
            ).fetchone()
        return self._row_to_question(row) if row else None

    def exact(self, normalized_question: str) -> list[Question]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM questions WHERE normalized_question=? ORDER BY id",
                (normalized_question,),
            ).fetchall()
        return [self._row_to_question(row) for row in rows]

    def fts_candidates(self, query: str, limit: int = 80) -> list[Question]:
        if len(query) < 3 or not self.fts_enabled():
            return []
        terms = []
        compact = query.replace('"', "")
        for start in (0, max(0, len(compact) // 2 - 5), max(0, len(compact) - 10)):
            term = compact[start : start + 10]
            if len(term) >= 3 and term not in terms:
                terms.append(term)
        if not terms:
            return []
        expression = " OR ".join(f'"{term}"' for term in terms)
        try:
            with self.connect() as connection:
                rows = connection.execute(
                    """SELECT q.* FROM questions_fts f
                    JOIN questions q ON q.id=f.rowid
                    WHERE questions_fts MATCH ? ORDER BY bm25(questions_fts) LIMIT ?""",
                    (expression, limit),
                ).fetchall()
            return [self._row_to_question(row) for row in rows]
        except sqlite3.OperationalError:
            return []

    def type_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT question_type,COUNT(*) AS count FROM questions GROUP BY question_type"
            ).fetchall()
        return {row["question_type"]: int(row["count"]) for row in rows}

    def duplicate_summary(self) -> dict[str, int]:
        with self.connect() as connection:
            duplicate_groups = connection.execute(
                """SELECT COUNT(*) FROM (
                    SELECT normalized_question FROM questions
                    GROUP BY normalized_question HAVING COUNT(*) > 1
                )"""
            ).fetchone()[0]
            conflicting_groups = connection.execute(
                """SELECT COUNT(*) FROM (
                    SELECT normalized_question FROM questions
                    GROUP BY normalized_question HAVING COUNT(DISTINCT answer) > 1
                )"""
            ).fetchone()[0]
            ambiguous_record_groups = connection.execute(
                """SELECT COUNT(*) FROM (
                    SELECT normalized_question FROM questions
                    GROUP BY normalized_question
                    HAVING COUNT(DISTINCT answer || '|' || options_json) > 1
                )"""
            ).fetchone()[0]
        return {
            "duplicate_groups": int(duplicate_groups),
            "conflicting_answer_groups": int(conflicting_groups),
            "ambiguous_record_groups": int(ambiguous_record_groups),
        }
