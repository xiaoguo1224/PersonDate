# 系统架构设计文档 v1.0

## 1. 架构结论

本系统采用以下架构：

```text
FastAPI 后端单体服务
+
LangGraph Agent 状态编排
+
PostgreSQL 数据库
+
APScheduler 提醒调度
+
openclaw-weixin 微信消息通道
+
Next.js Web Dashboard
```

系统不使用 OpenClaw Runtime，不使用 OpenClaw Agent 编排能力。`openclaw-weixin` 只作为微信消息收发通道，用于接收微信消息、发送微信回复和发送提醒。

最终架构一句话：

```text
基于 FastAPI + LangGraph 的微信智能日程规划 Agent 系统，
使用 openclaw-weixin 作为微信消息通道，
由自研 Schedule Agent Service 负责用户、权限、Agent、日程、任务、计划、冲突检测、提醒和 Web API。
```

## 2. 核心架构图

```text
┌────────────────────┐
│      微信用户       │
│  发送自然语言消息    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ openclaw-weixin    │
│ 微信消息通道         │
└─────────┬──────────┘
          │
          ▼
┌──────────────────────────────┐
│ WeChat Channel Adapter        │
│ 微信消息适配层                 │
│ 标准化消息 / 身份映射 / 消息发送 │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│ FastAPI Schedule Agent Service│
│ 系统核心后端                  │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│ SchedulePlanningGraph         │
│ LangGraph 状态流 Agent        │
│ 意图识别 / 规划 / 确认 / 回复   │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│ Tool Executor                 │
│ 工具执行器                    │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│ Business Services             │
│ 用户 / 日程 / 任务 / 计划 / 冲突 │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│ PostgreSQL                    │
│ 数据持久化                    │
└──────────────────────────────┘
```

提醒链路：

```text
APScheduler Reminder Worker
  ↓
扫描 reminder_job
  ↓
生成提醒文本
  ↓
WeChat Channel Adapter
  ↓
openclaw-weixin
  ↓
微信用户
```

Web 链路：

```text
Next.js Web Dashboard
  ↓
FastAPI REST API
  ↓
PostgreSQL
```

## 3. 架构边界

### 3.1 openclaw-weixin 的边界

openclaw-weixin 只负责微信消息通道。

它负责：

1. 接收微信文本消息。
2. 将微信消息传递给本系统。
3. 接收本系统的出站消息。
4. 向微信用户发送文本回复。
5. 向微信用户发送提醒消息。

它不负责：

1. Agent 逻辑。
2. 日程业务。
3. 任务规划。
4. 冲突检测。
5. 用户系统。
6. 权限系统。
7. Web Dashboard。
8. 数据库管理。

### 3.2 FastAPI 后端的边界

FastAPI 后端是系统核心。

它负责：

1. 接收 openclaw-weixin 转发来的微信消息。
2. 标准化微信消息。
3. 根据微信身份映射系统用户。
4. 运行 SchedulePlanningGraph。
5. 执行 Agent 工具。
6. 管理用户、邀请码、权限。
7. 管理日程、任务、每日计划、冲突事项。
8. 管理提醒任务。
9. 向 openclaw-weixin 发送微信回复和提醒。
10. 提供 Web Dashboard API。

### 3.3 LangGraph 的边界

LangGraph 只负责 Agent 状态流编排。

它负责：

1. 多轮对话状态流。
2. 用户确认流程。
3. 不同意图的流程分支。
4. 创建日程、创建任务、规划一天、确认草案、修改、删除等流程的节点编排。
5. Agent 执行路径清晰化。

它不负责：

1. 数据库 CRUD。
2. 权限校验。
3. 微信消息发送。
4. 精确冲突算法。
5. Web API。

### 3.4 LLM 的边界

LLM 负责自然语言理解和回复生成。

LLM 负责：

1. 理解用户自然语言。
2. 提取日程、任务、时间、地点、约束。
3. 判断用户意图。
4. 给出规划建议。
5. 生成适合微信发送的自然语言回复。

LLM 不负责：

1. 直接写数据库。
2. 直接决定 user_id。
3. 精确判断时间冲突。
4. 绕过工具修改数据。
5. 直接发送微信消息。

精确冲突检测必须由程序确定性算法完成。

## 4. 技术栈

### 4.1 后端

```text
FastAPI
Python 3.11+
Pydantic v2
SQLAlchemy 2.0
Alembic
PostgreSQL
LangGraph
OpenAI-compatible SDK
APScheduler
JWT + RBAC
argon2 / bcrypt
structlog / logging
```

### 4.2 前端

```text
Next.js
React
TypeScript
Ant Design
FullCalendar 或自定义时间轴组件
```

### 4.3 微信通道

```text
openclaw-weixin
自研 WeChat Channel Adapter
```

### 4.4 部署

