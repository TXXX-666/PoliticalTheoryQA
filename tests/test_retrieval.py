from pathlib import Path

from qabank.database import QuestionDatabase
from qabank.models import Question
from qabank.normalization import normalize_question
from qabank.retrieval import QuestionRetriever


def make_question(question_id: int, text: str, answer: str = "A") -> Question:
    return Question(
        id=question_id,
        question_type="single_choice",
        question=text,
        normalized_question=normalize_question(text),
        options={"A": "正确项", "B": "干扰项", "C": "其他项"},
        answer=answer,
        section="测试章节",
        source_file="fixture.docx",
        source_paragraph_start=question_id,
        source_paragraph_end=question_id + 3,
    )


def test_exact_match_ignores_number_spacing_and_punctuation(tmp_path: Path, settings_factory):
    source = tmp_path / "unused.docx"
    settings = settings_factory(source)
    database = QuestionDatabase(settings.database_path)
    database.replace_questions(
        [make_question(1, "习近平新时代中国特色社会主义思想的核心要义是（   ）。", "C")]
    )
    retriever = QuestionRetriever(database, settings)

    result = retriever.search("1、习近平新时代中国特色社会主义思想的核心要义是()? ")
    assert result.status == "matched"
    assert result.selected.question.answer == "C"
    assert result.selected.match_method == "exact"


def test_exact_match_accepts_question_with_inline_options(tmp_path: Path, settings_factory):
    settings = settings_factory(tmp_path / "unused.docx")
    database = QuestionDatabase(settings.database_path)
    database.replace_questions([make_question(1, "核心要义是（ ）。", "C")])
    retriever = QuestionRetriever(database, settings)

    result = retriever.search("核心要义是（ ）。 A. 选项甲 B. 选项乙 C. 正确项")
    assert result.status == "matched"
    assert result.selected.question.answer == "C"


def test_minor_typo_uses_lexical_match(tmp_path: Path, settings_factory):
    settings = settings_factory(tmp_path / "unused.docx")
    database = QuestionDatabase(settings.database_path)
    database.replace_questions(
        [
            make_question(1, "中国特色社会主义最本质的特征是什么？", "A"),
            make_question(2, "我国经济发展的基本特征是什么？", "B"),
        ]
    )
    retriever = QuestionRetriever(database, settings)

    result = retriever.search("中国特色社会主义最本质特征是什么")
    assert result.status == "matched"
    assert result.selected.question.id == 1


def test_conflicting_duplicate_never_auto_answers(tmp_path: Path, settings_factory):
    settings = settings_factory(tmp_path / "unused.docx")
    database = QuestionDatabase(settings.database_path)
    database.replace_questions(
        [
            make_question(1, "重复题干（ ）。", "A"),
            make_question(2, "重复题干（ ）。", "B"),
        ]
    )
    retriever = QuestionRetriever(database, settings)

    result = retriever.search("重复题干")
    assert result.status == "ambiguous"
    assert result.selected is None
    assert len(result.candidates) == 2


def test_unrelated_short_query_is_rejected(tmp_path: Path, settings_factory):
    settings = settings_factory(tmp_path / "unused.docx")
    database = QuestionDatabase(settings.database_path)
    database.replace_questions([make_question(1, "完整的政治理论题目是什么？")])
    retriever = QuestionRetriever(database, settings)

    result = retriever.search("政治")
    assert result.status == "no_match"
