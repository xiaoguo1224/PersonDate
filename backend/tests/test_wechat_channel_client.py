from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from app.core import wechat_channel as wechat_channel_module
from app.core.wechat_channel import WechatChannelHttpClient


def test_wechat_channel_http_client_posts_sendmessage_and_getupdates() -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        requests.append((request.url.path, request.headers.get("X-Channel-Token", ""), payload))
        if request.url.path == "/sendmessage":
            return httpx.Response(200, json={"success": True, "message_id": "wx_out_001"})
        if request.url.path == "/getconfig":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "account_id": "wx_account_001",
                    "status": "active",
                    "cursor": "cursor_1",
                    "typing_ticket": "ticket_001",
                },
            )
        if request.url.path == "/getuploadurl":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "ret": 0,
                    "upload_param": "upload_param_001",
                    "thumb_upload_param": "thumb_upload_param_001",
                },
            )
        if request.url.path == "/sendtyping":
            return httpx.Response(200, json={"success": True, "typing": True})
        return httpx.Response(200, json={"msgs": [], "get_updates_buf": "cursor_1"})

    transport = httpx.MockTransport(handler)
    client = WechatChannelHttpClient(
        base_url="https://wechat.example.com",
        channel_token="token_001",
    )
    client._client = httpx.Client(transport=transport, base_url="https://wechat.example.com")

    send_result = client.send_text("wx_user_001", "提醒：15:00 开会", context_token="ctx_001")
    updates_result = client.get_updates(bot_token="bot_001", cursor="cursor_0")
    config_result = client.get_config(bot_token="bot_001")
    upload_result = client.get_upload_url(
        filekey="file_001",
        media_type=3,
        to_user_id="wx_user_001",
        rawsize=12345,
        rawfilemd5="0123456789abcdef0123456789abcdef",
        filesize=12352,
    )
    typing_result = client.send_typing(
        conversation_id="wx_user_001",
        typing=True,
        bot_token="bot_001",
        typing_ticket="ticket_001",
    )

    assert send_result.message_id == "wx_out_001"
    assert updates_result.next_cursor == "cursor_1"
    assert updates_result.messages == []
    assert config_result.typing_ticket == "ticket_001"
    assert upload_result.upload_param == "upload_param_001"
    assert typing_result.typing is True
    assert requests[0][0] == "/sendmessage"
    assert requests[0][1] == "token_001"
    assert requests[0][2]["to_user_id"] == "wx_user_001"
    assert requests[0][2]["context_token"] == "ctx_001"
    assert requests[1][0] == "/getupdates"
    assert requests[1][1] == "token_001"
    assert requests[1][2]["bot_token"] == "bot_001"
    assert requests[1][2]["get_updates_buf"] == "cursor_0"
    assert requests[2][0] == "/getconfig"
    assert requests[2][2]["bot_token"] == "bot_001"
    assert requests[3][0] == "/getuploadurl"
    assert requests[3][2]["filekey"] == "file_001"
    assert requests[4][0] == "/sendtyping"
    assert requests[4][2]["typing_ticket"] == "ticket_001"


def test_require_wechat_channel_client_raises_without_base_url(monkeypatch) -> None:
    monkeypatch.setattr(
        wechat_channel_module,
        "build_wechat_channel_client",
        lambda: None,
    )

    app = SimpleNamespace(state=SimpleNamespace())

    try:
        wechat_channel_module.require_wechat_channel_client(app)  # type: ignore[arg-type]
    except RuntimeError as exc:
        assert "WECHAT_CHANNEL_BASE_URL" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
