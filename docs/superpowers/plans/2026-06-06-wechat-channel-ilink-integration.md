# 微信通道 iLink 协议集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将微信通道的 mock 实现替换为真实的 iLink 协议通信，打通扫码登录→消息接收→消息发送全链路，并接入已有 Agent 系统。同时补完每日计划推送（含天气）功能。

**Architecture:** 新增 `ILinkClient` 协议层封装 iLink HTTP 通信。wechat-channel 进程启动后为每个账号启动 PollerThread 进行长轮询，写入 `wechat_channel_inbound_messages` 表。消息发送改为走 `ILinkClient.send_message()` 真实投递。登录流程改为获取真实 iLink 二维码。每日推送利用已有的 `UserSettings.daily_plan_push_time/enabled`。所有上层业务（Adapter、Agent、Routes）保持不变。

**Tech Stack:** Python, httpx, FastAPI, SQLAlchemy 2.0, APScheduler, pytest (with respx for HTTP mocking)

---

### Task 1: 实现 ILinkClient 协议层

**Files:**
- Create: `backend/wechat_channel/ilink_client.py`
- Create: `backend/tests/test_ilink_client.py`
- Modify: `backend/.env.example`（无新增配置，ILinkClient 硬编码 iLink 域名）

**设计说明：**
- `ILinkClient` 是一个无状态协议客户端，每个方法构造完整的 HTTP 请求发往 `ilinkai.weixin.qq.com`
- 所有方法通过 `_request()` 统一发送，使用可 mock 的 `httpx.Client`
- 响应解析防御性处理：字段可能缺失、类型可能变化
- `X-WECHAT-UIN` 每次请求随机生成（防重放）

- [ ] **Step 1: 写 ILinkClient 的 mock 测试**

```python
# backend/tests/test_ilink_client.py
from __future__ import annotations

import base64
import json
import struct
import secrets
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from wechat_channel.ilink_client import ILinkClient, QRResult, QRStatus, UpdatesResult


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
        with pytest.raises(RuntimeError, match="获取二维码失败"):
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && uv run pytest tests/test_ilink_client.py -v
```

Expected: `FAILED` / `ModuleNotFoundError` — `ilink_client.py` 还不存在。

- [ ] **Step 3: 实现 ILinkClient**

```python
# backend/wechat_channel/ilink_client.py
from __future__ import annotations

import base64
import json
import secrets
import struct
from dataclasses import dataclass, field
from typing import Any

import httpx


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
    """iLink 协议客户端，与 ilinkai.weixin.qq.com 通信。

    每个方法独立构造完整请求，不依赖内部状态（bot_token 每次由调用方传入）。
    使用方式：

        client = ILinkClient()
        qr = client.get_qr_code()
        status = client.poll_qr_status(qr.qrcode_id)
        updates = client.get_updates(bot_token, cursor)
        client.send_message(bot_token, to_user, text, ctx_token)
    """

    api_base: str = ILINK_API_BASE
    _http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
    )

    BASE_HEADERS: dict[str, str] = field(
        default_factory=lambda: {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": str((2 << 16) | (4 << 8) | 3),  # "2.4.3"
        }
    )

    # typing_ticket 缓存: {account_id: {user_id: ticket}}
    _typing_ticket_cache: dict[str, dict[str, str]] = field(default_factory=dict)

    # --- Public API ---

    def get_qr_code(self) -> QRResult:
        """获取登录二维码。

        POST ilink/bot/get_bot_qrcode?bot_type=3
        返回二维码标识和 base64 编码的图片内容。
        """
        data = self._post("/ilink/bot/get_bot_qrcode", params={"bot_type": "3"})
        try:
            qrcode_id = data["qrcode"]
            qr_img = data["qrcode_img_content"]
        except KeyError as exc:
            raise RuntimeError(f"获取二维码失败: 缺少字段 {exc}") from exc
        return QRResult(qrcode_id=qrcode_id, qr_img_content=qr_img)

    def poll_qr_status(self, qrcode_id: str) -> QRStatus:
        """轮询二维码扫码状态。

        POST ilink/bot/get_qrcode_status?qrcode={qrcode_id}
        返回 scanned / confirmed / expired 等状态。
        confirmed 时附带 bot_token 和 base_url。
        """
        data = self._post(f"/ilink/bot/get_qrcode_status", params={"qrcode": qrcode_id})
        status = data.get("status", "unknown")
        if status == "confirmed":
            return QRStatus(
                state="confirmed",
                token=data.get("bot_token"),
                base_url=data.get("baseurl"),
            )
        return QRStatus(state=status)

    def get_updates(self, bot_token: str, cursor: str | None) -> UpdatesResult:
        """长轮询拉取消息。

        POST ilink/bot/getupdates
        bot_token 用于 Bearer 鉴权。
        cursor 为上次返回的 get_updates_buf，首次调用传 None。
        服务端 hold 连接最多 35 秒。
        """
        payload: dict[str, object] = {}
        if cursor is not None:
            payload["get_updates_buf"] = cursor
        payload["base_info"] = self._base_info()

        data = self._post(
            "/ilink/bot/getupdates",
            json=payload,
            extra_headers=self._auth_header(bot_token),
        )
        msgs = data.get("msgs") or data.get("messages") or []
        new_cursor = data.get("get_updates_buf") or cursor or ""
        return UpdatesResult(msgs=msgs, new_cursor=new_cursor)

    def send_message(
        self,
        bot_token: str,
        to_user_id: str,
        text: str,
        context_token: str,
    ) -> bool:
        """发送文本消息到微信用户。

        POST ilink/bot/sendmessage
        必需完整消息结构，缺少字段可能导致 HTTP 200 但消息不投递。
        """
        client_id = f"openclaw-weixin-{secrets.token_hex(4)}"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": f"{to_user_id}@im.wechat",
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "context_token": context_token,
                "item_list": [
                    {
                        "type": 1,
                        "text_item": {"text": text},
                    }
                ],
            },
            "base_info": self._base_info(),
        }
        data = self._post(
            "/ilink/bot/sendmessage",
            json=payload,
            extra_headers=self._auth_header(bot_token),
        )
        ret = data.get("ret", -1)
        if ret != 0:
            return False
        return True

    def get_typing_ticket(
        self,
        bot_token: str,
        user_id: str,
        context_token: str,
    ) -> str | None:
        """获取 typing_ticket，用于发送"正在输入"状态。

        POST ilink/bot/getconfig
        结果缓存在内存中，同一用户后续调用复用以避免额外请求。
        """
        # 检查缓存
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

        # 写缓存
        if bot_token not in self._typing_ticket_cache:
            self._typing_ticket_cache[bot_token] = {}
        self._typing_ticket_cache[bot_token][user_id] = ticket
        return ticket

    def send_typing(
        self,
        bot_token: str,
        user_id: str,
        ticket: str,
        status: int = 1,
    ) -> None:
        """发送"正在输入"状态。

        status=1: 开始显示
        status=2: 取消显示
        发送文本消息前设 status=1，发送完成后设 status=2。
        """
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

    # --- Internal ---

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

        # 检查 session 过期
        if ret == -14 or errcode == -14:
            raise ILinkSessionExpired(
                code=-14,
                message=data.get("err_msg") or data.get("message") or "session 过期",
            )

        return data

    @staticmethod
    def _uin_header() -> dict[str, str]:
        """生成随机 X-WECHAT-UIN（32 位 uint → base64）。"""
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && uv run pytest tests/test_ilink_client.py -v
```

Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add backend/wechat_channel/ilink_client.py backend/tests/test_ilink_client.py
git commit -m "feat(wechat): 实现 ILinkClient 协议层"
```

---

### Task 2: 改造登录流程 — 对接真实二维码

**Files:**
- Modify: `backend/app/models/channel.py` — WechatLoginSession 加字段
- Modify: `backend/app/wechat_channel_routes.py` — 新增 QR 码路由
- Modify: `backend/app/api/routes/wechat.py` — 创建/轮询对接真实二维码
- Modify: `backend/tests/test_wechat_login_sessions.py` — 更新测试

- [ ] **Step 1: WechatLoginSession 模型加字段**

```python
# backend/app/models/channel.py — WechatLoginSession 类

