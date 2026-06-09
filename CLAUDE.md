# AGENTS.md - 微信智能日程规划 Agent 开发指南

## 项目概述

微信智能日程规划 Agent 是一个基于微信消息通道的轻量多用户智能日程规划系统。

系统使用 `openclaw-weixin` 作为微信消息传递通道，但不使用 OpenClaw Runtime，也不使用 OpenClaw Agent 编排能力。后端由自研 FastAPI 服务负责 Agent、用户权限、日程规划、冲突检测、提醒调度和 Web API。

用户可以通过微信自然语言创建日程、创建任务、生成每日计划、处理冲突并接收提醒。Web Dashboard 用于展示日程驾驶舱、任务池、冲突事项、提醒任务、Agent 日志、邀请码和用户管理。

| 组件 | 技术栈 | 适用范围 |
| ---- | ------ | -------- |
| 后端服务 | Python 3.11+ + FastAPI + SQLAlchemy 2.0 + Alembic | 全局核心服务 |
| Agent 状态流 | LangGraph ReAct Agent + langchain_openai.ChatOpenAI | 日程识别、规划、确认、冲突处理 |
| 数据库 | PostgreSQL | 用户、日程、任务、计划、日志、提醒 |
| 缓存 | Redis 7+ | 查询缓存、天气缓存、Agent 状态缓存 |
| 提醒调度 | APScheduler | reminder_job 到点触发 |
| Web Dashboard | Next.js + React + TypeScript + Ant Design | owner/member 日程驾驶舱 |
| 微信通道 | openclaw-weixin + 自研 WeChat Channel Adapter | 微信消息接收、回复、提醒 |
| 部署 | Docker Compose | 自用部署 |

## 项目文档读取要求

在开始任何开发任务前，必须先阅读并理解 `docs/` 目录下的项目设计文档。

这些文档是本项目的开发依据，优先级高于临时猜测和通用工程习惯。开发时必须以文档中的架构、数据模型、接口、Agent 流程、微信通道设计和任务拆分为准。

必须阅读的文档包括：

```text

docs/01-requirements.md
docs/02-architecture-design.md
docs/03-database-design.md
docs/04-api-design.md
docs/05-agent-langgraph-design.md
docs/06-wechat-channel-design.md
docs/07-web-dashboard-design.md
docs/08-codex-tasks.md

```

各文档用途如下：

```text

docs/01-requirements.md
项目完整需求说明，包括系统定位、用户角色、核心功能、微信入口、Web 驾驶舱、邀请码机制等。

docs/02-architecture-design.md
系统架构设计，包括 FastAPI 后端、LangGraph Agent、openclaw-weixin 微信通道、Reminder Worker、Web Dashboard 的边界和调用关系。

docs/03-database-design.md
数据库设计，包括用户、邀请码、微信绑定、日程、任务、每日计划、冲突、提醒、Agent 日志等表结构。

docs/04-api-design.md
后端 REST API 设计，包括认证、邀请码、用户、微信绑定、日程、任务、计划、冲突、提醒、Agent 调试、系统设置等接口。

docs/05-agent-langgraph-design.md
Agent 与 LangGraph 设计，包括 AgentState、ReAct 循环、工具、Prompt、interrupt 确认、冲突处理等规则。

docs/06-wechat-channel-design.md
微信通道接入设计，明确 openclaw-weixin 只作为消息通道，WeChat Channel Adapter 负责消息标准化、绑定、入站和出站。

docs/07-web-dashboard-design.md
Web Dashboard 页面与权限设计，包括 owner/member 菜单、页面功能、调用接口和权限边界。

docs/08-codex-tasks.md
Codex 开发任务拆分文档，明确开发顺序必须是 Agent 先行，消息通道后置。

```

开发前必须遵守：

