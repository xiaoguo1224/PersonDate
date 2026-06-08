from __future__ import annotations

import json
import logging
from typing import TypeVar

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        raw_base_url = base_url or settings.llm_base_url
        if raw_base_url and raw_base_url.rstrip("/").endswith("/anthropic"):
            raw_base_url = raw_base_url[: -len("/anthropic")].rstrip("/")
        self.base_url = raw_base_url
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or "gpt-4o-mini"
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat_json(self, *, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("LLM 返回的不是合法 JSON: %s", content[:500])
            raise ValueError("LLM 返回的不是合法 JSON") from exc
        try:
            return schema.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "schema=%s 校验失败, payload=%s, errors=%s",
                schema.__name__,
                json.dumps(payload, ensure_ascii=False, default=str)[:1000],
                str(exc)[:500],
            )
            raise ValueError("LLM 返回结构与期望 schema 不匹配") from exc

    def chat_with_tools(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
    ) -> ChatCompletionMessage:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
        )
        return response.choices[0].message