```text
Docker Compose
```

服务组成：

```text
backend
web-dashboard
postgres
wechat-channel
```

## 5. 后端模块划分

FastAPI 后端建议分为以下模块：

```text
app/
  api/
    routes/
      auth.py
      invite_codes.py
      users.py
      wechat.py
      channel_identity.py
      calendar_events.py
      tasks.py
      day_plans.py
      conflicts.py
      reminders.py
      agent_logs.py
      settings.py

  agent/
    graph.py
    state.py
    nodes/
      load_context.py
      check_pending_state.py
      classify_intent.py
      extract_info.py
      route_intent.py
      handle_create_event.py
      handle_query_events.py
      handle_create_task.py
      handle_plan_day.py
      handle_update_event.py
      handle_delete_event.py
      handle_confirm.py
      detect_conflicts.py
      generate_response.py
    prompts/
    llm_client.py

  tools/
    registry.py
    executor.py
    create_event.py
    query_events.py
    update_event.py
    delete_event.py
    search_event_candidates.py
    create_task.py
    query_tasks.py
    analyze_day.py
    find_free_slots.py
    plan_tasks_into_day.py
    detect_conflicts.py
    suggest_reschedule.py
    confirm_plan.py
    ask_user_clarification.py

  services/
    auth_service.py
    invite_code_service.py
    user_service.py
    channel_identity_service.py
    calendar_event_service.py
    task_service.py
    day_plan_service.py
    conflict_service.py
    reminder_service.py
    agent_log_service.py
    system_setting_service.py
    wechat_channel_service.py

  workers/
    reminder_worker.py

  models/
  schemas/
  db/
  core/
```

## 6. 核心模块职责

### 6.1 WeChat Channel Adapter

职责：

1. 接收 openclaw-weixin 原始消息。
2. 标准化为系统内部消息。
3. 记录 `channel_message_log`。
4. 根据 `channel_user_id` / `conversation_id` 查找 `channel_identity`。
5. 如果用户未绑定，返回绑定提示。
6. 如果用户已绑定，将消息交给 SchedulePlanningGraph。
7. 接收 Agent `final_response`。
8. 调用 openclaw-weixin 发送微信消息。

标准入站消息：

```json
{
  "channel": "wechat",
  "message_id": "wx_msg_001",
  "conversation_id": "wx_user_001",
  "channel_user_id": "wx_user_001",
  "display_name": "用户昵称",
  "content_type": "text",
  "content": "明天下午 3 点开会",
  "raw_payload": {},
  "received_at": "2026-06-04T20:30:00+08:00"
}
```

标准出站消息：

```json
{
  "channel": "wechat",
  "conversation_id": "wx_user_001",
  "content_type": "text",
  "content": "已为你创建日程：开会，时间为明天下午 3 点。"
}
```

### 6.2 SchedulePlanningGraph

负责 Agent 流程。

核心状态：

```text
user_id
conversation_id
channel
input_text
current_time
timezone
user_settings
pending_state
intent
extracted
candidate_events
events
tasks
conflicts
draft_plan
tool_results
final_response
error
```

核心节点：

```text
load_context
check_pending_state
classify_intent
extract_info
route_intent
handle_create_event
handle_query_events
handle_create_task
handle_plan_day
handle_update_event
handle_delete_event
handle_confirm
detect_conflicts
save_pending_state
generate_response
save_agent_log
```

### 6.3 Tool Executor

职责：

1. 根据 `tool_name` 找到对应工具。
2. 自动注入 `user_id`。
3. 校验工具参数。
4. 调用业务服务。
5. 返回工具结果。
6. 记录工具调用过程。

工具执行不能信任模型输出的 `user_id`，`user_id` 必须来自系统上下文。

### 6.4 Business Services

业务服务负责确定性业务逻辑。

包括：

```text
AuthService
InviteCodeService
UserService
ChannelIdentityService
CalendarEventService
TaskService
DayPlanService
ConflictService
ReminderService
AgentLogService
SystemSettingService
WechatChannelService
```

其中：

```text
ConflictService 负责精确冲突检测。
ReminderService 负责 reminder_job 创建、更新和取消。
WechatChannelService 负责调用 openclaw-weixin 的发送能力。
```

### 6.5 Reminder Worker

职责：

1. APScheduler 定时扫描 `reminder_jobs`。
2. 找到 `status = pending` 且 `trigger_time <= now()` 的提醒。
3. 读取目标日程、任务或计划项。
4. 生成提醒文本。
5. 调用 WeChat Channel Adapter 发送微信消息。
6. 成功后更新 `status = fired`。
7. 失败后 `retry_count + 1`。
8. 超过最大重试次数后标记 `failed`。
9. 周期任务生成下一次 `reminder_job`。

提醒不经过 LLM。

## 7. Agent 图流程设计

### 7.1 总流程

