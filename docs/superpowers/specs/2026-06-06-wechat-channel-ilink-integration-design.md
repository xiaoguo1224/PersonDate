# 微信通道 iLink 协议集成设计

> 将微信通道的 mock 实现替换为真实的 iLink 协议通信，并增加每日日程推送+天气功能。

## 1. 背景

### 1.1 当前状态

现有 `wechat-channel` 服务（port 18789）是一个模拟实现：

| 接口 | 当前实现 | 问题 |
|------|---------|------|
| `getupdates` | 从本地 `wechat_channel_inbound_messages` 表读取 | 永远为空，没有真实数据写入 |
| `sendmessage` | 写入出站队列后结束 | 消息从未真正送达微信用户 |
| `sendtyping` | 空操作 | 用户看不到"正在输入" |
| `getconfig` | 返回硬编码数据 | 无法获取真实的 typing_ticket |
| 登录流程 | 返回自定义 `qr_payload` 字符串 | 不是真正的微信二维码 |

**结论：架构设计正确，但缺少底层的 iLink 协议通信实现。**

### 1.2 开源项目参考

[weixin-ClawBot-API](https://github.com/SiverKing/weixin-ClawBot-API) 实现了与腾讯 `ilinkai.weixin.qq.com` 的真实 iLink 协议通信，包括：

- ✅ QR 码获取与扫码状态轮询
- ✅ 长轮询拉取真实微信消息
- ✅ 消息真实投递
- ✅ "正在输入"状态
- ✅ 24h token 过期预警与重连

本项目提取其协议层代码（约 300 行），封装为 `ILinkClient` 嵌入 wechat-channel 服务。

### 1.3 设计原则

1. **不动上层业务** — 路由、适配器、Agent 链路全部复用
2. **只换协议实现层** — 将 mock 实现替换为真实 iLink 调用
3. **渐进式集成** — 分阶段上线，核心链路优先

## 2. 总体架构

```
用户微信                              wechat-channel (port 18789)              FastAPI Backend (port 8000)
    │                                       │                                       │
    │   ┌── 每日推送 ─────────────────────┐  │                                       │
    │   │ APScheduler → ILinkClient       │  │                                       │
    │   │ .send_message() → 真实推送      │  │                                       │
    │   │ 每日日程 + 天气                  │  │                                       │
    │   └────────────────────────────────┘  │                                       │
    │                                       │                                       │
    │   ┌── 消息接收 ─────────────────────┐  │  ┌── 消息处理 ──────────────────────┐  │
    │◄──│ PollerThread                    │  │  │                              │  │
    │   │ ILinkClient.get_updates() 循环   │──┼──│→POST /wechat/inbound          │  │
    │   │ → 写入 inbound_messages 表       │  │  │→WechatChannelAdapter          │  │
    │   │ → Backend 通过 /getupdates 读取  │  │  │→SchedulePlanningGraph (Agent) │  │
    │   └────────────────────────────────┘  │  │→回复 → sendmessage            │  │
    │                                       │  └────────────────────────────────┘  │
    │   ┌── 消息发送 ─────────────────────┐  │                                       │
    │◄──│ ILinkClient.send_message()       │◄─┼── send_text() 调用                  │
    │   │ ILinkClient.send_typing()        │  │                                       │
    │   └────────────────────────────────┘  │                                       │
    │                                       │                                       │
    │   ┌── 登录 ─────────────────────────┐  │  ┌── Web 扫码 ────────────────────┐  │
    │   │ ILinkClient.get_qr_code()        │◄─┼──│ POST /me/wechat-login-sessions │  │
    │   │ ILinkClient.poll_qr_status()     │──┼─►│ GET .../{id} 轮询              │  │
    │   └────────────────────────────────┘  │  └────────────────────────────────┘  │
    │                                       │                                       │
    ▼                                       ▼                                       ▼
ilinkai.weixin.qq.com                  DB (6 张表)                           Web Dashboard
```

### 2.1 进程关系

```
┌──────────────────────────────────────────────────────────────────┐
│  wechat-channel 进程 (port 18789)                                 │
│                                                                  │
│  FastAPI app: 路由层 (复用现有)                                    │
│    /getupdates /sendmessage /sendtyping /getconfig               │
│    /channel/qr-code /channel/qr-code-status                      │
│                                                                  │
│  ILinkClient: 协议层 (新增)                                       │
│    HTTP 通信 → ilinkai.weixin.qq.com                             │
│                                                                  │
│  PollerThreads: 后台线程 (新增)                                    │
│    每个 active 账号一个线程, 持续 getupdates 循环                   │
│                                                                  │
│  Scheduler: 定时任务                                              │
│    每日日程推送 + 天气                                             │
└──────────────────────────────────────────────────────────────────┘
                           │ HTTP
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI Backend 进程 (port 8000)                                 │
│  WechatChannelHttpClient → 调 wechat-channel                     │
│  WechatChannelAdapter → Agent → 回复                             │
│  Web 扫码 API → 调 wechat-channel 获取二维码                      │
└──────────────────────────────────────────────────────────────────┘
```

## 3. ILinkClient 协议层

**文件：** `backend/wechat_channel/ilink_client.py`（新增，约 300 行）

### 3.1 类定义

```python
@dataclass
class ILinkClient:
    """iLink 协议客户端，与 ilinkai.weixin.qq.com 通信。"""

    api_base: str = "https://ilinkai.weixin.qq.com"
    _http: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=60))

    # 固定请求头
    BASE_HEADERS = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "iLink-App-Id": "bot",
        "iLink-App-ClientVersion": str((2 << 16) | (4 << 8) | 3),
    }
```

### 3.2 方法清单

```python
def get_qr_code(self) -> QRResult
    """POST ilink/bot/get_bot_qrcode?bot_type=3
    返回: QRResult(qrcode_id, qr_img_content: base64)
    请求头携带随机 X-WECHAT-UIN"""

def poll_qr_status(self, qrcode_id: str) -> QRStatus
    """POST ilink/bot/get_qrcode_status?qrcode={qrcode_id}
    返回: QRStatus(scanned/confirmed/expired, bot_token?, base_url?)
    每 1-2 秒轮询一次, iLink 端确认后返回 bot_token"""

def get_updates(self, bot_token: str, cursor: str | None) -> UpdatesResult
    """POST ilink/bot/getupdates
    长轮询, 服务端 hold 最多 35 秒
    返回: UpdatesResult(msgs[], new_get_updates_buf)
    消息结构: from_user_id, context_token, item_list[0].text_item.text
    每次请求必须携带上一次返回的 get_updates_buf"""

def send_message(self, bot_token: str, to_user_id: str,
                 text: str, context_token: str) -> bool
    """POST ilink/bot/sendmessage
    必需字段: from_user_id="", to_user_id="@im.wechat"格式,
              client_id, message_type=2, message_state=2,
              context_token, item_list, base_info
    缺少任何字段会导致消息静默丢失(HTTP 200 但不投递)"""

def get_typing_ticket(self, bot_token: str,
                      user_id: str, context_token: str) -> str | None
    """POST ilink/bot/getconfig
    返回 typing_ticket, 用于 send_typing
    缓存: 首次对话时获取, 同一用户后续复用"""

def send_typing(self, bot_token: str, user_id: str,
                ticket: str, status: int = 1) -> None
    """POST ilink/bot/sendtyping
    status=1: 开始"正在输入"
    status=2: 取消"正在输入"
    发送消息前设 status=1, 发送完成后设 status=2"""
```

### 3.3 通用请求头

```python
@property
def _auth_headers(self) -> dict[str, str]:
    """每次请求刷新 X-WECHAT-UIN（随机 32 位 uint 转 base64）"""
    uin = base64.b64encode(
        struct.pack(">I", secrets.randbits(32))
    ).decode().rstrip("=")
    return {"X-WECHAT-UIN": uin}
```

### 3.4 sendmessage 消息结构

```json
{
  "msg": {
    "from_user_id": "",
    "to_user_id": "{to_user_id}@im.wechat",
    "client_id": "openclaw-weixin-{random_8_hex}",
    "message_type": 2,
    "message_state": 2,
    "context_token": "{context_token}",
    "item_list": [
      {
        "type": 1,
        "text_item": {"text": "{回复内容}"}
      }
    ]
  },
  "base_info": {
    "channel_version": "2.4.3",
    "bot_agent": "person-date-wechat/1.0"
  }
}
```

## 4. 登录流程改造

### 4.1 DB 模型变更

`WechatLoginSession` 表新增字段：

```python
qr_img_content: str | None   # base64 编码的二维码图片数据
qrcode_id: str | None        # iLink 平台返回的 qrcode 标识
```

### 4.2 新增 wechat-channel 路由

```python
# wechat_channel_routes.py

@router.post("/channel/qr-code")
def generate_qr_code():
    """调 ILinkClient.get_qr_code(), 返回真实二维码"""
    result = ilink.get_qr_code()
    return {"qrcode_id": result.id, "qr_img": result.img_base64}

@router.get("/channel/qr-code-status")
def get_qr_code_status(qrcode_id: str):
    """调 ILinkClient.poll_qr_status(), 轮询扫码状态"""
    status = ilink.poll_qr_status(qrcode_id)
    return {
        "status": status.state,       # scanned / confirmed / expired
        "bot_token": status.token,    # confirmed 时返回
        "base_url": status.base_url,  # confirmed 时返回
    }
```

### 4.3 Backend 登录 API 调整

```python
# backend/app/api/routes/wechat.py

@router.post("/me/wechat-login-sessions")
def create_wechat_login_session(...):
    # 调 wechat-channel → ILinkClient.get_qr_code()
    qr_code = channel_client.generate_qr_code()
    # 存 DB, 返回 real QR image to Web
    session = service.create_login_session(...)
    session.qr_img_content = qr_code.img_base64  # 直接给前端展示
    session.qrcode_id = qr_code.id
    ...

@router.get("/me/wechat-login-sessions/{id}")
def get_wechat_login_session(...):
    # 调 wechat-channel → ILinkClient.poll_qr_status()
    status = channel_client.get_qr_code_status(session.qrcode_id)
    if status.state == "confirmed":
        # 自动 confirm, 保存 bot_token / base_url / account_id
        service.confirm_login_session(...)
        # 启动 poller
```

### 4.4 前端展示

```html
<!-- 直接使用 base64 图片数据 -->
<img src="data:image/png;base64,{qr_img_content}" />
```

## 5. 消息接收（长轮询）

### 5.1 PollerThread

wechat-channel 启动时为每个 active 账号启动一个 PollerThread：

```python
class WechatPollerThread(threading.Thread):
    """每个微信账号一个线程，持续长轮询 iLink"""
    
    def __init__(self, account_id, bot_token, base_url, cursor, db_url):
        self.account_id = account_id
        self.bot_token = bot_token
        self.cursor = cursor
        self.ilink = ILinkClient()
        self.db_session = create_session(db_url)
    
    def run(self):
        while self.running:
            try:
                result = self.ilink.get_updates(self.bot_token, self.cursor)
                for msg in result.msgs:
                    self._process_message(msg)
                self.cursor = result.new_cursor
                self._save_cursor()
            except ILinkSessionExpired:
                self._mark_expired()
                break
            except Exception:
                time.sleep(5)  # 退避重试
```

### 5.2 消息处理

```python
def _process_message(self, msg):
    """将 iLink 原始消息写入 inbound 表"""
    text = msg["item_list"][0]["text_item"]["text"]
    message_id = msg.get("msg_id", generate_id())
    
    # 去重 (account_id + message_id)
    if self._is_duplicate(message_id):
        return
    
    self.db_session.add(WechatChannelInboundMessage(
        account_id=self.account_id,
        message_id=message_id,
        conversation_id=msg["from_user_id"],
        channel_user_id=msg["from_user_id"],
        content_type="text",
        content=text,
        context_token=msg["context_token"],
        raw_payload=msg,
        status="pending",
        cursor_token=build_cursor_token(),
    ))
    self.db_session.commit()
```

### 5.3 Backend 消费不变

现有 `WechatChannelPoller` 和 `WechatChannelAdapter` 保持不变，它们通过 `/getupdates` 读到 `inbound_messages` 表中的数据，经由 Adapter → Agent 处理。

## 6. 消息发送

### 6.1 send_text 改造

```python
# WechatChannelService.send_text()

def send_text(self, ..., conversation_id, content, context_token):
    account = self.resolve_send_account(conversation_id=conversation_id)
    if not account:
        raise NoActiveAccount()
    
    # 1. 获取 typing_ticket（首次或缓存过期）
    if not typing_ticket_cache.get(account.account_id, conversation_id):
        ticket = self.ilink.get_typing_ticket(
            account.bot_token, conversation_id, context_token
        )
        cache_set(account.account_id, conversation_id, ticket)
    
    # 2. 显示"正在输入"
    self.ilink.send_typing(account.bot_token, conversation_id, ticket, status=1)
    
    # 3. 发送消息
    success = self.ilink.send_message(
        account.bot_token, conversation_id, content, context_token
    )
    
    # 4. 取消"正在输入"
    self.ilink.send_typing(account.bot_token, conversation_id, ticket, status=2)
    
    # 5. 记录日志
    return self.create_message_log(..., status="sent" if success else "failed")
```

### 6.2 send_typing 改造

```python
def send_typing(self, ..., conversation_id, typing):
    account = self.resolve_send_account(conversation_id=conversation_id)
    if not account:
        return
    ticket = typing_ticket_cache.get(account.account_id, conversation_id)
    if ticket:
        self.ilink.send_typing(
            account.bot_token, conversation_id, ticket,
            status=1 if typing else 2
        )
```

## 7. 每日日程推送 + 天气

### 7.1 用户配置

User 模型新增字段（或单独的用户设置表）：

```python
daily_notification_enabled: bool = False      # 是否开启每日推送
daily_notification_time: str | None = "08:00" # 推送时间 HH:mm
timezone: str = "Asia/Shanghai"               # 用户时区
city: str | None = None                       # 城市（查天气用）
```

### 7.2 天气 API 接入

配置项：

```ini
# .env
WEATHER_API_PROVIDER=qweather      # 和风天气
WEATHER_API_KEY=your_api_key_here
```

推荐 [和风天气](https://dev.qweather.com/)（国内更准，免费 1000 次/天）。

缓存策略：同一城市当天的天气每小时刷新一次，避免重复调用。

### 7.3 定时任务

```python
# backend/app/services/daily_notification_service.py

class DailyNotificationService:
    """每日日程推送服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_due_users(self) -> list[User]:
        """查找当前时间点需要推送的用户"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        return self.db.scalars(
            select(User).where(
                User.daily_notification_enabled == True,
                User.daily_notification_time == current_time,
            )
        ).all()
    
    def notify_user(self, user: User) -> None:
        """向用户推送今日日程 + 天气"""
        # 1. 查日程
        events = self.get_today_events(user.id)
        tasks = self.get_today_tasks(user.id)
        plans = self.get_today_plans(user.id)
        
        # 2. 查天气
        weather = None
        if user.city:
            weather = self.get_weather(user.city)
        
        # 3. 拼消息
        message = self.build_message(
            date=datetime.now(),
            weather=weather,
            events=events,
            tasks=tasks,
            plans=plans,
        )
        
        # 4. 推送
        wechat_service = WechatChannelService(self.db)
        identity = self.get_user_wechat_identity(user.id)
        if identity:
            wechat_service.send_text(
                conversation_id=identity.conversation_id,
                content=message,
            )
```

### 7.4 消息格式模板

```
🌤 早安！今天是 {date:yyyy-MM-dd} {weekday}

📍 {city} 今日天气：{weather_icon} {weather_desc}  {temp_min}~{temp_max}°C
   {weather_tip}

📅 今日日程：
{for event in events}
  • {event.time} - {event.title}  {event.location}
{empty}
  （暂无日程安排）

✅ 待办任务：
{for task in tasks}
  • {task.title}（{task.priority}）
{empty}
  （暂无待办任务）

📌 回复我可调整今日安排～
```

### 7.5 注册定时任务

```python
# backend/app/core/scheduler.py

scheduler.add_job(
    DailyNotificationJob,
    trigger="interval",
    minutes=1,           # 每分钟检查一次
    id="daily_notification",
)
```

## 8. 重连策略

### 8.1 三层防御

| 层 | 机制 | 效果 |
|----|------|------|
| Token 持久化 | bot_token 存入 DB，重启时直接复用 | 进程重启无需重新扫码 |
| 每日推送 | 每天一次 sendmessage，保持活跃 | 确保每天至少有一次交互 |
| 被动检测 -14 | 发送时捕获 session 过期异常 | 发现过期立即标记 |

### 8.2 过期处理

```python
try:
    self.ilink.send_message(...)
except ILinkError as e:
    if e.code == -14:  # session 过期
        self.mark_account_expired(account_id)
        self.notify_admin(f"微信账号 {account_id} session 过期，需重新扫码")
```

### 8.3 恢复方式

第一版：
- token 过期 → 标记 expired → 用户从 Web 重新扫码绑定
- 管理员通过 Web Dashboard 重新生成二维码

后续迭代：
- token 过期 → 自动生成新二维码 → 通过微信消息发给用户
- 用户长按识别扫码 → token 刷新 → 自动恢复

## 9. 数据库变更

### 9.1 WechatLoginSession 表

```sql
ALTER TABLE wechat_login_sessions
  ADD COLUMN qr_img_content TEXT,
  ADD COLUMN qrcode_id VARCHAR(255);
```

### 9.2 User 表（或设置表）

```sql
ALTER TABLE users
  ADD COLUMN daily_notification_enabled BOOLEAN DEFAULT FALSE,
  ADD COLUMN daily_notification_time VARCHAR(5) DEFAULT '08:00',
  ADD COLUMN timezone VARCHAR(64) DEFAULT 'Asia/Shanghai',
  ADD COLUMN city VARCHAR(128);
```

## 10. 文件改动清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `backend/wechat_channel/ilink_client.py` | ILinkClient 协议层，约 300 行 |
| `backend/app/services/daily_notification_service.py` | 每日推送逻辑：查日程、查天气、拼消息 |
| `backend/tests/test_ilink_client.py` | ILinkClient 单元测试 |

### 修改文件

| 文件 | 改动说明 |
|------|---------|
| `backend/app/services/wechat_channel_service.py` | `send_text()` `send_typing()` `get_updates()` `get_config()` 从 mock 改为调 ILinkClient |
| `backend/app/wechat_channel_routes.py` | 新增 `/channel/qr-code`、`/channel/qr-code-status` 路由 |
| `backend/app/api/routes/wechat.py` | 创建登录会话时调 wechat-channel 获取真实二维码，轮询到 confirmed 后自动绑定 |
| `backend/app/core/scheduler.py` | 注册每日推送定时任务 |
| `backend/app/models/channel.py` | WechatLoginSession 加 qr_img_content、qrcode_id 字段 |
| `backend/app/models/user.py` | 加每日推送配置字段 |
| `backend/.env.example` | 加天气 API 配置项 |
| `web/` | 新增加通知设置页；登录页改为展示真实二维码 |

### 无需改动的文件

| 文件 | 原因 |
|------|------|
| `backend/app/services/wechat_channel_adapter.py` | 适配器层不变，只处理标准化消息 |
| `backend/app/schemas/wechat.py` | 入站消息 schema 不变 |
| `backend/app/schemas/wechat_channel.py` | 通道路由 schema 不变 |
| `backend/app/agent/` | Agent 链路不变，不感知底层通道变化 |
| `backend/app/wechat_channel_main.py` | 启动逻辑不变 |

## 11. 开发里程碑

### 阶段 1：ILinkClient 协议层

- [ ] 实现 `ILinkClient` 全部 6 个方法
- [ ] 单元测试（mock iLink 响应）
- [ ] 手动测试：能获取二维码、能发送消息

### 阶段 2：登录流程对接

- [ ] LoginSession 表加字段
- [ ] wechat-channel 新增 QR 码路由
- [ ] Backend 对接真实二维码
- [ ] Web 端展示真实二维码
- [ ] 端到端测试：扫码 → 确认 → 绑定成功

### 阶段 3：长轮询消息接收

- [ ] 实现 PollerThread
- [ ] 消息写入 inbound 表
- [ ] Backend 消费链路验证（去重、适配、Agent）
- [ ] 端到端测试：发微信 → 收到 → Agent 回复

### 阶段 4：消息真实发送

- [ ] send_text 改造：typing + 发送 + 日志
- [ ] send_typing 改造
- [ ] 端到端测试：Agent 回复 → 用户微信收到

### 阶段 5：每日推送 + 天气

- [ ] 用户设置 API + Web 页面
- [ ] 天气 API 集成
- [ ] 日程查询 + 消息拼装
- [ ] 定时任务注册
- [ ] 端到端测试：到点 → 收到推送

## 12. 风险点

1. **iLink 协议可能变化** — 腾讯未公开协议文档，有变更风险
2. **速率限制** — 腾讯未公开限速策略，需要实际测试
3. **扫码登录稳定性** — 每次扫码 bot_id 和 base_url 可能变化
4. **context_token 生命周期** — 必须在回复时原样传回，丢失后消息无法投递
5. **24h 硬限制** — 协议层面无法绕过，每日推送作为保底策略但不保证 100% 续期

## 13. 设计决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| iLink 代码位置 | 嵌入 / 旁路 / 替换 | 嵌入（方案 A） | 改动最小，全部业务代码复用 |
| 重连方式 | 自动发二维码 / 仅标记 expired | 第一版仅标记，后续迭代 | 先跑通核心链路 |
| 天气 API | 和风 / OpenWeatherMap | 和风天气 | 国内更准，免费额度足 |
| 推送检查频率 | 每 1min / 每 5min | 每 1min | 时间精确到分钟 |
