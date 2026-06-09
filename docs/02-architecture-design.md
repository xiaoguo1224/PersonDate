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
Redis 缓存层
+
APScheduler 提醒调度
+
自研微信通道服务
+
Next.js Web Dashboard
```

系统不依赖外部 Agent Runtime，也不使用外部 Agent 编排能力。自研微信通道服务只作为微信消息收发通道，用于接收微信消息、发送微信回复和发送提醒。

最终架构一句话：

```text
基于 FastAPI + LangGraph 的微信智能日程规划 Agent 系统，
使用自研微信通道服务作为微信消息通道，
由自研 Schedule Agent Service 负责用户、权限、Agent、安排、待办、计划、冲突检测、提醒和 Web API。
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
│ 自研微信通道服务      │
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
│ Redis                        │
│ 查询缓存层                    │
│ 写时失效 + TTL 兜底           │
└─────────┬────────────────────┘
          │ (cache miss)
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
│ Redis                        │
│ 查询缓存层                    │
│ 写时失效 + TTL 兜底           │
└─────────┬────────────────────┘
          │ (cache miss)
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
自研微信通道服务
  ↓
微信用户
```

Web 链路：

```text
Next.js Web Dashboard
  ↓
FastAPI REST API
  ↓
Redis 缓存层 (写时失效 + TTL 兜底)
  ↓
PostgreSQL
```

## 3. 架构边界

### 3.1 微信通道服务的边界

微信通道服务只负责微信消息通道。

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

1. 接收微信通道服务转发来的微信消息。
2. 标准化微信消息。
3. 根据微信身份映射系统用户。
4. 运行 SchedulePlanningGraph。
5. 执行 Agent 工具。
6. 管理用户、邀请码、权限。
7. 管理日程、任务、每日计划、冲突事项。
8. 管理提醒任务。
9. 向微信通道服务发送微信回复和提醒。
10. 提供 Web Dashboard API。

### 3.3 LangGraph 的边界

LangGraph 负责 Agent 状态流编排，采用 ReAct Agent 模式。

它负责：

1. ReAct 循环（agent ↔ tools）编排。
2. 多轮对话状态管理。
3. 用户确认流程（interrupt 机制）。
4. 工具调用路由和执行。
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
2. 提取安排、待办、时间、地点、约束。
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
Redis 7+
LangGraph
langchain_openai.ChatOpenAI
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
自研微信通道服务
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
redis
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
    graph.py          -- LangGraph ReAct Agent 图定义、AgentState、节点、条件路由
    tools.py          -- LangChain @tool 工具定义（18 个工具）
    security.py       -- InputSanitizer、ContentFilter、ToolCallGuard、ToolResultSanitizer、OutputSanitizer

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

1. 接收微信通道服务原始消息。
2. 标准化为系统内部消息。
3. 记录 `channel_message_log`。
4. 根据 `channel_user_id` / `conversation_id` 查找 `channel_identity`。
5. 如果用户未绑定，返回绑定提示。
6. 如果用户已绑定，将消息交给 SchedulePlanningGraph。
7. 接收 Agent `final_response`。
8. 调用微信通道服务发送微信消息。

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
  "content": "已为你创建安排：开会，时间为明天下午 3 点。"
}
```

### 6.2 SchedulePlanningGraph

负责 Agent 流程。采用 LangGraph ReAct Agent 模式。

核心状态（TypedDict）：

```text
messages          -- 对话消息列表（LangGraph 消息追加合并）
user_id
conversation_id
timezone
current_time
user_settings
tool_calls
tool_results
needs_confirmation
confirmation_prompt
confirmed_action
```

核心节点：

```text
agent             -- ReAct 循环节点，调用 LLM 推理
tools             -- ToolNode，执行工具调用
human             -- interrupt 确认节点
```

图结构：

```text
START → agent ↔ tools → human（条件） → END
```

与旧架构区别：不再使用独立的意图分类、信息抽取、路由节点，LLM 通过 ReAct 循环自主理解意图并调用工具。

### 6.3 工具系统

当前架构使用 LangChain `@tool` 装饰器定义工具，定义在 `backend/app/agent/tools.py`。由 LangGraph 内置 `ToolNode` 负责执行。

职责：

1. 工具通过 `@tool` 装饰器定义，LangChain 框架自动处理参数校验。
2. `user_id` 和 `conversation_id` 由系统上下文自动注入。
3. 工具内部调用业务服务完成实际操作。
4. 工具调用记录写入 `agent_run_logs`。

与旧架构区别：不再使用 `ToolRegistry` + `ToolExecutor` 模式，改为 LangChain 原生工具系统。

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
WechatChannelService 负责调用微信通道服务的发送能力。
```

### 6.5 Reminder Worker

职责：

1. APScheduler 定时扫描 `reminder_jobs`。
2. 找到 `status = pending` 且 `trigger_time <= now()` 的提醒。
3. 读取目标安排、待办或安排项。
4. 生成提醒文本。
5. 调用 WeChat Channel Adapter 发送微信消息。
6. 成功后更新 `status = fired`。
7. 失败后 `retry_count + 1`。
8. 超过最大重试次数后标记 `failed`。
9. 周期任务生成下一次 `reminder_job`。

提醒不经过 LLM。

### 6.6 Redis 缓存层

Redis 作为查询缓存层，位于 Business Services 与 PostgreSQL 之间。

缓存覆盖范围：

```text
日程查询
任务列表
冲突记录
提醒任务
系统设置
用户配置
天气数据
Agent 状态
```

缓存策略：

```text
写时失效：业务服务写入数据库后，主动清除相关缓存键
TTL 兜底：缓存键设置 10-60 分钟过期，防止脏数据长期驻留
自动降级：Redis 不可用时，自动降级为直接查询数据库，不影响业务可用性
```

缓存键命名规范：

```text
cache:{resource}:{user_id}:{query_hash}
```

示例：

```text
cache:events:user123:date_range:2026-06-08
cache:tasks:user123:status:pending
cache:settings:global
cache:weather:city:Shanghai
```

## 7. Agent 图流程设计

### 7.1 总流程

```text
微信消息 / Debug API 消息
  ↓