```text

1. 先阅读 docs/ 下相关文档，再开始实现。
2. 不得跳过文档直接按经验生成代码。
3. 如果任务涉及数据库，必须先阅读 docs/03-database-design.md。
4. 如果任务涉及接口，必须先阅读 docs/04-api-design.md。
5. 如果任务涉及 Agent，必须先阅读 docs/05-agent-langgraph-design.md。
6. 如果任务涉及微信消息，必须先阅读 docs/06-wechat-channel-design.md。
7. 如果任务涉及前端页面或权限菜单，必须先阅读 docs/07-web-dashboard-design.md。
8. 如果任务涉及开发顺序，必须先阅读 docs/08-codex-tasks.md。
9. 如果文档之间存在冲突，先停止开发并向用户说明冲突点，等待确认后再继续。
10. 不得将 openclaw-weixin 理解为 OpenClaw Runtime；本项目只使用它作为微信消息通道。

```

重要约束：

```text

Agent 先行，消息通道后置。

必须先保证 Debug API 能让 SchedulePlanningGraph 识别日程、任务、计划、冲突并完成相关操作，再接入 openclaw-weixin 微信消息通道。

```

## 构建/测试命令

### 后端服务

优先使用 `uv`。

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run mypy app
```

如果项目未使用 `uv`，则使用：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
pytest
ruff check .
mypy app
```

### Web Dashboard

优先使用 `pnpm`。

```bash
cd web
pnpm install
pnpm dev
pnpm build
pnpm typecheck
pnpm lint
```

如果项目未使用 `pnpm`，则使用：

```bash
cd web
npm install
npm run dev
npm run build
npm run typecheck
npm run lint
```

### Docker Compose

```bash
docker compose up -d
docker compose logs -f backend
docker compose logs -f web
docker compose down
```

## 代码风格

### 命名约定

| 类型 | 规则 |
| ---- | ---- |
| Python 模块文件 | snake_case，例如 `calendar_event_service.py` |
| Python 类名 | PascalCase，例如 `CalendarEventService` |
| Python 函数/变量 | snake_case，例如 `create_event` |
| Pydantic Schema | PascalCase，例如 `CreateEventRequest` |
| SQLAlchemy Model | PascalCase，例如 `CalendarEvent` |
| 数据库表名 | 复数 snake_case，例如 `calendar_events` |
| 前端组件 | PascalCase，例如 `TodayPlanTimeline.tsx` |
| 前端 Hook | camelCase，必须以 `use` 开头，例如 `useAuth.ts` |
| 前端变量/函数 | camelCase，例如 `fetchCalendarEvents` |
| TypeScript 类型/接口 | PascalCase，例如 `CalendarEventItem` |
| 常量 | UPPER_SNAKE_CASE，例如 `DEFAULT_TIMEZONE` |
| 布尔变量 | Python 使用 `is_`、`has_`、`can_` 前缀；TypeScript 使用 `is`、`has`、`can` 前缀 |
| 通用 | 禁止中文命名，禁用模糊缩写，API、URL、ID、DB、LLM 等通用缩写除外 |

### 核心规范

- 禁止使用 emoji。
- 文档、注释和说明统一使用中文。
- 变量名、类名、函数名、配置项、数据库字段必须使用英文。
- 代码中不要添加无意义注释。
- 只有在逻辑复杂、Agent 状态流较难理解、冲突检测算法较复杂时，才允许添加简洁注释。
- 在函数或代码块内使用模型、Schema、Service、Tool 时，必须确保当前文件已有完整 import。
- 禁止假设外层已经导入。
- 后端用户可见错误信息使用中文。
- 前端用户可见文案首版可以直接使用中文；后续如引入 i18n，再统一迁移。
- 所有涉及时间的字段必须明确时区含义。
- 数据库存储统一使用 UTC 时间，展示时按用户 `default_timezone` 转换。
- 默认时区为 `Asia/Shanghai`。

## 架构原则

### 总体架构

本项目最终架构为：

