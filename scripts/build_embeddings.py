from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qabank.config import Settings
from qabank.database import QuestionDatabase
from qabank.normalization import searchable_text
from qabank.providers import ModelProvider


def main() -> int:
    parser = argparse.ArgumentParser(description="为题库构建可选语义向量索引")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    settings = Settings.from_env()
    provider = ModelProvider(settings)
    if not provider.configured:
        print("DASHSCOPE_API_KEY 未配置，无法构建语义索引。", file=sys.stderr)
        return 2

    database = QuestionDatabase(settings.database_path)
    questions = database.all_questions()
    if not questions:
        print("题库为空，请先运行 scripts/import_docx.py。", file=sys.stderr)
        return 2

    vectors: list[tuple[int, list[float]]] = []
    batch_size = max(1, min(args.batch_size, 20))
    for start in range(0, len(questions), batch_size):
        batch = questions[start : start + batch_size]
        texts = [searchable_text(item.question, item.options) for item in batch]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                embeddings = provider.embeddings(texts)
                if len(embeddings) != len(batch):
                    raise RuntimeError("Embedding 返回数量与请求不一致")
                vectors.extend(
                    (item.id, vector) for item, vector in zip(batch, embeddings, strict=True)
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                time.sleep(2**attempt)
        if last_error:
            print(f"第 {start + 1} 批构建失败：{last_error}", file=sys.stderr)
            return 1
        print(f"已生成 {len(vectors)}/{len(questions)} 条向量")

    database.replace_embeddings(settings.embedding_model, vectors)
    print(f"语义索引构建完成：{len(vectors)} 条，模型 {settings.embedding_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