```text
微信消息 / Debug API 消息
  ↓
load_context
  ↓
check_pending_state
  ↓
classify_intent
  ↓
extract_info
  ↓
route_intent
  ↓
具体业务分支
  ↓
detect_conflicts
  ↓
generate_response
  ↓
save_agent_log
  ↓
返回回复
```

### 7.2 创建固定日程流程

```text
handle_create_event
  ↓
create_event 工具
  ↓
detect_conflicts 工具
  ↓
create_reminder 工具
  ↓
generate_response
```

如果无冲突，自动创建并回复。

如果存在冲突，保存 `pending_state`，并让用户选择处理方案。

### 7.3 创建弹性任务并规划流程

```text
handle_create_task
  ↓
create_task 工具
  ↓
analyze_day 工具
  ↓
find_free_slots 工具
  ↓
plan_tasks_into_day 工具
  ↓
detect_conflicts 工具
  ↓
save_pending_state
  ↓
generate_response
```

复杂规划只生成草案，不直接写入正式计划。

### 7.4 用户确认流程

当存在 `pending_state` 时，用户输入：

```text
确认
取消
1
2
3
调整
```

系统优先进入 `handle_confirm`，而不是重新识别普通意图。

## 8. 权限架构

角色：

```text
owner
member
```

owner 可访问系统设置、模型配置、微信通道状态、全局日志、用户管理、邀请码管理、自己的日程 Agent 功能。

member 只能访问自己的日程、任务、每日计划、冲突事项、提醒、Agent 日志和个人设置。

Agent 工具调用必须自动注入当前 `user_id`。所有工具必须限制：

```text
calendar_events.user_id = 当前用户
task_items.user_id = 当前用户
day_plans.user_id = 当前用户
schedule_conflicts.user_id = 当前用户
reminder_jobs.user_id = 当前用户
agent_pending_states.user_id = 当前用户
```

## 9. 微信身份绑定

绑定流程：

```text
用户通过邀请码注册系统账号
  ↓
登录 Web Dashboard
  ↓
生成微信绑定码
  ↓
用户在微信中发送：绑定 123456
  ↓
WeChat Channel Adapter 验证绑定码
  ↓
写入 channel_identities
```

绑定后，微信消息才能进入 Agent。

未绑定用户发送消息时，系统回复：

```text
你还没有绑定账号，请先在 Web 中使用邀请码注册并绑定微信。
```

被禁用用户发送消息时，系统回复：

```text
你的账号当前不可用，请联系系统主用户。
```

## 10. 部署架构

推荐 Docker Compose：

```text
services:
  backend:
    FastAPI Schedule Agent Service

  web:
    Next.js Web Dashboard

  postgres:
    PostgreSQL

  wechat-channel:
    openclaw-weixin 运行环境 / 消息通道
```

后端内部包含：

```text
FastAPI API Server
SchedulePlanningGraph
Tool Executor
Business Services
APScheduler Reminder Worker
```

不拆微服务。

原因：

1. 自用项目，部署简单优先。
2. 单体后端更容易维护。
3. 数据库事务更简单。
4. Agent、提醒、Web API 之间共享业务逻辑。
5. 后续不计划大规模迭代，不需要过早微服务化。

## 11. 日志与可观测性

业务日志存数据库，用于 Web 展示：

```text
channel_message_logs
agent_run_logs
reminder_jobs
invite_code_usages
```

运行日志用于排查问题：

```text
FastAPI 运行日志
Agent 执行异常
LLM 调用异常
微信通道异常
提醒发送异常
数据库异常
```

owner 可查看全局业务日志，member 只能查看自己的日志。

## 12. 安全设计

1. Web 使用 JWT 登录认证。
2. 密码使用 argon2 或 bcrypt 哈希。
3. RBAC 控制 owner / member 权限。
4. 所有业务数据按 user_id 隔离。
5. API Key 等敏感配置不向 member 暴露。
6. Agent 工具调用不信任模型输出的 user_id。
7. 微信消息必须先映射到系统用户。
8. 未绑定微信用户不能使用 Agent。
9. 被禁用用户不能登录，也不能通过微信使用 Agent。

## 13. 架构最终确认

最终确定：

1. 后端使用 FastAPI。
2. Agent 状态流使用 LangGraph。
3. 不使用 LangChain Agent。
4. 不使用 OpenClaw Runtime。
5. openclaw-weixin 只作为微信消息通道。
6. Agent、业务、权限、数据库、Web API 全部由自研 FastAPI 后端实现。
7. LLM 调用使用 OpenAI-compatible SDK。
8. 日程冲突检测使用确定性程序算法。
9. 提醒使用 APScheduler，不经过 LLM。
10. Web Dashboard 使用 Next.js + Ant Design。
11. 系统采用单体后端 + 多模块架构，不拆微服务。
