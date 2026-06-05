# 自研微信通道服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前项目中的微信能力收口为一套自研的 `wechat-channel` 服务，提供 `getupdates` / `sendmessage` / `getconfig` / `sendtyping` 协议，并与现有 FastAPI Adapter、Agent、Reminder Worker 和 Docker 编排打通。

**Architecture:** 采用“独立微信通道服务 + FastAPI 主后端”的单体双进程模式。`wechat-channel` 负责扫码会话、账号状态、长轮询与出站发送；`backend` 负责 Agent、业务服务、RBAC、日志和提醒调度。两者通过 HTTP JSON 交互，`WECHAT_CHANNEL_BASE_URL` 仅表示我们自己部署的通道服务地址。

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, APScheduler, httpx, pytest, Docker Compose, uv, pnpm

---

### Task 1: 落地自研微信通道 HTTP 协议层

**Files:**
- Create: `backend/app/wechat_channel_app.py`
- Create: `backend/app/wechat_channel_routes.py`
- Modify: `backend/app/core/wechat_channel.py`
- Modify: `backend/app/wechat_channel_main.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/schemas/wechat_channel.py`
- Modify: `docker-compose.yml`
- Test: `backend/tests/test_wechat_channel_app.py`
- Test: `backend/tests/test_wechat_channel_client.py`

- [ ] **Step 1: 写失败测试，锁定协议与启动行为**

```python
def test_wechat_channel_app_exposes_protocol_routes():
    client = TestClient(create_wechat_channel_app())
    assert client.post("/getupdates", json={"get_updates_buf": ""}).status_code == 200
    assert client.post("/sendmessage", json={"to_user_id": "wx_1", "content": "hi"}).status_code == 200
    assert client.post("/getconfig", json={"account_id": "wx_account_1"}).status_code == 200
    assert client.post("/sendtyping", json={"conversation_id": "wx_1", "typing": True}).status_code == 200

def test_wechat_channel_client_can_call_protocol_endpoints():
    client = WechatChannelHttpClient(base_url="http://wechat-channel:18789", channel_token="token")
    assert client.get_updates(bot_token="bot").next_cursor is not None
```

Run:

