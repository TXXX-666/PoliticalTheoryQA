from pathlib import Path

from qabank.parser import parse_docx
from qabank.service import QuestionAnswerService
from tests.test_parser import build_fixture


def test_service_returns_database_answer_without_api_key(tmp_path: Path, settings_factory):
    source = tmp_path / "fixture.docx"
    build_fixture(source)
    settings = settings_factory(source)
    service = QuestionAnswerService(settings)

    result = service.ask("核心要义是（）。")
    assert result["status"] == "matched"
    assert result["answer"]["answer"] == "C"
    assert result["answer"]["answer_options"] == [
        {"letter": "C", "text": "选项丙"}
    ]
    assert service.stats()["llm_configured"] is False


def test_fixture_is_structurally_valid(tmp_path: Path):
    source = tmp_path / "fixture.docx"
    build_fixture(source)
    assert parse_docx(source, expected_count=3).valid
