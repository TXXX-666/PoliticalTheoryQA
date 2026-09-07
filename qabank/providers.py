from __future__ import annotations

from openai import OpenAI

from .config import Settings
from .models import Question


class ModelProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = (
            OpenAI(api_key=settings.api_key, base_url=settings.llm_base_url)
            if settings.api_key
            else None
        )

    @property
    def configured(self) -> bool:
        return self.client is not None

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        if self.client is None:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")
        response = self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=texts,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]

    def explain(self, item: Question) -> str:
        if self.client is None:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")
        options = "\n".join(f"{key}. {value}" for key, value in item.options.items())
        completion = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是政治理论题库学习助手。标准答案由题库提供，绝对不能修改。"
                        "只解释题干与标准答案之间的关系；如果依据不足，明确说明这是辅助理解，"
                        "不得伪造政策原文、文件条款、出处或日期。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"题型：{item.question_type}\n题目：{item.question}\n"
                        f"选项：\n{options or '无'}\n题库标准答案：{item.answer}\n\n"
                        "请用不超过150字解释答案。开头必须写：辅助说明："
                    ),
                },
            ],
            temperature=0.1,
        )
        return (completion.choices[0].message.content or "").strip()
