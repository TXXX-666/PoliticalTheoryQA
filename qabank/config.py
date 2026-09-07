from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    runtime_dir: Path
    source_docx: Path
    database_path: Path
    expected_count: int
    api_key: str
    llm_base_url: str
    llm_model: str
    embedding_model: str
    enable_semantic: bool
    enable_llm_explanation: bool
    access_token: str
    require_auth: bool
    max_query_chars: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    auto_match_threshold: float
    auto_match_margin: float
    candidate_threshold: float

    @classmethod
    def from_env(cls) -> "Settings":
        runtime_dir = Path(
            os.getenv("QABANK_RUNTIME_DIR", str(PROJECT_ROOT / "runtime"))
        ).expanduser().resolve()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        source_docx = Path(
            os.getenv(
                "QABANK_SOURCE_DOCX", str(PROJECT_ROOT / "source" / "question_bank.docx")
            )
        ).expanduser().resolve()
        return cls(
            runtime_dir=runtime_dir,
            source_docx=source_docx,
            database_path=runtime_dir / "question_bank.db",
            expected_count=max(1, int(os.getenv("QABANK_EXPECTED_COUNT", "4180"))),
            api_key=os.getenv("DASHSCOPE_API_KEY", "").strip(),
            llm_base_url=os.getenv(
                "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ).strip(),
            llm_model=os.getenv("LLM_MODEL", "qwen3.8-flash").strip(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4").strip(),
            enable_semantic=_flag("QABANK_ENABLE_SEMANTIC"),
            enable_llm_explanation=_flag("QABANK_ENABLE_LLM_EXPLANATION"),
            access_token=os.getenv("QABANK_ACCESS_TOKEN", "").strip(),
            require_auth=_flag("QABANK_REQUIRE_AUTH"),
            max_query_chars=max(100, int(os.getenv("QABANK_MAX_QUERY_CHARS", "2000"))),
            rate_limit_requests=max(
                1, int(os.getenv("QABANK_RATE_LIMIT_REQUESTS", "20"))
            ),
            rate_limit_window_seconds=max(
                10, int(os.getenv("QABANK_RATE_LIMIT_WINDOW_SECONDS", "60"))
            ),
            auto_match_threshold=float(
                os.getenv("QABANK_AUTO_MATCH_THRESHOLD", "0.90")
            ),
            auto_match_margin=float(os.getenv("QABANK_AUTO_MATCH_MARGIN", "0.04")),
            candidate_threshold=float(
                os.getenv("QABANK_CANDIDATE_THRESHOLD", "0.55")
            ),
        )
