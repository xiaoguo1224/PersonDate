# backend/wechat_channel/ilink_client.py
from __future__ import annotations

import base64
import logging
import secrets
import struct
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)
ILINK_API_BASE = "https://ilinkai.weixin.qq.com"


@dataclass
class QRResult:
    qrcode_id: str
    qr_img_content: str  # base64 编码的二维码图片


@dataclass
class QRStatus:
    state: str  # scanned / confirmed / expired / need_verifycode
    token: str | None = None
    base_url: str | None = None


@dataclass
class SendResult:
    success: bool
    ret: int = 0
    err_msg: str = ""


@dataclass
class UpdatesResult:
    msgs: list[dict[str, Any]]
    new_cursor: str


class ILinkError(Exception):
    """iLink 协议级错误"""

    def __init__(self, code: int, message: str = "") -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ILinkSessionExpired(ILinkError):
    """Session 过期（errcode: -14），需要重新扫码"""

    pass


@dataclass
class ILinkClient:
    """iLink 协议客户端，与 ilinkai.weixin.qq.com 通信。"""

    api_base: str = ILINK_API_BASE
    _http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
    )

    BASE_HEADERS: dict[str, str] = field(
        default_factory=lambda: {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": str((2 << 16) | (4 << 8) | 3),
        }
    )

    _typing_ticket_cache: dict[str, dict[str, str]] = field(default_factory=dict)

    def get_qr_code(self) -> QRResult:
        data = self._post("/ilink/bot/get_bot_qrcode", params={"bot_type": "3"})
        try:
            qrcode_id = data["qrcode"]
            qr_img = data["qrcode_img_content"]
        except KeyError as exc:
            raise ILinkError(
                code=-1,
                message=f"获取二维码失败: 缺少字段 {exc}",
            ) from exc
        return QRResult(qrcode_id=qrcode_id, qr_img_content=qr_img)

    def poll_qr_status(self, qrcode_id: str) -> QRStatus:
        data = self._post("/ilink/bot/get_qrcode_status", params={"qrcode": qrcode_id})
        status = data.get("status", "unknown")
        if status == "confirmed":
            return QRStatus(
                state="confirmed",
                token=data.get("bot_token"),
                base_url=data.get("baseurl"),
            )
        return QRStatus(state=status)

    def get_updates(self, bot_token: str, cursor: str | None) -> UpdatesResult:
        payload: dict[str, object] = {}
        if cursor is not None:
            payload["get_updates_buf"] = cursor
        payload["base_info"] = self._base_info()
        data = self._post(
            "/ilink/bot/getupdates",
            json=payload,
            extra_headers=self._auth_header(bot_token),
        )
        msgs = data.get("msgs")
        if msgs is None:
            msgs = data.get("messages", [])
        new_cursor = data.get("get_updates_buf", cursor or "")
        return UpdatesResult(msgs=msgs, new_cursor=new_cursor)

    def send_message(
        self,
        bot_token: str,
        to_user_id: str,
        text: str,
        context_token: str | None = None,
    ) -> SendResult:
        client_id = f"openclaw-weixin-{secrets.token_hex(4)}"
        msg = {
            "msg": {
                "from_user_id": "",
                "to_user_id": (
                    to_user_id
                    if to_user_id.endswith("@im.wechat")
                    else f"{to_user_id}@im.wechat"
                ),
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            },
            "base_info": self._base_info(),
        }
        if context_token:
            msg["msg"]["context_token"] = context_token
        data = self._post(
            "/ilink/bot/sendmessage",
            json=msg,
            extra_headers=self._auth_header(bot_token),
        )
        # ret=0 成功, ret=-2 排队中（iLink 正常行为）, 其他值失败
        ret = data.get("ret", 0)
        err_msg = data.get("err_msg") or data.get("message") or ""
        if ret not in (0, -2):
            logger.warning(
                "iLink 发送消息失败: ret=%s, err_msg=%s, to_user_id=%s, content_preview=%s",
                ret, err_msg, to_user_id, text[:50],
            )
            return SendResult(success=False, ret=ret, err_msg=err_msg)
        return SendResult(success=True, ret=ret, err_msg="")

    def get_typing_ticket(
        self, bot_token: str, user_id: str, context_token: str,
    ) -> str | None:
        account_cache = self._typing_ticket_cache.get(bot_token)
        if account_cache and user_id in account_cache:
            return account_cache[user_id]

        payload = {
            "ilink_user_id": user_id,
            "context_token": context_token,
            "base_info": self._base_info(),
        }
        try:
            data = self._post(
                "/ilink/bot/getconfig",
                json=payload,
                extra_headers=self._auth_header(bot_token),
            )
        except ILinkError:
            return None

        ticket = data.get("typing_ticket")
        if not ticket:
            return None

        if bot_token not in self._typing_ticket_cache:
            self._typing_ticket_cache[bot_token] = {}
        self._typing_ticket_cache[bot_token][user_id] = ticket
        return ticket

    def send_typing(self, bot_token: str, user_id: str, ticket: str, status: int = 1) -> None:
        payload = {
            "ilink_user_id": user_id,
            "typing_ticket": ticket,
            "status": status,
            "base_info": self._base_info(),
        }
        self._post(
            "/ilink/bot/sendtyping",
            json=payload,
            extra_headers=self._auth_header(bot_token),
        )

    def close(self) -> None:
        """关闭底层 HTTP 连接池。"""
        self._http.close()

    def _post(
        self,
        path: str,
        json: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = dict(self.BASE_HEADERS)
        headers.update(self._uin_header())
        if extra_headers:
            headers.update(extra_headers)
        url = f"{self.api_base}{path}"
        response = self._http.post(url, headers=headers, json=json, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ILinkError(
                code=exc.response.status_code,
                message=f"iLink 请求失败: {exc.response.text[:200]}",
            ) from exc
        data = response.json()
        ret = data.get("ret", 0)
        errcode = data.get("errcode", 0)
        if ret == -14 or errcode == -14:
            raise ILinkSessionExpired(
                code=-14,
                message=data.get("err_msg") or data.get("message") or "session 过期",
            )
        if ret != 0:
            err_msg = data.get("err_msg") or data.get("message") or ""
            logger.info("iLink API 返回非零 ret: ret=%s, err_msg=%s, path=%s", ret, err_msg, path)
        return data

    @staticmethod
    def _uin_header() -> dict[str, str]:
        uin = base64.b64encode(
            struct.pack(">I", secrets.randbits(32))
        ).decode().rstrip("=")
        return {"X-WECHAT-UIN": uin}

    @staticmethod
    def _auth_header(bot_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {bot_token}"}

    @staticmethod
    def _base_info() -> dict[str, str]:
        return {
            "channel_version": "2.4.3",
            "bot_agent": "person-date-wechat/1.0",
        }