注入系统上下文（user_id, current_time, timezone, user_settings）
  ↓
agent 节点（LLM ReAct 推理）
  ↔
tools 节点（执行工具调用）
  ↓
human 节点（条件：needs_confirmation 时 interrupt 等待用户确认）
  ↓
返回最终回复
```

### 7.2 创建固定安排流程

```text
agent 节点：LLM 理解用户意图，调用 create_scheduled_item 工具
  ↓
tools 节点：执行创建，自动检测冲突
  ↓
agent 节点：根据结果决定是否需要创建提醒
  ↓
返回创建结果
```

如果无冲突，自动创建并回复。如果存在冲突，LLM 将冲突信息反馈给用户并询问处理方案。

### 7.3 创建弹性任务并规划流程

```text
agent 节点：LLM 理解意图，调用 create_task 创建任务
  ↓
agent 节点：调用 analyze_day / find_free_slots / plan_tasks_into_day
  ↓
agent 节点：调用 detect_conflicts
  ↓
needs_confirmation = True → human 节点 interrupt 等待确认
  ↓
用户确认后恢复执行
```

复杂规划只生成草案，不直接写入正式计划。

### 7.4 用户确认流程

当 LLM 判断需要用户确认时：

1. 设置 `needs_confirmation = True` 和 `confirmation_prompt`。
2. 进入 `human` 节点，`interrupt()` 暂停图执行。
3. 用户回复后通过 `Command(resume=...)` 恢复。
4. LLM 根据用户回复继续处理。

## 8. 权限架构

角色：

```text
owner
member
```

owner 可访问系统设置、模型配置、微信通道状态、全局日志、用户管理、邀请码管理、自己的安排 Agent 功能。

member 只能访问自己的安排、待办、每日安排、冲突事项、提醒、Agent 日志和个人设置。

Agent 工具调用必须自动注入当前 `user_id`。所有工具必须限制：

```text
scheduled_items.user_id = 当前用户
task_items.user_id = 当前用户
day_plans.user_id = 当前用户
schedule_conflicts.user_id = 当前用户
reminder_jobs.user_id = 当前用户
```

## 9. 微信身份绑定

绑定流程：

```text
用户通过邀请码注册系统账号
  ↓
登录 Web Dashboard
  ↓
创建微信二维码登录会话
  ↓
用户使用微信扫码并确认
  ↓
WeChat Channel Adapter 轮询登录状态并获取通道凭证
  ↓
写入 `wechat_accounts` 和 `channel_identities`
```

绑定后，微信消息才能进入 Agent。

未绑定用户发送消息时，系统回复：

```text
你还没有绑定账号，请先在 Web 中创建二维码登录会话并完成微信确认。
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

  redis:
    Redis 缓存层

  wechat-channel:
    自研微信通道服务 / 长轮询与消息转发进程
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

### 12.1 基础安全

1. Web 使用 JWT 登录认证。
2. 密码使用 argon2 或 bcrypt 哈希。
3. RBAC 控制 owner / member 权限。
4. 所有业务数据按 user_id 隔离。
5. API Key 等敏感配置不向 member 暴露。
6. Agent 工具调用不信任模型输出的 user_id。
7. 微信消息必须先映射到系统用户。
8. 未绑定微信用户不能使用 Agent。
9. 被禁用用户不能登录，也不能通过微信使用 Agent。

### 12.2 Agent 安全防护

Agent 实现 5 层安全防御机制：

```text
用户输入
  ↓
InputSanitizer（输入消毒）
  - 检测 prompt 注入攻击
  - 限制输入长度（最大 2000 字符）
  - 关键词和正则模式匹配
  ↓
LLM 处理
  ↓
ToolCallGuard（工具调用守卫）
  - 高风险工具需要用户确认
  - 验证 confirmed_action 参数
  ↓
ContentFilter（内容过滤）
  - 过滤写入工具参数中的注入内容
  - 截断过长的文本字段
  - 替换检测到的注入内容为 [已过滤]
  ↓
ToolResultSanitizer（工具结果消毒）
  - 为用户数据添加安全标记
  - 防止工具结果被误解为系统指令
  ↓
OutputSanitizer（输出消毒）
  - 检测并过滤系统提示词泄露
  - 替换泄露内容为安全提示
  ↓
最终回复
```

安全防护组件：

```text
InputSanitizer - 输入消毒器
ContentFilter - 内容过滤器
ToolCallGuard - 工具调用守卫
ToolResultSanitizer - 工具结果消毒器
OutputSanitizer - 输出消毒器
```

## 13. 架构最终确认

最终确定：

1. 后端使用 FastAPI。
2. Agent 状态流使用 LangGraph。
3. 使用 LangGraph ReAct Agent 模式（agent ↔ tools 循环）。
4. 不使用外部 Agent Runtime。
5. 微信通道只作为消息通道。
6. Agent、业务、权限、数据库、Web API 全部由自研 FastAPI 后端实现。
7. LLM 调用使用 langchain_openai.ChatOpenAI。
8. 安排冲突检测使用确定性程序算法。
9. 提醒使用 APScheduler，不经过 LLM。
10. Web Dashboard 使用 Next.js + Ant Design。
11. 系统采用单体后端 + 多模块架构，不拆微服务。