```text
微信用户
  ↓
openclaw-weixin
  ↓
WeChat Channel Adapter
  ↓
FastAPI Schedule Agent Service
  ↓
LangGraph SchedulePlanningGraph (ReAct: agent ↔ tools)
  ↓
LangChain @tool + ToolNode
  ↓
Business Services
  ↓
PostgreSQL
  ↓
Redis 缓存层 (写时失效 + TTL 兜底)
  ↓
APScheduler Reminder Worker
  ↓
WeChat Channel Adapter
  ↓
openclaw-weixin
  ↓
微信用户
```

Web 访问链路：

```text
Next.js Web Dashboard
  ↓
FastAPI REST API
  ↓
PostgreSQL
```

### 核心边界

- `openclaw-weixin` 只作为微信消息通道。
- 不使用 OpenClaw Runtime。
- 不使用 OpenClaw Agent 编排。
- 后端 Agent、业务、权限、数据库、Web API 全部由 FastAPI 实现。
- LangGraph 只负责 Agent 状态流，不负责数据库 CRUD。
- LLM 只负责自然语言理解、信息抽取和回复生成。
- 冲突检测必须由程序确定性算法完成。
- 提醒发送不经过 LLM。
- Agent 不允许直接写数据库，必须通过 @tool 装饰器的工具函数调用业务服务。
- 工具函数内部使用 `set_user_id()` 注入用户身份，不允许信任模型输出的 `user_id`。
- `user_id` 必须由系统上下文注入。

## 目录结构限制

### 后端目录

推荐结构：

```text
backend/
  app/
    api/
      routes/
        auth.py
        invite_codes.py
        users.py
        wechat.py
        channel_identity.py
        scheduled_items.py
        tasks.py
        conflicts.py
        reminders.py
        agent_logs.py
        settings.py

    agent/
      graph.py
      tools.py
      security.py

    services/
      auth_service.py
      invite_code_service.py
      user_service.py
      channel_identity_service.py
      scheduled_item_service.py
      task_service.py
      conflict_service.py
      reminder_service.py
      agent_log_service.py
      system_setting_service.py
      wechat_channel_service.py
      cache_manager.py
      cache_invalidator.py

    workers/
      reminder_worker.py

    models/
      __init__.py
      enums.py
      user.py
      schedule.py
      scheduled_item.py
      channel.py
      agent.py
      system.py

    schemas/
    db/
    core/
      config.py
      security.py
      redis.py
      cache.py
      cache_invalidator.py
```

### 前端目录

推荐结构：

```text
web/
  app/
    login/
    register/
    dashboard/
      today/
      calendar/
      tasks/
      conflicts/
      reminders/
      agent-logs/
      wechat-binding/
    admin/
      invite-codes/
      users/
      settings/
      wechat-status/
      message-logs/

  components/
  lib/
  api/
  types/
  hooks/
```

## 数据库与数据规则

### 迁移管理

- 所有数据库结构变更必须通过 Alembic 进行迁移管理。
- 必须生成 migration 文件。
- migration 必须支持正向执行。
- 涉及删除字段、删除表、数据迁移等高风险操作时，必须先向用户说明影响，得到确认后再执行。
- 禁止手动直接修改生产数据库表结构。

### 主键与时间

- 主键统一使用 UUID。
- 时间字段统一使用 `TIMESTAMP WITH TIME ZONE`。
- 后端统一使用 aware datetime。
- 数据库存储 UTC。
- 展示时按用户 `user_settings.default_timezone` 转换。

### 软删除

核心业务数据必须使用逻辑删除，禁止物理删除。

适用表：

```text
users
scheduled_items
task_items
schedule_conflicts
reminder_jobs
```

规则：

- `users` 使用 `status = deleted`。
- `scheduled_items` 使用 `status = deleted`。
- `task_items` 使用 `status = deleted`。
- 查询默认过滤 deleted 数据。
- 短期验证码、过期绑定码可以后续定期物理清理。

### 数据隔离

所有用户业务数据必须按 `user_id` 隔离。

必须隔离的表：

```text
scheduled_items
task_items
schedule_conflicts
reminder_jobs
agent_run_logs
channel_message_logs
```

