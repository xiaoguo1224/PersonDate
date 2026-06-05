# 微信通道接入文档 v2.0

## 1. 接入目标

本系统使用自研的微信通道服务，不依赖外部运行时，也不使用外部 Agent 编排能力。

微信通道目标：

1. 通过二维码登录绑定微信账号。
2. 持久化保存通道账号凭证、游标和连接状态。
3. 接收微信文本消息并转发给 FastAPI 后端。
4. 接收 FastAPI 后端生成的回复并发送给微信用户。
5. 支持 APScheduler Reminder Worker 主动发送提醒消息。

## 2. 总体链路

```text
微信用户
  ↓ 扫码登录
自研微信通道服务
  ↓ 标准化消息 / 维护游标 / 保存凭证
WeChat Channel Adapter
  ↓ POST /api/wechat/inbound
FastAPI Schedule Agent Service
  ↓ SchedulePlanningGraph
  ↓ final_response
WeChat Channel Adapter
  ↓ sendmessage
自研微信通道服务
  ↓
微信用户
```

提醒链路：

```text
APScheduler Reminder Worker
  ↓
ReminderService
  ↓
WechatChannelService
  ↓ sendmessage
自研微信通道服务
  ↓
微信用户
```

## 3. WeChat Channel Adapter 职责

WeChat Channel Adapter 是本项目封装的通道适配层。

职责：

1. 适配微信通道服务的消息格式。
2. 转换为系统标准入站消息。
3. 调用 FastAPI 的 `/api/wechat/inbound`。
4. 接收后端返回的 reply。
5. 调用微信通道服务发送消息。
6. 为 Reminder Worker 提供发送接口。
7. 记录发送结果、账号状态和同步游标。

## 4. 微信账号绑定流程

通道账号绑定采用二维码登录，不通过微信内发送绑定码。

完整流程：

```text
用户在 Web 中点击“绑定微信”
  ↓
后端请求二维码登录信息
  ↓
前端展示二维码
  ↓
用户使用微信扫码并确认
  ↓
后端轮询登录状态
  ↓
获取 bot_token、account_id、base_url
  ↓
调用 `POST /api/me/wechat-login-sessions/{id}/confirm`
  ↓
保存账号凭证
  ↓
启动该账号的消息监听器
```

登录状态机：

```text
INIT
  ↓
QR_CREATED
  ↓
WAIT_SCAN
  ↓
SCANNED
  ↓
CONFIRMED
  ↓
BOUND
```

异常状态：

```text
WAIT_SCAN / SCANNED
  ↓
EXPIRED
  ↓
重新生成二维码
```

## 5. 通道账号持久化

绑定成功后，至少保存以下信息：

```text
account_id
wechat_user_id
owner_user_id
bot_token
base_url
cursor
status
bind_time
last_active_time
remark
```

建议的持久化结构：

```text
wechat_accounts
  - id
  - account_id
  - wechat_user_id
  - owner_user_id
  - bot_token
  - base_url
  - status
  - cursor
  - remark
  - bind_time
  - last_active_time
  - created_at
  - updated_at
```

开发阶段可以先落库，正式环境中 `bot_token` 需要加密保存。

## 6. 消息监听

绑定成功后，系统为该账号启动消息监听器。

处理流程：

```text
读取所有 active 微信账号
  ↓
每个账号启动一个 Poller
  ↓
Poller 携带该账号 bot_token 调用 getupdates
  ↓
拿到 msgs 和新的 get_updates_buf
  ↓
逐条消息进入处理队列
  ↓
调用 Agent
  ↓
回复用户
```

要求：

1. 一个账号一个 poller。
2. 一个账号一个 cursor。
3. 每次成功拉取新 cursor 后立即持久化。
4. 服务重启后不得重复处理已确认消息。

## 7. getupdates 长轮询

`getupdates` 是长轮询接口，不是 webhook。

流程：