# 在 expires_at 后面追加:
qr_img_content: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
qrcode_id: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
```

- [ ] **Step 2: 生成并运行迁移**

```bash
cd backend
uv run alembic revision --autogenerate -m "add qr_img_content and qrcode_id to login_sessions"
uv run alembic upgrade head
```

Expected: `alembic upgrade head` 成功，`wechat_login_sessions` 表新增 qr_img_content / qrcode_id 列。

- [ ] **Step 3: wechat-channel 新增真实二维码路由**

```python
# backend/app/wechat_channel_routes.py — 追加

import httpx
from app.core.wechat_channel import build_wechat_channel_client

@router.get("/channel/qr-code")
def generate_qr_code(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> dict[str, str]:
    """生成真实的 iLink 登录二维码，返回 base64 图片数据。"""
    from wechat_channel.ilink_client import ILinkClient
    try:
        client = ILinkClient()
        result = client.get_qr_code()
    except (RuntimeError, httpx.HTTPStatusError) as exc:
        raise HTTPException(status_code=502, detail=f"获取 iLink 二维码失败: {exc}")
    return {
        "qrcode_id": result.qrcode_id,
        "qr_img_content": result.qr_img_content,
    }


@router.get("/channel/qr-code-status")
def get_qr_code_status(
    qrcode_id: str = Query(),
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> dict[str, object]:
    """轮询二维码扫码状态。"""
    from wechat_channel.ilink_client import ILinkClient
    try:
        client = ILinkClient()
        status = client.poll_qr_status(qrcode_id)
    except (RuntimeError, httpx.HTTPStatusError) as exc:
        raise HTTPException(status_code=502, detail=f"轮询 iLink 状态失败: {exc}")
    return {
        "status": status.state,
        "bot_token": status.token,
        "base_url": status.base_url,
    }
```

- [ ] **Step 4: 修改 Backend 登录 API 对接真实二维码**

```python
# backend/app/api/routes/wechat.py — 修改 create_wechat_login_session

@router.post("/me/wechat-login-sessions")
def create_wechat_login_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatLoginSessionCreateResponse]:
    service = WechatChannelService(db)

    # 调 wechat-channel 获取真实二维码
    channel_client = build_wechat_channel_client()
    if channel_client is None:
        raise HTTPException(status_code=503, detail="微信通道服务不可用")
    try:
        qr = channel_client.get_channel_qr_code()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取二维码失败: {exc}")

    # 创建 session，写入真实二维码数据
    session = service.create_login_session(current_user.id)
    session.qr_img_content = qr["qr_img_content"]
    session.qrcode_id = qr["qrcode_id"]
    db.commit()

    return ApiResponse(
        data=WechatLoginSessionCreateResponse(
            login_session_id=session.login_session_id,
            qr_payload=session.qr_payload,
            qr_img_content=session.qr_img_content,
            expires_at=session.expires_at,
            status=session.status,
        ),
        message="请使用微信扫码完成登录",
    )
```

- [ ] **Step 5: 修改 Backend 轮询 API 做自动确认**

```python
# backend/app/api/routes/wechat.py — 重写 get_my_wechat_login_session

@router.get("/me/wechat-login-sessions/{login_session_id}")
def get_my_wechat_login_session(
    login_session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatLoginSessionItem]:
    service = WechatChannelService(db)
    session = service.get_login_session(
        owner_user_id=current_user.id,
        login_session_id=login_session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="登录会话不存在")

    # 如果已有真实二维码且未确认，轮询 iLink 扫码状态
    if session.qrcode_id and session.status in ("qr_created", "scanned"):
        channel_client = build_wechat_channel_client()
        if channel_client is not None:
            try:
                status = channel_client.get_channel_qr_code_status(session.qrcode_id)
                remote_state = status["status"]
                if remote_state == "scanned":
                    session.status = "scanned"
                    db.commit()
                elif remote_state == "confirmed":
                    # 自动确认绑定
                    bot_token = status["bot_token"]
                    base_url = status["base_url"]
                    wechat_user_id = status.get("wechat_user_id") or session.qrcode_id
                    service.confirm_login_session(
                        owner_user_id=current_user.id,
                        login_session_id=login_session_id,
                        account_id=session.qrcode_id,
                        wechat_user_id=wechat_user_id,
                        bot_token=bot_token,
                        base_url=base_url,
                    )
                    db.commit()
                elif remote_state == "expired":
                    session.status = "expired"
                    db.commit()
            except Exception:
                pass  # 轮询失败不阻塞，前端继续下一次轮询

    return ApiResponse(data=_to_login_session_item(session))
```

- [ ] **Step 6: 修复现有测试**

```bash
cd backend && uv run pytest tests/test_wechat_login_sessions.py -v
```

修复失败的测试（这些测试用 mock db session，需要在 LoginSessionCreateResponse schema 里加上可选的 qr_img_content 字段）。

- [ ] **Step 7: 更新 WechatLoginSessionCreateResponse schema**

```python
# backend/app/schemas/wechat.py — WechatLoginSessionCreateResponse 追加

class WechatLoginSessionCreateResponse(BaseModel):
    login_session_id: str
    qr_payload: str
    qr_img_content: str | None = None  # 新增：base64 二维码图片
    expires_at: datetime
    status: str
```

- [ ] **Step 8: 在 WechatChannelHttpClient 中新增 QR code 方法**

```python
# backend/app/core/wechat_channel.py — 追加方法

class WechatChannelHttpClient:
    # ... 现有方法保持不变

    def get_channel_qr_code(self) -> dict[str, str]:
        response = self._client.get(
            "/channel/qr-code",
            headers=self._headers(),
        )
        return response.json()

    def get_channel_qr_code_status(self, qrcode_id: str) -> dict[str, object]:
        response = self._client.get(
            f"/channel/qr-code-status",
            params={"qrcode_id": qrcode_id},
            headers=self._headers(),
        )
        return response.json()
```

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/channel.py backend/app/wechat_channel_routes.py backend/app/api/routes/wechat.py backend/app/core/wechat_channel.py backend/app/schemas/wechat.py backend/app/alembic/
git commit -m "feat(wechat): 登录流程对接真实 iLink 二维码"
```

---

### Task 3: 实现 PollerThread 长轮询接收消息

**Files:**
- Create: `backend/wechat_channel/poller.py` — PollerThread + PollerManager
- Modify: `backend/app/wechat_channel_main.py` — 启动时初始化 PollerManager
- Test: 手动验证

- [ ] **Step 1: 实现 PollerManager**

```python
# backend/wechat_channel/poller.py
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import WechatChannelInboundMessage
from wechat_channel.ilink_client import ILinkClient, ILinkSessionExpired

logger = logging.getLogger(__name__)


@dataclass
class PollerThread(threading.Thread):
    """单个微信账号的长轮询拉取线程。"""

    account_id: str
    bot_token: str
    cursor: str | None
    db_url: str
    ilink: ILinkClient = field(default_factory=ILinkClient)
    running: bool = True
    daemon: bool = True  # 主进程退出时自动结束

    def __post_init__(self) -> None:
        super().__init__(name=f"poller-{self.account_id[:8]}", daemon=True)
        engine = create_engine(self.db_url)
        self._session_factory = sessionmaker(bind=engine)

    def run(self) -> None:
        logger.info("Poller 启动: account=%s", self.account_id)
        consecutive_errors = 0

        while self.running:
            try:
                result = self.ilink.get_updates(
                    bot_token=self.bot_token,
                    cursor=self.cursor,
                )
                consecutive_errors = 0

                if result.msgs:
                    self._process_messages(result.msgs)

                if result.new_cursor != self.cursor:
                    self.cursor = result.new_cursor
                    self._save_cursor()

            except ILinkSessionExpired:
                logger.warning("Session 过期: account=%s", self.account_id)
                self._mark_expired()
                break
            except Exception:
                consecutive_errors += 1
                wait = min(consecutive_errors * 2, 30)  # 指数退避，最大 30s
                logger.exception(
                    "Poller 异常(account=%s, retry=%ds)", self.account_id, wait
                )
                time.sleep(wait)

    def _process_messages(self, msgs: list[dict[str, Any]]) -> None:
        db = self._session_factory()
        try:
            for msg in msgs:
                if msg.get("message_type") != 1:
                    continue  # 只处理文本消息
                text = (
                    msg.get("item_list", [{}])[0]
                    .get("text_item", {})
                    .get("text", "")
                )
                if not text:
                    continue

                from_user = msg.get("from_user_id", "")
                context_token = msg.get("context_token")
                msg_id = msg.get("msg_id") or f"{from_user}_{int(datetime.now(UTC).timestamp())}"

                # 去重: account_id + message_id 唯一约束在 DB 层
                existing = db.query(WechatChannelInboundMessage).filter(
                    WechatChannelInboundMessage.account_id == self.account_id,
                    WechatChannelInboundMessage.message_id == msg_id,
                ).first()
                if existing:
                    continue

                inbound = WechatChannelInboundMessage(
                    account_id=self.account_id,
                    message_id=msg_id,
                    cursor_token=self._build_cursor_token(),
                    conversation_id=from_user,
                    channel_user_id=from_user,
                    content_type="text",
                    content=text,
                    context_token=context_token,
                    raw_payload=msg,
                    status="pending",
                )
                db.add(inbound)
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("消息处理失败: account=%s", self.account_id)
        finally:
            db.close()

    def _save_cursor(self) -> None:
        db = self._session_factory()
        try:
            from app.models import WechatAccount
            account = db.query(WechatAccount).filter(
                WechatAccount.account_id == self.account_id
            ).first()
            if account:
                account.cursor = self.cursor
                account.last_active_time = datetime.now(UTC)
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("游标保存失败: account=%s", self.account_id)
        finally:
            db.close()

    def _mark_expired(self) -> None:
        db = self._session_factory()
        try:
            from app.models import WechatAccount
            account = db.query(WechatAccount).filter(
                WechatAccount.account_id == self.account_id
            ).first()
            if account:
                account.status = "expired"
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def stop(self) -> None:
        self.running = False

    @staticmethod
    def _build_cursor_token() -> str:
        timestamp = int(datetime.now(UTC).timestamp() * 1000)
        import secrets
        return f"{timestamp:013d}_{secrets.token_hex(8)}"


@dataclass
class PollerManager:
    """管理所有账号的 PollerThread 生命周期。"""

    db_url: str

    def __post_init__(self) -> None:
        self._threads: dict[str, PollerThread] = {}

    def start_all(self, accounts: list[tuple[str, str, str | None]]) -> None:
        """为所有 active 账号启动 poller。

        accounts: [(account_id, bot_token, cursor), ...]
        """
        for account_id, bot_token, cursor in accounts:
            if account_id in self._threads:
                continue
            thread = PollerThread(
                account_id=account_id,
                bot_token=bot_token,
                cursor=cursor,
                db_url=self.db_url,
            )
            thread.start()
            self._threads[account_id] = thread
            logger.info("Poller 已启动: %s", account_id)

    def stop_all(self) -> None:
        for thread in self._threads.values():
            thread.stop()
        for thread in self._threads.values():
            thread.join(timeout=5)
        self._threads.clear()

    def refresh(self, accounts: list[tuple[str, str, str | None]]) -> None:
        """刷新 poller 列表，停止已移除的账号，启动新账号。"""
        active_ids = {a[0] for a in accounts}

        # 停止不再 active 的线程
        for account_id in list(self._threads.keys()):
            if account_id not in active_ids:
                self._threads[account_id].stop()
                del self._threads[account_id]

        # 启动新线程
        self.start_all(accounts)
```

- [ ] **Step 2: 在 wechat-channel 启动时初始化 PollerManager**

```python
# backend/app/wechat_channel_main.py — 在 lifespan 中启动

from wechat_channel.poller import PollerManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    attach_wechat_channel_client(app)

    # 启动 PollerManager
    from app.db.session import get_db_url
    from app.services.wechat_channel_service import WechatChannelService

    db_url = get_db_url()
    poller_manager = PollerManager(db_url=db_url)
    app.state.poller_manager = poller_manager

    db = SessionLocal()
    try:
        service = WechatChannelService(db)
        accounts = [
            (a.account_id, a.bot_token, a.cursor)
            for a in service.list_active_accounts()
        ]
        poller_manager.start_all(accounts)
    finally:
        db.close()

    scheduler = None
    updates_client = getattr(app.state, "wechat_updates_client", None)
    if updates_client is not None:
        scheduler = build_wechat_channel_scheduler(
            updates_client_provider=lambda: getattr(app.state, "wechat_updates_client", None),
        )
        scheduler.start()
    app.state.wechat_channel_scheduler = scheduler
    try:
        yield
    finally:
        poller_manager.stop_all()
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        app.state.wechat_channel_scheduler = None
        close_wechat_channel_client(app)
```

- [ ] **Step 3: 提交**

```bash
git add backend/wechat_channel/poller.py backend/app/wechat_channel_main.py
git commit -m "feat(wechat): 实现 PollerThread 长轮询接收消息"
```

---

### Task 4: 改造消息发送 — 真实 iLink 发送

**Files:**
- Modify: `backend/app/services/wechat_channel_service.py` — send_text / send_typing 改为调 ILinkClient
- Modify: `backend/app/services/wechat_channel_poller.py` — polling 逻辑已由 PollerThread 接管，可注释或移除
- Test: 现有 `test_wechat_outbound.py` 验证

- [ ] **Step 1: 修改 `send_text()` 为真实发送**

```python
# backend/app/services/wechat_channel_service.py — 重写 send_text 方法

# 在文件顶部引入
from wechat_channel.ilink_client import ILinkClient, ILinkSessionExpired


class WechatChannelService:
    # ... 现有方法保持不变

    SESSION_EXPIRED_ERROR_CODES = {"SESSION_EXPIRED", "TOKEN_EXPIRED", "-14"}

    def _get_ilink_client(self) -> ILinkClient:
        """获取或创建 ILinkClient 实例。"""
        if not hasattr(self, '_ilink_client') or self._ilink_client is None:
            self._ilink_client = ILinkClient()
        return self._ilink_client

    def send_text(
        self,
        *,
        conversation_id: str,
        content: str,
        context_token: str | None = None,
        user_id: str | None = None,
        channel_user_id: str | None = None,
        message_id: str | None = None,
        retry_count: int = 0,
    ) -> ChannelMessageLog:
        identity = self.db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "wechat",
                ChannelIdentity.conversation_id == conversation_id,
                ChannelIdentity.status == "active",
            )
        )
        resolved_user_id = user_id or (identity.user_id if identity else None)
        resolved_channel_user_id = channel_user_id or (
            identity.channel_user_id if identity else None
        )
        resolved_context_token = context_token or self._resolve_context_token(conversation_id)

        # 查找可用的发送账号
        account = self.resolve_send_account(
            conversation_id=conversation_id,
            to_user_id=resolved_channel_user_id,
        )
        if account is None:
            return self.create_message_log(
                user_id=resolved_user_id,
                message_id=message_id,
                conversation_id=conversation_id,
                channel_user_id=resolved_channel_user_id,
                direction=MessageDirection.OUTBOUND.value,
                content_type="text",
                content=content,
                context_token=resolved_context_token,
                status="failed",
                error_code="NO_ACCOUNT",
                error_message="当前没有可用的微信账号",
            )

        ilink = self._get_ilink_client()
        status = "failed"
        error_code = None
        error_message = None
        outbound_retry_count = retry_count
        attempt_count = 0

        while attempt_count < self.SEND_TEXT_MAX_ATTEMPTS:
            attempt_count += 1
            try:
                # 1. 获取 typing_ticket（首次时需要）
                ticket = ilink.get_typing_ticket(
                    bot_token=account.bot_token,
                    user_id=resolved_channel_user_id or conversation_id,
                    context_token=resolved_context_token or "",
                )

                # 2. 显示"正在输入"
                if ticket:
                    ilink.send_typing(
                        bot_token=account.bot_token,
                        user_id=resolved_channel_user_id or conversation_id,
                        ticket=ticket,
                        status=1,
                    )

                # 3. 发送消息
                success = ilink.send_message(
                    bot_token=account.bot_token,
                    to_user_id=resolved_channel_user_id or conversation_id,
                    text=content,
                    context_token=resolved_context_token or "",
                )

                # 4. 取消"正在输入"
                if ticket:
                    try:
                        ilink.send_typing(
                            bot_token=account.bot_token,
                            user_id=resolved_channel_user_id or conversation_id,
                            ticket=ticket,
                            status=2,
                        )
                    except Exception:
                        pass  # 取消 typing 失败不影响消息发送

                if success:
                    status = "sent"
                    error_code = None
                    error_message = None
                    outbound_retry_count = retry_count + attempt_count - 1
                    account.last_active_time = datetime.now(UTC)
                    break

                error_message = "微信消息发送失败"
                error_code = "SEND_FAILED"

            except ILinkSessionExpired as exc:
                status = "failed"
                error_code = "SESSION_EXPIRED"
                error_message = str(exc)
                account.status = "expired"
                self.db.flush()
                break  # session 过期不重试
            except Exception as exc:
                error_message = str(exc)
                error_code = exc.__class__.__name__.upper()
                if not self._is_retryable_send_exception(exc) or attempt_count >= self.SEND_TEXT_MAX_ATTEMPTS:
                    outbound_retry_count = retry_count + attempt_count - 1
                    break

        # 记录到 outbound_messages 表
        if account:
            self.create_outbound_message(
                account=account,
                to_user_id=resolved_channel_user_id or conversation_id,
                conversation_id=conversation_id,
                content=content,
                context_token=resolved_context_token,
                status=status,
                retry_count=outbound_retry_count,
                error_code=error_code,
                error_message=error_message,
            )

        # 记录到 message_logs 表
        return self.create_message_log(
            user_id=resolved_user_id,
            message_id=message_id,
            conversation_id=conversation_id,
            channel_user_id=resolved_channel_user_id,
            direction=MessageDirection.OUTBOUND.value,
            content_type="text",
            content=content,
            context_token=resolved_context_token,
            status=status,
            retry_count=outbound_retry_count,
            error_code=error_code,
            error_message=error_message,
        )
```

- [ ] **Step 2: 修改 `send_typing()` 为真实发送**

```python
# backend/app/services/wechat_channel_service.py — 重写 send_typing 方法

def send_typing(
    self,
    *,
    conversation_id: str,
    typing: bool,
    account_id: str | None = None,
    bot_token: str | None = None,
    typing_ticket: str | None = None,
) -> WechatSendTypingResponse:
    account = self._resolve_account(account_id=account_id, bot_token=bot_token)
    if account is None:
        return WechatSendTypingResponse(success=True, ret=0, typing=typing)

    ilink = self._get_ilink_client()

    # 如果没有传入 ticket，尝试从缓存获取
    ticket = typing_ticket
    if not ticket:
        # 从最近一条入站消息获取 context_token
        context_token = self._resolve_context_token(conversation_id)
        if context_token:
            ticket = ilink.get_typing_ticket(
                bot_token=account.bot_token,
                user_id=conversation_id,
                context_token=context_token,
            )

    if not ticket:
        return WechatSendTypingResponse(success=True, ret=0, typing=typing)

    try:
        ilink.send_typing(
            bot_token=account.bot_token,
            user_id=conversation_id,
            ticket=ticket,
            status=1 if typing else 2,
        )
    except Exception:
        return WechatSendTypingResponse(
            success=False,
            ret=-1,
            typing=typing,
            error_code="TYPING_FAILED",
            error_message="发送 typing 状态失败",
        )

    return WechatSendTypingResponse(success=True, ret=0, typing=typing)
```

- [ ] **Step 3: 运行现有测试，确保不影响已有逻辑**

```bash
cd backend && uv run pytest tests/test_wechat_outbound.py tests/test_wechat_channel_adapter.py tests/test_wechat_inbound.py -v
```

Expected: ALL PASS（如果测试用了 mock sender，则不会受真实发送逻辑影响）

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/wechat_channel_service.py
git commit -m "feat(wechat): send_text/send_typing 改为真实 iLink 发送"
```

---

### Task 5: 实现每日计划推送 + 天气

**Files:**
- Modify: `backend/app/models/user.py` — UserSettings 加 city 字段
- Create: `backend/app/services/daily_notification_service.py` — 推送服务
- Modify: `backend/app/core/scheduler.py` — 注册定时任务
- Create: `backend/tests/test_daily_notification.py`
- Modify: `backend/.env.example` — 加天气 API 配置

**注意：** `UserSettings` 已有 `daily_plan_push_time` (08:00:00)、`daily_plan_push_enabled` (False)、`default_timezone`。只需要加 `city` 字段。

- [ ] **Step 1: UserSettings 加 city 字段+迁移**

```python
# backend/app/models/user.py — UserSettings 类

# 在 daily_plan_push_enabled 后追加:
city: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
```

```bash
cd backend
uv run alembic revision --autogenerate -m "add city to user_settings"
uv run alembic upgrade head
```

- [ ] **Step 2: 写服务的测试**

```python
# backend/tests/test_daily_notification.py
from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.daily_notification_service import DailyNotificationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    from app.db.base import Base
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def service(db_session):
    return DailyNotificationService(db_session)


class TestGetDueUsers:
    def test_returns_users_with_matching_time(self, service, db_session):
        from app.models.user import User, UserSettings
        user = User(username="test", display_name="Test", password_hash="hash")
        db_session.add(user)
        db_session.flush()

        settings = UserSettings(
            user_id=user.id,
            daily_plan_push_enabled=True,
            daily_plan_push_time="08:00",
        )
        db_session.add(settings)
        db_session.commit()

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # 模拟当前时间
        with patch.object(service, '_current_time', return_value="08:00"):
            users = service.get_due_users()
            assert len(users) == 1
            assert users[0].id == user.id

    def test_skips_disabled_users(self, service, db_session):
        from app.models.user import User, UserSettings
        user = User(username="test2", password_hash="hash")
        db_session.add(user)
        db_session.flush()
        settings = UserSettings(
            user_id=user.id,
            daily_plan_push_enabled=False,
            daily_plan_push_time="08:00",
        )
        db_session.add(settings)
        db_session.commit()

        with patch.object(service, '_current_time', return_value="08:00"):
            users = service.get_due_users()
            assert len(users) == 0


class TestBuildMessage:
    def test_builds_message_with_schedule(self, service):
        events = [
            {"time": "10:00", "title": "产品评审会议", "location": "3楼会议室"},
        ]
        tasks = [
            {"title": "完成周报", "priority": "高"},
        ]

        msg = service.build_message(
            date=datetime(2026, 6, 7),
            weather={"desc": "晴", "temp_min": 22, "temp_max": 31, "icon": "☀️"},
            city="北京",
            events=events,
            tasks=tasks,
        )
        assert "2026-06-07" in msg
        assert "北京" in msg
        assert "☀️" in msg
        assert "产品评审会议" in msg
        assert "完成周报" in msg

    def test_builds_empty_message(self, service):
        msg = service.build_message(
            date=datetime(2026, 6, 7),
            weather=None,
            city=None,
            events=[],
            tasks=[],
        )
        assert "暂无日程安排" in msg
        assert "暂无待办任务" in msg


class TestGetWeather:
    def test_returns_weather_data(self, service):
        with patch.object(service, '_fetch_weather_from_api') as mock_fetch:
            mock_fetch.return_value = {
                "desc": "晴", "temp_min": 22, "temp_max": 31, "icon": "☀️"
            }
            result = service.get_weather("北京")
            assert result["desc"] == "晴"
            assert result["temp_min"] == 22
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
cd backend && uv run pytest tests/test_daily_notification.py -v
```

Expected: FAILED — `daily_notification_service.py` 还不存在。

- [ ] **Step 4: 实现 DailyNotificationService**

```python
# backend/app/services/daily_notification_service.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User, UserSettings

logger = logging.getLogger(__name__)

WEATHER_CACHE: dict[str, dict[str, Any]] = {}
WEATHER_CACHE_TTL_SECONDS = 3600  # 1 小时
WEATHER_CACHE_TIMESTAMP: dict[str, float] = {}


class DailyNotificationService:
    """每日计划推送服务。

    在用户设置的推送时间，查询当天日程和天气，拼装消息并通过微信发送。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_due_users(self) -> list[User]:
        """查找当前时间点需要推送的用户。"""
        current_time = self._current_time()
        stmt = (
            select(User)
            .join(UserSettings)
            .where(
                UserSettings.daily_plan_push_enabled == True,
                UserSettings.daily_plan_push_time == current_time,
            )
        )
        return list(self.db.scalars(stmt))

    def notify_user(self, user: User) -> bool:
        """向单个用户推送今日日程 + 天气。"""
        from app.services.wechat_channel_service import WechatChannelService
        from app.models import ChannelIdentity

        # 1. 查日程
        events = self._get_today_events(user.id)
        tasks = self._get_today_tasks(user.id)

        # 2. 查天气
        settings = self.db.scalar(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        city = settings.city if settings else None
        weather = None
        if city:
            try:
                weather = self.get_weather(city)
            except Exception:
                logger.exception("获取天气失败: city=%s", city)

        # 3. 拼消息
        message = self.build_message(
            date=datetime.now(),
            weather=weather,
            city=city,
            events=events,
            tasks=tasks,
        )

        # 4. 推送
        identity = self.db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "wechat",
                ChannelIdentity.user_id == user.id,
                ChannelIdentity.status == "active",
            )
        )
        if identity is None:
            logger.info("用户 %s 没有绑定微信，跳过推送", user.id)
            return False

        wechat_service = WechatChannelService(self.db)
        log = wechat_service.send_text(
            conversation_id=identity.conversation_id,
            content=message,
            user_id=user.id,
        )
        return log.status == "sent"

    def get_weather(self, city: str) -> dict[str, Any]:
        """获取城市天气，带 1 小时缓存。"""
        now = datetime.now().timestamp()
        if city in WEATHER_CACHE:
            age = now - WEATHER_CACHE_TIMESTAMP.get(city, 0)
            if age < WEATHER_CACHE_TTL_SECONDS:
                return WEATHER_CACHE[city]

        data = self._fetch_weather_from_api(city)
        WEATHER_CACHE[city] = data
        WEATHER_CACHE_TIMESTAMP[city] = now
        return data

    def build_message(
        self,
        *,
        date: datetime,
        weather: dict[str, Any] | None,
        city: str | None,
        events: list[dict[str, str]],
        tasks: list[dict[str, str]],
    ) -> str:
        """拼装推送消息。"""
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_names[date.weekday()]
        date_str = date.strftime("%Y-%m-%d")

        lines: list[str] = []

        # 问候 + 日期
        lines.append(f"🌤 早安！今天是 {date_str} {weekday}")
        lines.append("")

        # 天气
        if weather and city:
            icon = weather.get("icon", "🌤")
            desc = weather.get("desc", "")
            temp_min = weather.get("temp_min", "?")
            temp_max = weather.get("temp_max", "?")
            lines.append(f"📍 {city} 今日天气：{icon} {desc}  {temp_min}~{temp_max}°C")
            lines.append("")
        elif city:
            lines.append(f"📍 {city}")
            lines.append("")

        # 日程
        lines.append("📅 今日日程：")
        if events:
            for event in events:
                loc = f"  📍 {event['location']}" if event.get("location") else ""
                lines.append(f"  • {event['time']} - {event['title']}{loc}")
        else:
            lines.append("  （暂无日程安排）")
        lines.append("")

        # 待办任务
        lines.append("✅ 待办任务：")
        if tasks:
            for task in tasks:
                priority = task.get("priority", "")
                prio_tag = f"（{priority}优先级）" if priority else ""
                lines.append(f"  • {task['title']}{prio_tag}")
        else:
            lines.append("  （暂无待办任务）")
        lines.append("")

        lines.append("📌 回复我可调整今日安排～")
        return "\n".join(lines)

    # --- Internal ---

    def _current_time(self) -> str:
        return datetime.now().strftime("%H:%M")

    def _get_today_events(self, user_id: str) -> list[dict[str, str]]:
        """查询用户当天的日程事件。"""
        from app.models import Event
        today = datetime.now().date()
        stmt = (
            select(Event)
            .where(
                Event.user_id == user_id,
                Event.date == today,
                Event.status.in_({"active", "confirmed"}),
            )
            .order_by(Event.start_time.asc())
        )
        results = []
        for event in self.db.scalars(stmt):
            results.append({
                "time": event.start_time.strftime("%H:%M") if event.start_time else "",
                "title": event.title,
                "location": event.location or "",
            })
        return results

    def _get_today_tasks(self, user_id: str) -> list[dict[str, str]]:
        """查询用户当天的待办任务。"""
        from app.models import Task
        today = datetime.now().date()
        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.due_date == today,
                Task.status.in_({"todo", "in_progress"}),
            )
            .order_by(Task.priority.desc(), Task.created_at.asc())
        )
        results = []
        for task in self.db.scalars(stmt):
            results.append({
                "title": task.title,
                "priority": task.priority,
            })
        return results

    def _fetch_weather_from_api(self, city: str) -> dict[str, Any]:
        """调用和风天气 API 获取天气数据。"""
        settings = get_settings()
        api_key = settings.weather_api_key
        if not api_key:
            logger.warning("天气 API Key 未配置")
            return {"desc": "未知", "temp_min": "?", "temp_max": "?", "icon": "🌤"}

        provider = settings.weather_api_provider or "qweather"
        if provider == "qweather":
            return self._fetch_qweather(city, api_key)
        elif provider == "openweathermap":
            return self._fetch_openweathermap(city, api_key)
        else:
            return {"desc": "未知", "temp_min": "?", "temp_max": "?", "icon": "🌤"}

    def _fetch_qweather(self, city: str, api_key: str) -> dict[str, Any]:
        """和风天气 API。"""
        with httpx.Client(timeout=10) as client:
            # 1. 查询城市 ID
            geo_resp = client.get(
                "https://geoapi.qweather.com/v2/city/lookup",
                params={"location": city, "key": api_key},
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            if geo_data.get("code") != "200" or not geo_data.get("location"):
                raise RuntimeError(f"找不到城市: {city}")
            location_id = geo_data["location"][0]["id"]

            # 2. 查询天气
            weather_resp = client.get(
                "https://devapi.qweather.com/v7/weather/now",
                params={"location": location_id, "key": api_key},
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()
            if weather_data.get("code") != "200":
                raise RuntimeError(f"天气查询失败: {weather_data}")

            now_data = weather_data.get("now", {})
            return {
                "desc": now_data.get("text", "未知"),
                "temp": now_data.get("temp", "?"),
                "icon": self._qweather_icon_to_emoji(now_data.get("icon", "")),
            }

    def _fetch_openweathermap(self, city: str, api_key: str) -> dict[str, Any]:
        """OpenWeatherMap API。"""
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric", "lang": "zh_cn"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "desc": data["weather"][0]["description"],
                "temp_min": round(data["main"]["temp_min"]),
                "temp_max": round(data["main"]["temp_max"]),
                "icon": self._owm_icon_to_emoji(data["weather"][0]["icon"]),
            }

    @staticmethod
    def _qweather_icon_to_emoji(icon: str) -> str:
        mapping = {
            "100": "☀️", "101": "🌤", "102": "⛅", "103": "🌥",
            "104": "☁️", "150": "🌙", "151": "🌙",
            "300": "🌦", "301": "🌦", "302": "🌧", "303": "🌧",
            "400": "🌨", "401": "🌨", "402": "🌨",
            "500": "🌫", "501": "🌫", "502": "🌫",
            "503": "🌪", "504": "🌪",
            "507": "🏔", "508": "🏔",
        }
        return mapping.get(icon, "🌤")

    @staticmethod
    def _owm_icon_to_emoji(icon: str) -> str:
        mapping = {
            "01d": "☀️", "01n": "🌙", "02d": "🌤", "02n": "🌙",
            "03d": "⛅", "03n": "☁️", "04d": "☁️", "04n": "☁️",
            "09d": "🌧", "09n": "🌧", "10d": "🌦", "10n": "🌧",
            "11d": "⛈", "11n": "⛈", "13d": "🌨", "13n": "🌨",
            "50d": "🌫", "50n": "🌫",
        }
        return mapping.get(icon, "🌤")
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd backend && uv run pytest tests/test_daily_notification.py -v
```

Expected: ALL PASS

- [ ] **Step 6: 在 scheduler 中注册定时任务**

```python
# backend/app/core/scheduler.py — 追加新函数和 job

from app.services.daily_notification_service import DailyNotificationService


def run_daily_notification_scan(
    *,
    session_factory: SessionFactory = SessionLocal,
) -> int:
    """检查并执行到点的每日推送。"""
    db = session_factory()
    try:
        service = DailyNotificationService(db)
        users = service.get_due_users()
        pushed_count = 0
        for user in users:
            try:
                if service.notify_user(user):
                    pushed_count += 1
            except Exception:
                logger.exception("推送失败: user=%s", user.id)
        return pushed_count
    finally:
        db.close()


def build_wechat_channel_scheduler(...) -> BackgroundScheduler:
    # 在现有 job 之后追加

    scheduler.add_job(
        run_daily_notification_scan,
        trigger="interval",
        minutes=1,  # 每分钟检查一次
        id="daily-notification-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={
            "session_factory": session_factory,
        },
    )
    return scheduler
```

- [ ] **Step 7: 更新 .env.example**

```ini
# backend/.env.example — 追加
WEATHER_API_PROVIDER=qweather
WEATHER_API_KEY=
```

- [ ] **Step 8: 在 config.py 中读取天气配置**

```python
# backend/app/core/config.py — 追加两个字段

weather_api_provider: str = "qweather"
weather_api_key: str = ""
```

- [ ] **Step 9: 提交**

```bash
git add backend/app/services/daily_notification_service.py backend/app/core/scheduler.py backend/app/core/config.py backend/app/models/user.py backend/.env.example backend/tests/test_daily_notification.py backend/app/alembic/
git commit -m "feat(wechat): 实现每日计划推送 + 天气"
```

---

### Task 6: Web 端对接 — 展示真实二维码 + 通知设置页

**Files:**
- Modify: `web/` — 扫码页面改为展示真实 `<img src="data:image/...">`
- Modify: `web/` — 通知设置页面

- [ ] **Step 1: 修改扫码页面展示真实二维码**

现有扫码页展示 `qr_payload`（字符串），改为展示 `qr_img_content`（base64 图片）。

```tsx
// web/src/pages/bind-wechat.tsx (示例路径，按实际项目结构调整)

// 创建会话时取 qr_img_content
const { data } = await api.post('/me/wechat-login-sessions');
setQrCodeSrc(`data:image/png;base64,${data.qr_img_content}`);

// 渲染
<img src={qrCodeSrc} alt="微信扫码" />
```

- [ ] **Step 2: 调整轮询逻辑**

前端轮询 `GET /me/wechat-login-sessions/{id}`，当状态变为 `confirmed` 时自动跳转到成功页。

```tsx
// 轮询循环
const poll = async () => {
  const { data } = await api.get(`/me/wechat-login-sessions/${sessionId}`);
  if (data.status === 'confirmed') {
    navigate('/bind-success');
  } else if (data.status === 'expired') {
    setError('二维码已过期，请刷新页面重新获取');
  } else {
    setTimeout(poll, 2000);
  }
};
```

- [ ] **Step 3: 新增通知设置页面**

```tsx
// web/src/pages/notification-settings.tsx (示例路径)

const NotificationSettings = () => {
  const [enabled, setEnabled] = useState(false);
  const [time, setTime] = useState('08:00');
  const [city, setCity] = useState('');

  const save = async () => {
    await api.put('/me/notification-settings', {
      daily_plan_push_enabled: enabled,
      daily_plan_push_time: time,
      city,
    });
  };

  return (
    <div>
      <h2>每日推送设置</h2>
      <Switch checked={enabled} onChange={setEnabled} label="开启每日推送" />
      <TimePicker value={time} onChange={setTime} />
      <Input value={city} onChange={setCity} placeholder="所在城市（用于天气）" />
      <Button onClick={save}>保存</Button>
    </div>
  );
};
```

- [ ] **Step 4: 通知设置 API**

```python
# backend/app/api/routes/wechat.py — 追加通知设置路由

@router.get("/me/notification-settings")
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    if settings is None:
        return ApiResponse(data={"daily_plan_push_enabled": False, "daily_plan_push_time": "08:00", "city": None})
    return ApiResponse(data={
        "daily_plan_push_enabled": settings.daily_plan_push_enabled,
        "daily_plan_push_time": settings.daily_plan_push_time,
        "city": settings.city,
    })


@router.put("/me/notification-settings")
def update_notification_settings(
    payload: NotificationSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    if settings is None:
        from app.models.user import UserSettings
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
    settings.daily_plan_push_enabled = payload.daily_plan_push_enabled
    settings.daily_plan_push_time = payload.daily_plan_push_time
    settings.city = payload.city
    db.commit()
    return ApiResponse(message="已保存")
```

```python
# backend/app/schemas/wechat.py — 追加 schema

class NotificationSettingsUpdateRequest(BaseModel):
    daily_plan_push_enabled: bool = False
    daily_plan_push_time: str = "08:00"
    city: str | None = None
```

- [ ] **Step 5: 提交**

```bash
git add web/ backend/app/api/routes/wechat.py backend/app/schemas/wechat.py
git commit -m "feat(web): 展示真实二维码 + 通知设置页"
```

---

### Coverage Check

| 设计文档需求 | 对应 Task | 说明 |
|------------|-----------|------|
| ILinkClient 协议层（6 个方法） | Task 1 | `get_qr_code`, `poll_qr_status`, `get_updates`, `send_message`, `get_typing_ticket`, `send_typing` |
| 登录流程: 真实二维码 | Task 2 | 路由 + 后端 API 修改 + DB 迁移 |
| 消息接收: 长轮询 | Task 3 | PollerThread + PollerManager |
| 消息发送: 真实投递 | Task 4 | send_text / send_typing 改为调 ILinkClient |
| typing 缓存 | Task 4 | `ILinkClient._typing_ticket_cache` 内存缓存 |
| 24h 重连: 检测 -14 | Task 4 | `ILinkSessionExpired` 异常处理，标记 expired |
| 每日推送 + 天气 | Task 5 | DailyNotificationService |
| 天气缓存 | Task 5 | `WEATHER_CACHE` 1h TTL |
| 前端对接 | Task 6 | 真实二维码展示 + 通知设置页 |
| 现有代码不变 | — | Adapter、Agent、schemas 均不变 |
