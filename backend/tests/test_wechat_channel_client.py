from __future__ import annotations

import json

import httpx

from app.core.wechat_channel import WechatChannelHttpClient


def test_wechat_channel_http_client_posts_sendmessage_and_getupdates() -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        requests.append((request.url.path, request.headers.get("X-Channel-Token", ""), payload))
        if request.url.path == "/sendmessage":
            return httpx.Response(200, json={"success": True, "message_id": "wx_out_001"})
        return httpx.Response(200, json={"msgs": [], "get_updates_buf": "cursor_1"})

    transport = httpx.MockTransport(handler)
    client = WechatChannelHttpClient(
        base_url="https://wechat.example.com",
        channel_token="token_001",
    )
    client._client = httpx.Client(transport=transport, base_url="https://wechat.example.com")

    send_result = client.send_text("wx_user_001", "提醒：15:00 开会", context_token="ctx_001")
    updates_result = client.get_updates(bot_token="bot_001", cursor="cursor_0")

    assert send_result["message_id"] == "wx_out_001"
    assert updates_result["get_updates_buf"] == "cursor_1"
    assert requests[0][0] == "/sendmessage"
    assert requests[0][1] == "token_001"
    assert requests[0][2]["to_user_id"] == "wx_user_001"
    assert requests[0][2]["context_token"] == "ctx_001"
    assert requests[1][0] == "/getupdates"
    assert requests[1][1] == "token_001"
    assert requests[1][2]["bot_token"] == "bot_001"
    assert requests[1][2]["get_updates_buf"] == "cursor_0"