规则：

- member 查询时必须强制附加 `user_id = current_user.id`。
- member 修改时必须验证数据归属。
- member 删除时必须验证数据归属。
- owner 可以访问全局日志和用户管理。
- owner 自己的日程数据仍然以 owner 的 `user_id` 存储。
- Agent 工具调用时 `user_id` 由系统注入，禁止使用模型输出的 `user_id`。

## Agent 开发规范

### LangGraph 使用边界

当前架构使用 LangGraph ReAct 循环，包含 3 个节点：

```text
agent: ReAct 循环核心，LLM 自主判断意图并调用工具
tools: LangGraph ToolNode，执行 @tool 装饰器定义的工具函数
human: interrupt 确认节点，暂停等待用户输入后恢复执行
```

工具函数定义在 `backend/app/agent/tools.py`，使用 LangChain `@tool` 装饰器，共 18 个工具。

禁止将以下逻辑交给 LLM 直接处理：

```text
数据库 CRUD（由工具函数完成）
权限校验（由系统上下文注入）
微信消息发送（由 WeChat Channel Adapter 完成）
精确冲突算法（由 ConflictService 完成）
用户身份识别（由 set_user_id() 注入）
密码、邀请码、系统设置
```

### Agent 安全防护

Agent 必须实现 5 层安全防御：

1. **输入消毒 (InputSanitizer)**
   - 检测并阻止 prompt 注入攻击
   - 限制输入长度（最大 2000 字符）
   - 关键词和正则模式匹配

2. **内容过滤 (ContentFilter)**
   - 过滤写入工具参数中的注入内容
   - 截断过长的文本字段
   - 替换检测到的注入内容为 `[已过滤]`

3. **工具调用守卫 (ToolCallGuard)**
   - 高风险工具（如删除）需要用户确认
   - 验证 `confirmed_action` 参数

4. **工具结果消毒 (ToolResultSanitizer)**
   - 为用户数据添加安全标记
   - 防止工具结果被误解为系统指令

5. **输出消毒 (OutputSanitizer)**
   - 检测并过滤系统提示词泄露
   - 替换泄露内容为安全提示

### AgentState 要求

AgentState 定义在 `backend/app/agent/graph.py`，使用 LangGraph `TypedDict`：

```text
messages: Annotated[list, add_messages]  # 消息列表（LangGraph 核心）
user_id: str
conversation_id: str
timezone: str
current_time: str
user_settings: dict | None
tool_calls: list[dict]   # 工具调用记录
tool_results: list[dict] # 工具执行结果
needs_confirmation: bool  # 是否需要用户确认
confirmation_prompt: str  # 确认提示内容
confirmed_action: str | None  # 用户确认动作
```

### 工具系统要求

- 所有工具使用 LangChain `@tool` 装饰器定义在 `backend/app/agent/tools.py`。
- 工具函数使用 `set_user_id()` 从上下文注入 `user_id`，不允许接受模型传入的 `user_id`。
- 工具函数内部创建 `SessionLocal()` 数据库会话，不依赖外部注入。
- 工具调用记录通过 `AgentLogService` 写入 `agent_run_logs`。

### 工具列表

必须支持：

```text
create_scheduled_item
query_scheduled_items
update_scheduled_item
delete_scheduled_item
search_scheduled_item_candidates

create_task
query_tasks
update_task
complete_task

analyze_day
find_free_slots
plan_tasks_into_day
confirm_plan
regenerate_plan

detect_conflicts
suggest_reschedule

create_reminder
update_reminder
cancel_reminder

ask_user_clarification
```

### Agent 交互规则

- 单条明确日程可以自动写入。
- 单条明确提醒可以自动写入。
- 复杂规划必须先生成草案。
- 存在冲突时必须询问用户。
- 多候选时必须让用户选择。
- 信息不足时必须追问。
- 用户回复”确认””取消””1””2””3”时，由 LangGraph interrupt 机制自动恢复执行。
- Reminder 不经过 Agent，不调用 LLM。