```text
第一次请求：get_updates_buf = ""
后续请求：get_updates_buf = 上一次响应里的新游标
```

必须保存同步游标，否则会出现以下问题：

1. 服务重启后重复收到旧消息。
2. 服务重启期间可能漏消息。

## 8. 消息标准化

微信原始消息不能直接传给 Agent，必须先标准化。

标准入站消息建议包含：

```text
message_id
from_user_id
to_user_id
session_id
conversation_id
channel_user_id
display_name
content_type
content
context_token
raw_payload
```

系统内部标准输入建议为：

```json
{
  "channel": "wechat",
  "account_id": "wx_account_001",
  "user_id": "system_user_uuid",
  "conversation_id": "wechat:wx_account_001:wx_user_001",
  "message_id": "wx_msg_001",
  "message_type": "text",
  "text": "明天下午 3 点开会",
  "raw_message": {}
}
```

## 9. 文本消息处理流程

第一版优先处理文本消息。

处理流程：

```text
收到 msg
  ↓
检查 message_id 是否已处理
  ↓
提取文本内容
  ↓
如果文本为空，返回“暂时只支持文本消息”
  ↓
组装 Agent 输入
  ↓
调用 Agent
  ↓
拿到回复
  ↓
调用 sendmessage
```

## 10. 调用 Agent

Agent 统一暴露一个调用入口。

输入结构：

```text
channel
account_id
user_id
conversation_id
message_id
message
metadata
```

输出结构：

```text
reply_text
actions
need_followup
status
```

Agent 不应返回微信专用结构，只返回“说什么”和“做了什么”。

## 11. 会话 ID 设计

建议按账号和发送者隔离会话：

```text
私聊：
wechat:{account_id}:{from_user_id}:{session_id}

群聊：
wechat:{account_id}:{group_id}:{from_user_id}:{session_id}
```

如果后续支持多个通道账号，必须把 `account_id` 加入会话键，避免不同账号之间串会话。

## 12. 回复消息

回复消息时必须保留原始消息里的 `context_token`。

发送流程：

```text
Agent 返回 reply_text
  ↓
检查 reply_text 是否为空
  ↓
如果为空，使用兜底回复
  ↓
构造 sendmessage 请求
  ↓
带上 to_user_id
  ↓
带上 context_token
  ↓
发送文本 item
  ↓
记录发送结果
```

发送失败时记录：

```text
account_id
message_id
to_user_id
context_token
reply_text
retry_count
error_code
error_message
```

## 13. 去重机制

必须基于以下组合去重：

```text
account_id + message_id
```

处理流程：

```text
收到消息
  ↓
检查 message_id 是否存在
  ↓
如果存在，直接跳过
  ↓
如果不存在，写入处理中状态
  ↓
调用 Agent
  ↓
发送回复
  ↓
标记处理完成
```

建议使用 Redis 或数据库唯一约束实现。

## 14. 异常处理

### 14.1 token 失效

表现：

```text
getupdates 返回 session timeout 或鉴权失败
```

处理：

```text
账号状态改为 expired
停止该账号 poller
通知管理员重新扫码绑定
```

### 14.2 二维码过期

表现：

```text
扫码状态返回 expired
```

处理：

```text
前端提示二维码已过期
自动重新生成二维码
或者让用户手动刷新
```

### 14.3 Agent 超时

处理：

```text
先回复：我已收到，正在处理
后台继续执行
完成后再补发结果
```

### 14.4 sendmessage 失败

处理：

```text
短暂网络错误：重试 1-3 次
鉴权错误：标记账号失效
上下文错误：记录失败，不要无限重试
```

## 15. 账号管理

至少支持：

```text
查看已绑定账号
绑定新微信账号
解绑账号
重新扫码
启用账号
停用账号
查看账号状态
查看最后收消息时间
查看最后错误
```

账号状态建议：

```text
active
binding
expired
disabled
error
```

多个微信账号时，每个账号独立：

