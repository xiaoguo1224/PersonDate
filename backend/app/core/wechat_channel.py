from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI

from app.core.config import get_settings
from app.schemas.wechat_channel import (
    WechatGetConfigResponse,
    WechatGetUpdatesResponse,
    WechatSendTextResponse,
    WechatSendTypingResponse,
)


@dataclass
class WechatChannelHttpClient:
    base_url: str
    channel_token: str | None = None
    timeout_seconds: float = 10.0
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def get_updates(
        self,
        *,
        bot_token: str,
        cursor: str | None = None,
    ) -> WechatGetUpdatesResponse:
        payload: dict[str, object] = {"bot_token": bot_token}
        if cursor is not None:
            payload["get_updates_buf"] = cursor
        return WechatGetUpdatesResponse.model_validate(
            self._request_json("/getupdates", payload)
        )

    def send_text(
        self,
        conversation_id: str,
        content: str,
        context_token: str | None = None,
    ) -> WechatSendTextResponse:
        payload: dict[str, object] = {
            "to_user_id": conversation_id,
            "conversation_id": conversation_id,
            "content": content,
        }
        if context_token is not None:
            payload["context_token"] = context_token
        response = self._client.post(
            "/sendmessage",
            json=payload,
            headers=self._headers(),
        )
        return WechatSendTextResponse.model_validate(self._response_json(response))

    def get_config(
        self,
        *,
        account_id: str | None = None,
        bot_token: str | None = None,
    ) -> WechatGetConfigResponse:
        payload: dict[str, object] = {}
        if account_id is not None:
            payload["account_id"] = account_id
        if bot_token is not None:
            payload["bot_token"] = bot_token
        return WechatGetConfigResponse.model_validate(
            self._request_json("/getconfig", payload)
        )

    def send_typing(
        self,
        *,
        conversation_id: str,
        typing: bool = True,
        account_id: str | None = None,
        bot_token: str | None = None,
        typing_ticket: str | None = None,
    ) -> WechatSendTypingResponse:
        payload: dict[str, object] = {
            "conversation_id": conversation_id,
            "typing": typing,
        }
        if account_id is not None:
            payload["account_id"] = account_id
        if bot_token is not None:
            payload["bot_token"] = bot_token
        if typing_ticket is not None:
            payload["typing_ticket"] = typing_ticket
        return WechatSendTypingResponse.model_validate(
            self._request_json("/sendtyping", payload)
        )

    def _headers(self) -> dict[str, str]:
        if not self.channel_token:
            return {}
        return {"X-Channel-Token": self.channel_token}

    def _request_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        response = self._client.post(path, json=payload, headers=self._headers())
        return self._response_json(response)

    def _response_json(self, response: httpx.Response) -> dict[str, object]:
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
            return payload["data"]
        if isinstance(payload, dict):
            return payload
        raise TypeError("微信通道响应必须是 JSON 对象")


def build_wechat_channel_client() -> WechatChannelHttpClient | None:
    settings = get_settings()
    if not settings.wechat_channel_base_url:
        return None
    return WechatChannelHttpClient(
        base_url=settings.wechat_channel_base_url,
        channel_token=settings.wechat_channel_token,
    )


def attach_wechat_channel_client(app: FastAPI) -> None:
    client = build_wechat_channel_client()
    app.state.wechat_sender = client
    app.state.wechat_updates_client = client


def require_wechat_channel_client(app: FastAPI) -> WechatChannelHttpClient:
    client = build_wechat_channel_client()
    if client is None:
        raise RuntimeError("WECHAT_CHANNEL_BASE_URL 未配置，无法初始化微信通道客户端")
    app.state.wechat_sender = client
    app.state.wechat_updates_client = client
    return client


def close_wechat_channel_client(app: FastAPI) -> None:
    client = getattr(app.state, "wechat_sender", None)
    if client is not None and hasattr(client, "close"):
        client.close()
    app.state.wechat_sender = None
    app.state.wechat_updates_client = None