## 微信通道规范

### openclaw-weixin 边界

`openclaw-weixin` 只做消息传递。

它负责：

```text
接收微信文本消息
发送微信文本回复
发送提醒消息
```

它不负责：

```text
Agent 逻辑
日程业务
用户系统
权限系统
冲突检测
Web Dashboard
数据库管理
```

### WeChat Channel Adapter

WeChat Channel Adapter 负责：

```text
接收 openclaw-weixin 原始消息
标准化消息
记录 channel_message_logs
识别绑定命令
映射 channel_identity
调用 SchedulePlanningGraph
发送 final_response
调用 openclaw-weixin 发送提醒
```

标准入站消息：

```json
{
  "message_id": "wx_msg_001",
  "conversation_id": "wx_user_001",
  "channel_user_id": "wx_user_001",
  "display_name": "用户昵称",
  "content_type": "text",
  "content": "明天下午 3 点开会",
  "raw_payload": {}
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

### 微信绑定

绑定流程：

```text
用户登录 Web
  ↓
生成绑定码
  ↓
微信发送：绑定 123456
  ↓
系统校验绑定码
  ↓
写入 channel_identities
```

未绑定用户发送普通消息时回复：

```text
你还没有绑定账号，请先在 Web 中使用邀请码注册并绑定微信。
```

被禁用用户发送消息时回复：

```text
你的账号当前不可用，请联系系统主用户。
```

## Web Dashboard 规范

### 权限菜单

owner 菜单：

```text
今日计划
日历视图
任务池
冲突事项
提醒任务
Agent 日志
微信绑定
微信通道状态
用户管理
邀请码管理
系统设置
模型配置
全局消息日志
```

member 菜单：

```text
今日计划
日历视图
任务池
冲突事项
提醒任务
我的 Agent 记录
微信绑定
我的账号设置
```

### 权限边界

- 前端隐藏菜单只作为体验优化。
- 后端必须做权限校验。
- member 访问 admin API 必须返回 403。
- member 访问其他用户资源必须返回 403 或 404。
- `LLM_API_KEY` 不允许明文展示。

## 错误处理原则

### 必须遵循

- 不确定的事情先查证，查不到就说明查不到。
- 回答或提交修改时说明依据，定位到文件、接口、日志或测试结果。
- 如果无法解决，列出已经尝试的排查步骤。
- 排查方向错误时直接承认并修正。
- 修改失败后不得隐瞒错误。
- Agent 解析失败必须返回可理解的用户提示。
- LLM JSON 解析失败不能导致服务崩溃。
- Reminder 发送失败必须记录 error_message 和 retry_count。

### 严禁

- 禁止猜测性断言。
- 禁止未经验证就声称“已修复”。
- 禁止绕过权限校验直接查库。
- 禁止直接相信 LLM 输出。
- 禁止在没有用户确认的情况下执行破坏性操作。
- 禁止提交 `.env`、密钥、数据库密码、LLM API Key。

## 问题处理流程

发现问题后不要立即修改，先报告给用户，等用户确认方案后再改。

流程：

1. 明确描述问题。
2. 说明影响范围。
3. 说明已检查的位置。
4. 提出修复方案。
5. 等待用户确认。
6. 确认后执行代码级修复。

例外情况可直接修复：

```text
明显拼写错误
导入缺失
lint 格式错误
用户明确要求“直接修”
测试断言中的明显字段名错误
```

## Git 规范

### 分支命名

格式：

```text
<type>/<kebab-case-description>
```

可用前缀：

```text
feat
fix
refactor
chore
docs
perf
test
build
```

示例：

```text
feat/schedule-agent-graph
feat/invite-code-auth
fix/reminder-retry
docs/api-design
```

禁止：

```text
temp
test
new
final
中文分支名
纯日期分支名
大写或下划线分支名
```

### Commit Message 格式

```text
<type>(<scope>): <subject>
```

要求：

- type 与分支前缀一致。
- subject 必须使用中文。
- subject 使用祈使语态。
- subject 50 字内。

示例：

```text
feat(auth): 新增邀请码注册接口
feat(agent): 实现日程创建意图识别
fix(reminder): 修复提醒重试次数更新错误
docs(api): 补充微信入站接口说明
```

### 提交要求

- 每完成一个可独立验证的最小改动，必须提交一次。
- 禁止把大量无关修改合并成一个 commit。
- 禁止提交 `.env`。
- 禁止提交 `.venv/`。
- 禁止提交 `node_modules/`。
- 禁止提交 `dist/`、`.next/`、缓存目录。
- 禁止提交真实 API Key、微信通道 token、数据库密码。

### 分批提交与部署验证

完成一个功能或任务后，必须按照以下流程进行分批提交和部署验证：

**分批提交策略：**

```text
1. 后端代码变更（models、services、routes、agent 等）
2. 前端代码变更（components、pages、hooks、api 等）
3. 配置文件变更（docker-compose、Dockerfile、环境变量等）
4. 文档变更（docs、README 等）
```

**提交流程：**

```text
1. 检查 git status，识别所有变更文件
2. 按模块分组：后端、前端、配置、文档
3. 分批执行 git add 和 git commit
4. 每批 commit message 必须清晰描述变更范围
5. 确保每批提交都能独立构建通过
```

**Docker 部署验证流程：**

```text
1. 完成所有分批提交后
2. 执行 docker compose build --no-cache 重新构建镜像
3. 执行 docker compose up -d 启动服务
4. 等待服务启动完成（约 30-60 秒）
5. 验证后端服务：curl http://localhost:8000/health
6. 验证前端服务：访问 http://localhost:3000
7. 检查日志：docker compose logs --tail=50
8. 确认无错误后，执行 docker compose down 停止服务
```

**验证检查点：**

```text
后端验证：
- GET /health 返回 ok
- 数据库连接正常
- API 接口响应正常

