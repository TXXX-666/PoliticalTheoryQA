from __future__ import annotations

from pathlib import Path

import pytest

from qabank.config import Settings


@pytest.fixture
def settings_factory(tmp_path: Path):
    def build(source_docx: Path, **overrides) -> Settings:
        values = {
            "runtime_dir": tmp_path / "runtime",
            "source_docx": source_docx,
            "database_path": tmp_path / "runtime" / "question_bank.db",
            "expected_count": 3,
            "api_key": "",
            "llm_base_url": "https://example.invalid/v1",
            "llm_model": "qwen3.8-flash",
            "embedding_model": "text-embedding-v4",
            "enable_semantic": False,
            "enable_llm_explanation": False,
            "access_token": "",
            "require_auth": False,
            "max_query_chars": 2000,
            "rate_limit_requests": 20,
            "rate_limit_window_seconds": 60,
            "auto_match_threshold": 0.90,
            "auto_match_margin": 0.04,
            "candidate_threshold": 0.55,
        }
        values.update(overrides)
        return Settings(**values)

    return build
