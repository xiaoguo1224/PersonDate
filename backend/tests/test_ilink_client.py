# backend/tests/test_ilink_client.py
from __future__ import annotations

import base64
import json

import pytest
import respx
from httpx import Response

from wechat_channel.ilink_client import ILinkClient, ILinkError, QRResult, QRStatus, UpdatesResult


@pytest.fixture
def client():
    return ILinkClient()


@pytest.fixture
def mock_ilink():
    with respx.mock(base_url="https://ilinkai.weixin.qq.com") as respx_mock:
        yield respx_mock


class TestGetQrCode:
    def test_returns_qr_result(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/get_bot_qrcode?bot_type=3").respond(
            json={"qrcode": "qr_bot_abc123", "qrcode_img_content": "base64imagedata"}
        )
        result = client.get_qr_code()
        assert isinstance(result, QRResult)
        assert result.qrcode_id == "qr_bot_abc123"
        assert result.qr_img_content == "base64imagedata"

    def test_sends_random_uin_header(self, client, mock_ilink):
        def check_headers(request):
            uin = request.headers.get("X-WECHAT-UIN")
            assert uin is not None and len(uin) > 0
            decoded = base64.b64decode(uin + "=" * (4 - len(uin) % 4))
            assert len(decoded) == 4
            return Response(200, json={"qrcode": "test", "qrcode_img_content": ""})

        mock_ilink.post("/ilink/bot/get_bot_qrcode?bot_type=3").mock(side_effect=check_headers)
        client.get_qr_code()

    def test_raises_on_http_error(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/get_bot_qrcode?bot_type=3").respond(status_code=500)
        with pytest.raises(ILinkError):
            client.get_qr_code()


class TestPollQrStatus:
    def test_returns_scanned(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/get_qrcode_status?qrcode=qr_1").respond(
            json={"status": "scanned"}
        )
        result = client.poll_qr_status("qr_1")
        assert result.state == "scanned"
        assert result.token is None

    def test_returns_confirmed(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/get_qrcode_status?qrcode=qr_1").respond(
            json={"status": "confirmed", "bot_token": "bt_xxx", "baseurl": "https://ilink.example.com"}
        )
        result = client.poll_qr_status("qr_1")
        assert result.state == "confirmed"
        assert result.token == "bt_xxx"
        assert result.base_url == "https://ilink.example.com"

    def test_returns_expired(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/get_qrcode_status?qrcode=qr_1").respond(
            json={"status": "expired"}
        )
        result = client.poll_qr_status("qr_1")
        assert result.state == "expired"


class TestGetUpdates:
    def test_returns_messages(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/getupdates").respond(
            json={
                "get_updates_buf": "buf_next",
                "msgs": [
                    {
                        "from_user_id": "wx_user_1",
                        "context_token": "ctx_1",
                        "message_type": 1,
                        "item_list": [{"type": 1, "text_item": {"text": "你好"}}],
                    }
                ],
            }
        )
        result = client.get_updates(bot_token="bt_1", cursor="buf_prev")
        assert isinstance(result, UpdatesResult)
        assert len(result.msgs) == 1
        assert result.msgs[0]["from_user_id"] == "wx_user_1"
        assert result.msgs[0]["item_list"][0]["text_item"]["text"] == "你好"
        assert result.new_cursor == "buf_next"

    def test_sends_past_cursor(self, client, mock_ilink):
        def check_payload(request):
            body = json.loads(request.content)
            assert body["get_updates_buf"] == "buf_prev"
            return Response(200, json={"get_updates_buf": "buf_next", "msgs": []})

        mock_ilink.post("/ilink/bot/getupdates").mock(side_effect=check_payload)
        client.get_updates(bot_token="bt_1", cursor="buf_prev")

    def test_empty_response(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/getupdates").respond(
            json={"get_updates_buf": "buf_same", "msgs": []}
        )
        result = client.get_updates(bot_token="bt_1", cursor="buf_same")
        assert result.msgs == []
        assert result.new_cursor == "buf_same"


class TestSendMessage:
    def test_sends_message_successfully(self, client, mock_ilink):
        def check_payload(request):
            body = json.loads(request.content)
            msg = body["msg"]
            assert msg["to_user_id"] == "wx_user_1@im.wechat"
            assert msg["message_type"] == 2
            assert msg["item_list"][0]["text_item"]["text"] == "回复内容"
            assert msg["context_token"] == "ctx_1"
            assert "base_info" in body
            return Response(200, json={"ret": 0})

        mock_ilink.post("/ilink/bot/sendmessage").mock(side_effect=check_payload)
        result = client.send_message(
            bot_token="bt_1", to_user_id="wx_user_1",
            text="回复内容", context_token="ctx_1"
        )
        assert result is True

    def test_fails_on_error_ret(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/sendmessage").respond(
            json={"ret": -1, "err_msg": "send failed"}
        )
        result = client.send_message(
            bot_token="bt_1", to_user_id="wx_user_1",
            text="hi", context_token="ctx_1"
        )
        assert result is False


class TestGetTypingTicket:
    def test_returns_ticket(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/getconfig").respond(
            json={"typing_ticket": "ticket_abc"}
        )
        ticket = client.get_typing_ticket(
            bot_token="bt_1", user_id="wx_user_1", context_token="ctx_1"
        )
        assert ticket == "ticket_abc"

    def test_returns_none_on_failure(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/getconfig").respond(status_code=500)
        ticket = client.get_typing_ticket(
            bot_token="bt_1", user_id="wx_user_1", context_token="ctx_1"
        )
        assert ticket is None


class TestSendTyping:
    def test_sends_typing_status_1(self, client, mock_ilink):
        def check_payload(request):
            body = json.loads(request.content)
            assert body["status"] == 1
            assert body["typing_ticket"] == "ticket_abc"
            return Response(200, json={"ret": 0})

        mock_ilink.post("/ilink/bot/sendtyping").mock(side_effect=check_payload)
        client.send_typing(
            bot_token="bt_1", user_id="wx_user_1",
            ticket="ticket_abc", status=1
        )

    def test_sends_typing_status_2(self, client, mock_ilink):
        mock_ilink.post("/ilink/bot/sendtyping").respond(json={"ret": 0})
        client.send_typing(
            bot_token="bt_1", user_id="wx_user_1",
            ticket="ticket_abc", status=2
        )
