from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI

from app.core.config import get_settings
from app.schemas.wechat_channel import WechatGetUpdatesResponse, WechatSendTextResponse


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
        response = self._client.post(
            "/getupdates",
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        return WechatGetUpdatesResponse.model_validate(response.json())

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
        response.raise_for_status()
        return WechatSendTextResponse.model_validate(response.json())

    def _headers(self) -> dict[str, str]:
        if not self.channel_token:
            return {}
        return {"X-Channel-Token": self.channel_token}


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
        raise RuntimeError("WECHAT_CHANNEL_BASE_URL 未配置，无法启动独立微信通道服务")
    app.state.wechat_sender = client
    app.state.wechat_updates_client = client
    return client


def close_wechat_channel_client(app: FastAPI) -> None:
    client = getattr(app.state, "wechat_sender", None)
    if client is not None and hasattr(client, "close"):
        client.close()
    app.state.wechat_sender = None
    app.state.wechat_updates_client = None