前端验证：
- 页面能正常加载
- 无控制台错误
- API 调用正常
```

**异常处理：**

```text
1. 如果构建失败，检查 Dockerfile 和依赖
2. 如果启动失败，检查 docker compose logs
3. 如果接口异常，检查后端日志和数据库连接
4. 如果前端异常，检查构建日志和控制台错误
```

## 测试要求

### 后端测试

必须覆盖：

```text
认证登录
邀请码注册
RBAC 权限
数据隔离
微信绑定码
日程创建
日程查询
任务创建
计划草案
计划确认
冲突检测
Reminder Worker
SchedulePlanningGraph
LangGraph ReAct 循环
interrupt 确认机制
```

### Agent 测试用例

必须通过：

```text
明天下午 3 点开会
明天有什么安排？
明天写论文 2 小时
帮我安排明天的计划
确认
把明天下午 3 点的会议改到 4 点
删除明天下午 4 点的会议
明天下午 3 点开会，但已有冲突
提醒我写论文，但未指定时间
取消
```

### 前端测试

至少保证：

```text
owner 和 member 菜单隔离
member 无法看到 admin 菜单
登录失败有提示
日历页面能展示日程
任务池能展示任务
冲突页能展示冲突
Agent 日志页能展示工具调用
```

## 部署与容器化

### Docker 平台

所有 Docker 构建操作必须显式指定平台：

```bash
docker build --platform linux/amd64 -t schedule-agent-backend .
```

### Docker Compose 服务

推荐服务：

```text
backend
web
postgres
redis
wechat-channel
```

### 环境变量

必须提供 `.env.example`，但禁止提交 `.env`。

后端环境变量至少包括：

```text
DATABASE_URL
REDIS_URL
JWT_SECRET
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
DEFAULT_TIMEZONE
REMINDER_SCAN_INTERVAL_SECONDS
WECHAT_CHANNEL_TOKEN
```

敏感环境变量不得写入 README 示例真实值。

## 破坏性操作确认

以下操作执行前，必须逐项列出影响并获得用户明确确认：

```text
DROP TABLE
TRUNCATE TABLE
DELETE 大量业务数据
清空用户数据
重置数据库
删除 migration
修改已有 migration 历史
git reset --hard
git push --force
删除 Docker volume
删除 PostgreSQL 数据目录
修改生产环境变量
覆盖系统设置
禁用 owner 用户
```

## 同源逻辑同步

修改一处逻辑后，必须全局搜索是否存在相同逻辑并同步修改。

常见同步点：

| 逻辑类型 | 需同步检查位置 |
| -------- | -------------- |
| 状态枚举 | SQLAlchemy Model、Pydantic Schema、前端常量 |
| 权限规则 | FastAPI dependency、前端路由守卫、菜单配置 |
| API 字段 | 后端 Schema、前端 API 类型、表单字段 |
| 时间规则 | Agent Prompt、后端时间工具、前端展示组件 |
| 冲突规则 | ConflictService、Agent 回复模板、Web 冲突页 |
| 提醒规则 | ReminderService、Reminder Worker、Web 提醒页 |
| 用户状态 | AuthService、WeChat inbound、Web 用户管理页 |

## 用户偏好

- 使用中文交流。
- 回答风格简洁直接。
- 拒绝废话。
- 代码默认不加注释。
- 复杂 Agent 状态流、复杂冲突检测算法可以添加必要注释。
- 先确认需求和方案，再动手改代码。
- Codex 任务应先做 Agent 能力闭环，再接微信消息通道。

## Codex 开发顺序

必须遵守以下开发顺序：

```text
1. FastAPI 基础工程
2. 数据库模型
3. 用户认证和权限
4. 邀请码注册
5. 日程 / 任务 / 计划 / 提醒业务服务
6. 冲突检测
7. Reminder Worker
8. LangChain @tool 工具函数
9. LangGraph ReAct Agent
10. SchedulePlanningGraph 基础版
11. Agent 支持任务和计划
12. Agent 支持冲突处理
13. Agent 支持修改和删除
14. Agent 安全防护
15. Agent 总体验收
16. Web Dashboard 基础页面
17. owner 管理页面
18. 微信绑定和入站接口
19. 接入 openclaw-weixin
20. 测试和文档
```

最重要原则：

```text
Agent 先行，消息通道后置。
```

必须先保证：

```text
Debug API 输入自然语言
  ↓
