from __future__ import annotations

from collections import defaultdict

from rapidfuzz import fuzz, process

from .config import Settings
from .database import QuestionDatabase
from .models import Question, SearchHit, SearchResult
from .normalization import normalize_question


class QuestionRetriever:
    def __init__(
        self,
        database: QuestionDatabase,
        settings: Settings,
    ):
        self.database = database
        self.settings = settings
        self._questions: list[Question] = []
        self._by_id: dict[int, Question] = {}
        self._choices: dict[int, str] = {}
        self.refresh()

    def refresh(self) -> None:
        self._questions = self.database.all_questions()
        self._by_id = {item.id: item for item in self._questions}
        self._choices = {item.id: item.normalized_question for item in self._questions}

    def _lexical_hits(self, normalized: str, limit: int) -> list[SearchHit]:
        scores: dict[int, float] = defaultdict(float)
        fts_items = self.database.fts_candidates(normalized, limit=max(40, limit * 8))
        for rank, item in enumerate(fts_items, 1):
            scores[item.id] = max(scores[item.id], 0.55 + 0.15 / rank)

        matches = process.extract(
            normalized,
            self._choices,
            scorer=fuzz.WRatio,
            limit=max(40, limit * 8),
            score_cutoff=self.settings.candidate_threshold * 100,
        )
        for _, score, question_id in matches:
            scores[int(question_id)] = max(scores[int(question_id)], float(score) / 100)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [
            SearchHit(
                question=self._by_id[question_id],
                score=score,
                lexical_score=score,
                match_method="lexical",
            )
            for question_id, score in ranked[:limit]
        ]

    def search(self, query: str, *, limit: int = 5) -> SearchResult:
        normalized = normalize_question(query)
        if len(normalized) < 4:
            return SearchResult(
                status="no_match",
                query=query,
                normalized_query=normalized,
                reason="题目内容过短，请粘贴完整题干。",
            )

        exact = self.database.exact(normalized)
        if exact:
            hits = [SearchHit(item, 1.0, "exact", lexical_score=1.0) for item in exact]
            answers = {(item.answer, tuple(item.options.items())) for item in exact}
            if len(answers) == 1:
                return SearchResult(
                    status="matched",
                    query=query,
                    normalized_query=normalized,
                    selected=hits[0],
                    candidates=hits,
                    reason="原题精确匹配。" if len(hits) == 1 else "原题存在重复记录，答案一致。",
                )
            return SearchResult(
                status="ambiguous",
                query=query,
                normalized_query=normalized,
                candidates=hits[:limit],
                reason="题库中存在相同题干但答案不同的记录，请核对章节。",
            )

        lexical = self._lexical_hits(normalized, max(limit, 8))
        by_id = {hit.question.id: hit for hit in lexical}
        candidates = sorted(by_id.values(), key=lambda item: item.score, reverse=True)[:limit]
        if not candidates:
            return SearchResult(
                status="no_match",
                query=query,
                normalized_query=normalized,
                reason="未找到足够相似的题目。",
            )

        top = candidates[0]
        runner_up = candidates[1].score if len(candidates) > 1 else 0.0
        margin = top.score - runner_up
        if (
            top.score >= self.settings.auto_match_threshold
            and margin >= self.settings.auto_match_margin
        ):
            return SearchResult(
                status="matched",
                query=query,
                normalized_query=normalized,
                selected=top,
                candidates=candidates,
                reason=f"高置信{top.match_method}匹配。",
            )
        return SearchResult(
            status="ambiguous",
            query=query,
            normalized_query=normalized,
            candidates=candidates,
            reason="存在多个相似题目，系统不会自动猜测，请选择原题。",
        )