```bash
uv run pytest tests/test_wechat_channel_app.py tests/test_wechat_channel_client.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 2: 实现最小可用协议服务与客户端扩展**

新增通道协议请求 schema：

```text
WechatGetUpdatesRequest
WechatSendMessageRequest
WechatGetConfigRequest
WechatSendTypingRequest
```

```python
@router.post("/getupdates")
def get_updates(
    payload: WechatGetUpdatesRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[WechatGetUpdatesResponse]:
    service = WechatChannelService(db)
    data = service.get_updates(get_updates_buf=payload.get_updates_buf, bot_token=payload.bot_token)
    return ApiResponse(data=data)

@router.post("/sendmessage")
def send_message(
    payload: WechatSendMessageRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[WechatSendTextResponse]:
    service = WechatChannelService(db)
    log = service.send_text(
        conversation_id=payload.to_user_id,
        content=payload.content,
        context_token=payload.context_token,
    )
    return ApiResponse(data=WechatSendTextResponse(sent=log.status == "sent", conversation_id=log.conversation_id, content=payload.content, message_id=log.message_id, error_message=log.error_message))

@router.post("/getconfig")
def get_config(
    payload: WechatGetConfigRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[WechatGetConfigResponse]:
    service = WechatChannelService(db)
    data = service.get_config(account_id=payload.account_id)
    return ApiResponse(data=data)

@router.post("/sendtyping")
def send_typing(
    payload: WechatSendTypingRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[WechatSendTypingResponse]:
    service = WechatChannelService(db)
    data = service.send_typing(conversation_id=payload.conversation_id, typing=payload.typing)
    return ApiResponse(data=data)
```

新增 `WechatChannelHttpClient.get_config()` 与 `WechatChannelHttpClient.send_typing()`，并让 `wechat_channel_main.py` 在 `WECHAT_CHANNEL_BASE_URL` 缺失时保持空闲、在地址存在时启动真实服务模式。

Run:

```bash
uv run pytest tests/test_wechat_channel_app.py tests/test_wechat_channel_client.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 3: 验证协议服务在 Docker 中能被 backend 访问**

Run:

```bash
docker compose up -d --build
docker compose logs -f wechat-channel
```

Expected:

```text
wechat-channel started
backend can read WECHAT_CHANNEL_BASE_URL
```

- [ ] **Step 4: 独立提交**

```bash
git add backend/app/wechat_channel_app.py backend/app/wechat_channel_routes.py backend/app/core/wechat_channel.py backend/app/wechat_channel_main.py backend/app/core/config.py backend/.env.example docker-compose.yml backend/tests/test_wechat_channel_app.py backend/tests/test_wechat_channel_client.py
git commit -m "feat(wechat): 落地自研通道协议层"
```

---

### Task 2: 打通登录会话、账号状态与轮询游标

**Files:**
- Modify: `backend/app/services/wechat_channel_service.py`
- Modify: `backend/app/services/wechat_channel_poller.py`
- Modify: `backend/app/schemas/wechat_channel.py`
- Modify: `backend/app/models/channel.py`
- Modify: `backend/app/alembic/versions/*`（如需要补字段）
- Test: `backend/tests/test_wechat_login_sessions.py`
- Test: `backend/tests/test_wechat_channel_management.py`
- Test: `backend/tests/test_wechat_channel_poller.py`

- [ ] **Step 1: 写失败测试，覆盖会话确认、状态收敛和游标推进**

重点测试这三件事：

```text
1. POST /api/me/wechat-login-sessions/{id}/confirm 之后，wechat_accounts 和 channel_identities 都被写入。
2. getupdates 返回 401/403 时，WechatChannelPoller 会把账号状态改成 expired。
3. getupdates 返回新 cursor 时，WechatChannelPoller 会把 cursor 持久化到 wechat_accounts。
```

Run:

```bash
uv run pytest tests/test_wechat_login_sessions.py tests/test_wechat_channel_management.py tests/test_wechat_channel_poller.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 2: 实现会话与轮询状态机**

让 `WechatChannelService` 统一负责：

```text
create_login_session
get_login_session
confirm_login_session
list_accounts
list_active_accounts
update_account_cursor
update_account_status
list_message_logs
create_message_log
```

让 `WechatChannelPoller` 统一负责：

```text
拉取增量消息
去重
推进 cursor
401/403 标记 expired
网络错误标记 error
```

Run:

```bash
uv run pytest tests/test_wechat_login_sessions.py tests/test_wechat_channel_management.py tests/test_wechat_channel_poller.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 3: 独立提交**

```bash
git add backend/app/services/wechat_channel_service.py backend/app/services/wechat_channel_poller.py backend/app/schemas/wechat_channel.py backend/app/models/channel.py backend/app/alembic/versions backend/tests/test_wechat_login_sessions.py backend/tests/test_wechat_channel_management.py backend/tests/test_wechat_channel_poller.py
git commit -m "feat(wechat): 完成登录会话与轮询状态"
```

---

### Task 3: 收口入站转发、出站发送与提醒链路

**Files:**
- Modify: `backend/app/services/wechat_channel_adapter.py`
- Modify: `backend/app/api/routes/wechat.py`
- Modify: `backend/app/workers/reminder_worker.py`
- Modify: `backend/app/core/scheduler.py`
- Modify: `backend/app/core/wechat_channel.py`
- Test: `backend/tests/test_wechat_channel_adapter.py`
- Test: `backend/tests/test_wechat_inbound.py`
- Test: `backend/tests/test_wechat_outbound.py`
- Test: `backend/tests/test_reminder_worker.py`

- [ ] **Step 1: 写失败测试，覆盖入站去重、上下文 token、提醒发送**

重点测试这三件事：

```text
1. 相同 account_id + message_id 的微信入站请求只处理一次。
2. 出站发送时如果存在最近一条入站 context_token，send_text 会复用它。
3. ReminderWorker 触发时会走 WechatChannelService.send_text，而不是绕过通道层。
```

Run:

```bash
uv run pytest tests/test_wechat_channel_adapter.py tests/test_wechat_inbound.py tests/test_wechat_outbound.py tests/test_reminder_worker.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 2: 实现转发与发送链路**

让 `WechatChannelAdapter` 统一负责：

```text
原始消息标准化
签名 / token 校验
channel_identity 映射
调用 /api/wechat/inbound
记录 channel_message_logs
```

让 `ReminderWorker` 统一通过 `WechatChannelService.send_text()` 发提醒，并在失败时更新 `retry_count`、`error_code`、`error_message`。

Run:

```bash
uv run pytest tests/test_wechat_channel_adapter.py tests/test_wechat_inbound.py tests/test_wechat_outbound.py tests/test_reminder_worker.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 3: 独立提交**

```bash
git add backend/app/services/wechat_channel_adapter.py backend/app/api/routes/wechat.py backend/app/workers/reminder_worker.py backend/app/core/scheduler.py backend/app/core/wechat_channel.py backend/tests/test_wechat_channel_adapter.py backend/tests/test_wechat_inbound.py backend/tests/test_wechat_outbound.py backend/tests/test_reminder_worker.py
git commit -m "feat(wechat): 收口消息转发与提醒发送"
```

---

### Task 4: 对齐 Docker、文档和最终验收

**Files:**
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `docs/04-api-design.md`
- Modify: `docs/06-wechat-channel-design.md`
- Modify: `docs/08-codex-tasks.md`
- Modify: `docs/superpowers/specs/2026-06-05-self-hosted-wechat-channel-design.md`（如实现过程中发现边界需要微调）

- [ ] **Step 1: 写最终回归测试与冒烟命令**

重点冒烟检查：

```text
1. docker compose up -d --build 后，backend、web、wechat-channel 都处于 Up。
2. backend 可以通过 WECHAT_CHANNEL_BASE_URL 访问 wechat-channel。
3. wechat-channel 重启后不会丢失账号状态和游标。
```

Run:

```bash
uv run pytest tests -q
ruff check app tests
mypy app
docker compose up -d --build
```

Expected:

```text
tests pass
lint pass
types pass
containers up
```

- [ ] **Step 2: 同步说明文档**

明确写清：

```text
WECHAT_CHANNEL_BASE_URL = 我们自研微信通道服务地址
wechat-channel = 本项目独立的微信通道进程
OpenClaw Runtime = 不使用
```

- [ ] **Step 3: 独立提交**

```bash
git add docker-compose.yml README.md backend/README.md docs/04-api-design.md docs/06-wechat-channel-design.md docs/08-codex-tasks.md
git commit -m "docs(wechat): 收尾自研通道部署说明"
```

---

### Coverage Check

这份计划覆盖了设计说明中的关键要求：

1. 自研微信通道服务，而不是 OpenClaw Runtime。
2. `getupdates` / `sendmessage` / `getconfig` / `sendtyping` 协议。
3. 二维码登录会话、账号状态、游标、去重、消息日志。
4. FastAPI Adapter 与 Agent 闭环。
5. Docker Compose 启动与 `WECHAT_CHANNEL_BASE_URL` 口径。
6. 测试、lint、类型检查和分批提交。