```text
独立 token
独立 cursor
独立 poller
独立错误状态
独立消息去重
```

## 16. 访问控制

建议先做白名单或授权控制。

处理流程：

```text
收到消息
  ↓
检查 from_user_id 是否在白名单
  ↓
不在白名单：返回“当前账号未授权”
  ↓
在白名单：进入 Agent
```

对于日程 Agent，权限尤其重要。普通用户只能操作自己的日程，管理员可以查看全局状态。

## 17. 与日程 Agent 的结合

用户消息：

```text
明天下午三点提醒我开会
```

通道层只做：

```text
提取文本
附加元信息
交给 Agent
```

Agent 负责：

```text
识别意图
解析时间
抽取事项
判断缺失信息
调用日程工具
返回结果
```

## 18. 推荐运行流程

```text
服务启动
  ↓
加载所有微信账号
  ↓
过滤 active 账号
  ↓
为每个账号启动 poller
  ↓
poller 调用 getupdates
  ↓
收到消息
  ↓
消息去重
  ↓
权限检查
  ↓
消息标准化
  ↓
投递到 Agent
  ↓
Agent 执行业务
  ↓
生成回复
  ↓
sendmessage 回复
  ↓
记录日志
  ↓
继续 getupdates
```

扫码绑定流程是独立的：

```text
用户发起绑定
  ↓
生成二维码
  ↓
展示二维码
  ↓
轮询扫码状态
  ↓
确认成功
  ↓
保存 token
  ↓
启动该账号 poller
```

## 19. 数据表建议

建议至少有以下数据对象：

```text
wechat_accounts
  - 账号凭证、游标、状态、备注

wechat_login_sessions
  - 二维码、会话状态、过期时间

channel_identities
  - 系统用户与微信身份映射

wechat_message_logs
  - 入站、出站消息、context_token、retry_count、error_code、处理状态

wechat_send_logs
  - 发送结果与错误信息

wechat_allowed_users
  - 通道白名单
```

## 20. 开发里程碑

建议分 5 个阶段：

### 阶段 1：绑定成功

目标：

```text
能展示二维码
能扫码
能拿到 token
能保存账号
```

### 阶段 2：能收到消息

目标：

```text
用 getupdates 拉消息
打印原始消息
保存 cursor
```

### 阶段 3：能回复固定文本

目标：

```text
收到任何文本都回复：我收到了
```

### 阶段 4：接入 Agent

目标：

```text
把微信文本传给 Agent
把 Agent 输出发回微信
```

### 阶段 5：生产增强

目标：

```text
去重
白名单
多账号
异常重试
token 失效重绑
日志
监控
```

## 21. 风险点

1. 扫码登录协议和通道后端接口可能发生变化。
2. 长轮询服务必须常驻，不能只部署普通 HTTP 接口。
3. `context_token` 丢失会影响回复上下文。
4. 权限控制必须先做，否则任何通道用户都可能操作日程。

## 22. 最终推荐方案

最适合本项目的方案是：

```text
不把 Agent 绑死在微信协议里。
新增一个独立微信通道服务。
通道服务负责扫码登录、凭证保存、长轮询、消息标准化和消息发送。
FastAPI 只处理标准化后的消息和业务结果。
```

一句话总结：**你不是要把 Agent 直接塞进微信协议里，而是要在 Agent 外面做一层独立的微信通道服务，负责扫码登录、拉消息、标准化、发消息和状态管理。**

推荐通过 `WECHAT_CHANNEL_BASE_URL` 配置独立微信通道服务地址，由 `wechat-channel` 进程启动时初始化 `wechat_sender` 和 `wechat_updates_client`，并由 APScheduler 常驻轮询活跃账号。

在 Docker 编排中，建议把长轮询逻辑放到独立的 `wechat-channel` 进程里运行，backend 仅保留业务 API 和提醒调度，避免两处同时轮询同一批账号。
