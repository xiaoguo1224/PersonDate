# 自研微信通道服务设计说明

## 目标

实现一套独立的微信通道服务，协议形态参考 Tencent 官方 `openclaw-weixin` 插件的消息交互方式，但不依赖 OpenClaw Runtime，不依赖 OpenClaw Agent 编排，也不要求安装 OpenClaw CLI。

这套通道服务的职责是：

1. 管理微信账号的扫码登录会话。
2. 保存账号凭证、游标、状态和错误信息。
3. 向上游 FastAPI 转发标准化后的微信消息。
4. 接收 FastAPI 的回复，并把消息发回微信。
5. 支持提醒任务主动发送微信消息。

## 设计边界

### 通道服务负责什么

- 二维码登录会话。
- 账号绑定、解绑、启用、停用。
- `getupdates` 长轮询。
- `sendmessage` 出站发送。
- `getconfig` / `sendtyping` 这类协议扩展。
- 消息去重、游标推进、状态收敛。
- 记录微信通道侧的消息日志。

### 通道服务不负责什么

- 日程、任务、每日计划、冲突检测。
- Agent 状态流编排。
- LLM 调用。
- 用户权限与 RBAC。
- 业务数据 CRUD。

## 对外协议

通道服务对内对外都保持稳定的 HTTP JSON 形态，至少包含以下接口：

```text
POST /getupdates
POST /sendmessage
POST /getconfig
POST /sendtyping
```

其中：

- `getupdates` 负责拉取微信增量消息。
- `sendmessage` 负责发送文本回复和提醒消息。
- `getconfig` 负责返回账号侧配置。
- `sendtyping` 负责可选的输入状态提示。

## 与 FastAPI 的关系

FastAPI 是系统主后端，负责：

- 接收来自通道服务的标准化消息。
- 将消息交给 `SchedulePlanningGraph`。
- 执行工具调用和业务写入。
- 返回最终自然语言回复。

通道服务只做消息收发与账号状态管理，不参与 Agent 逻辑。

## `WECHAT_CHANNEL_BASE_URL` 的含义

`WECHAT_CHANNEL_BASE_URL` 表示 **我们自己部署的微信通道服务地址**，不是 OpenClaw gateway，也不是扫码结果。

典型示例：

```text
http://localhost:18789
```

如果该值为空，说明当前环境没有配置可用的微信通道服务。此时：

- 后端可以继续启动。
- `wechat-channel` 进程可以空闲运行。
- 真实微信收发不会启用。

## 账号与数据模型

建议至少保留以下对象：

```text
wechat_login_sessions
wechat_accounts
channel_identities
channel_message_logs
```

其中：

- `wechat_login_sessions` 保存二维码登录会话状态。
- `wechat_accounts` 保存通道账号凭证、游标、状态和备注。
- `channel_identities` 保存微信身份与系统用户映射。
- `channel_message_logs` 保存入站、出站、错误、重试和上下文信息。

## 运行流程

### 入站

```text
微信用户
  ↓
微信通道服务
  ↓ getupdates
标准化消息
  ↓
FastAPI /api/wechat/inbound
  ↓
SchedulePlanningGraph
  ↓
业务服务
  ↓
最终回复
  ↓
微信通道服务 sendmessage
  ↓
微信用户
```

### 出站提醒

```text
APScheduler Reminder Worker
  ↓
ReminderService
  ↓
FastAPI WeChat Adapter
  ↓
微信通道服务 sendmessage
  ↓
微信用户
```

## 错误处理

- `getupdates` 鉴权失败时，将账号标记为 `expired`。
- 网络异常时，将账号标记为 `error`。
- `sendmessage` 失败时记录 `retry_count`、`error_code`、`error_message`。
- 消息处理失败时不能影响下一条消息的拉取。

## 实现原则

1. Agent 先行，通道后置。
2. 通道协议参考官方插件，但实现必须自研。
3. 不依赖 OpenClaw Runtime。
4. 不让 Agent 直接接触通道底层协议。
5. 不把 `user_id` 交给 LLM 决定。

