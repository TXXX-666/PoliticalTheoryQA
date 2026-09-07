from __future__ import annotations

from typing import Any

from .config import Settings
from .database import QuestionDatabase
from .models import SearchHit, SearchResult
from .parser import parse_docx
from .providers import ModelProvider
from .retrieval import QuestionRetriever


TYPE_LABELS = {
    "single_choice": "单项选择题",
    "multiple_choice": "多项选择题",
    "true_false": "判断题",
}


class QuestionAnswerService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.database = QuestionDatabase(self.settings.database_path)
        self.provider = ModelProvider(self.settings)
        self._ensure_database()
        self.retriever = QuestionRetriever(
            self.database, self.settings, provider=self.provider
        )

    def _ensure_database(self) -> None:
        if self.database.count() > 0:
            return
        if not self.settings.source_docx.exists():
            raise FileNotFoundError(
                f"题库尚未导入，请将 DOCX 放到 {self.settings.source_docx} 后运行导入脚本。"
            )
        report = parse_docx(
            self.settings.source_docx, expected_count=self.settings.expected_count
        )
        if not report.valid:
            details = "; ".join(item.message for item in report.issues[:8])
            raise ValueError(f"题库解析校验失败：{details}")
        self.database.replace_questions(report.questions)

    @staticmethod
    def answer_payload(hit: SearchHit) -> dict[str, Any]:
        item = hit.question
        return {
            "question_id": item.id,
            "question_type": item.question_type,
            "question_type_label": TYPE_LABELS[item.question_type],
            "question": item.question,
            "options": item.options,
            "answer": item.answer,
            "answer_options": [
                {"letter": letter, "text": text}
                for letter, text in item.answer_options()
            ],
            "section": item.section,
            "source_file": item.source_file,
            "match_method": hit.match_method,
            "score": hit.score,
            "lexical_score": hit.lexical_score,
            "semantic_score": hit.semantic_score,
        }

    def ask(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        result = self.retriever.search(query, limit=limit)
        return self._result_payload(result)

    def answer_question_id(self, question_id: int) -> dict[str, Any] | None:
        item = self.database.question(question_id)
        if item is None:
            return None
        return self.answer_payload(SearchHit(item, 1.0, "manual_selection", 1.0))

    def _result_payload(self, result: SearchResult) -> dict[str, Any]:
        payload = result.to_dict()
        payload["answer"] = (
            self.answer_payload(result.selected) if result.selected else None
        )
        return payload

    def explain(self, question_id: int) -> str:
        if not self.settings.enable_llm_explanation:
            raise RuntimeError("LLM 辅助说明未启用")
        item = self.database.question(question_id)
        if item is None:
            raise ValueError("题目不存在")
        return self.provider.explain(item)

    def stats(self) -> dict[str, Any]:
        return {
            "question_count": self.database.count(),
            "type_counts": self.database.type_counts(),
            "duplicates": self.database.duplicate_summary(),
            "fts_enabled": self.database.fts_enabled(),
            "embedding_count": self.database.embedding_count(),
            "semantic_enabled": self.settings.enable_semantic,
            "llm_configured": self.provider.configured,
            "llm_explanation_enabled": self.settings.enable_llm_explanation,
        }