SchedulePlanningGraph ReAct 循环
  ↓
@tool 工具函数执行业务逻辑
  ↓
数据库写入 / 查询 / 修改 / 删除
  ↓
返回自然语言回复
```

再接入：

```text
openclaw-weixin
```

## 特殊架构说明

### 单体后端原则

本项目为自用系统，不拆微服务。

FastAPI 后端内部按模块拆分，但物理上保持单体服务：

```text
API Server
SchedulePlanningGraph (ReAct Agent)
LangChain @tool 工具函数
Business Services
Reminder Worker
```

原因：

```text
部署简单
维护简单
事务一致性更容易
Agent 和业务服务复用方便
后续不计划大规模迭代
```

### Agent 与业务分层原则

新增功能时必须遵守：

```text
Agent 节点负责流程判断（ReAct 循环）
@tool 工具函数负责工具调用
Service 负责业务逻辑
Model 负责数据映射
Schema 负责输入输出校验
```

禁止：

```text
在 Agent 节点里直接写数据库
在路由里写复杂业务逻辑
在工具里绕过 Service
在 LLM Prompt 中暴露敏感配置
在前端实现后端权限逻辑
```

### 微信通道分层原则

新增微信相关能力时必须遵守：

```text
openclaw-weixin 只负责消息通道
WeChat Channel Adapter 负责格式适配
FastAPI 负责业务处理
SchedulePlanningGraph 负责 Agent 逻辑
```

禁止：

```text
在微信通道层写日程逻辑
在微信通道层调用数据库创建日程
在微信通道层判断复杂意图
在 Reminder Worker 中调用 LLM
```
