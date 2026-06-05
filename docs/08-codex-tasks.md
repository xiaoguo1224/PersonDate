# Codex 开发任务拆分文档 v2.0

## 1. 开发主线调整

本项目开发顺序以 Agent 能力闭环为核心。

不要一开始接真实微信通道。  
不要一开始做完整 Web Dashboard。  
不要先围绕微信通道设计开发顺序。

正确开发主线是：

```text
1. 后端基础工程
2. 数据库模型
3. 用户 / 权限 / 数据隔离
4. 日程、任务、计划、冲突、提醒等业务服务
5. Tool Executor
6. SchedulePlanningGraph
7. Agent Debug API
8. 通过 Debug API 验证 Agent 能识别日程并完成相关操作
9. Web Dashboard
10. 最后接入微信通道服务
```

核心原则：

```text
先让 Agent 会做事，再让微信成为输入输出通道。
```

## 2. 阶段目标

### 阶段一：Agent 能力闭环

目标：

```text
用户通过 Debug API 输入自然语言
  ↓
SchedulePlanningGraph 识别意图
  ↓
Agent 调用工具
  ↓
工具操作数据库
  ↓
完成日程、任务、计划、冲突检测、提醒任务创建
  ↓
Agent 返回自然语言回复
```

验收示例：

```text
输入：明天下午 3 点开会
结果：创建 calendar_event + reminder_job，并返回自然语言回复

输入：明天有什么安排？
结果：查询明天日程并返回列表

输入：明天写论文 2 小时，帮我安排一下
结果：创建 task_item，生成 day_plan 草案，保存 pending_state

输入：确认
结果：确认草案并写入正式 day_plan / plan_item

输入：把明天下午 3 点的会议改到 4 点
结果：搜索候选日程，修改日程，更新提醒

输入：删除明天下午 4 点的会议
结果：删除日程，取消提醒
```

### 阶段二：Web Dashboard

目标：

```text
用 Web 展示 Agent 创建的数据和执行过程。
```

### 阶段三：微信通道接入

目标：

```text
将微信通道接收到的微信消息接入同一个 SchedulePlanningGraph。
```

微信只是换一个输入输出通道，不能改变 Agent 主流程。

## 3. Task 1：初始化 FastAPI 后端项目

### 目标

初始化后端基础工程。

### 技术栈

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
```

### 要求

1. 创建 FastAPI 项目结构。
2. 配置 `settings.py`。
3. 配置数据库连接。
4. 配置 SQLAlchemy session。
5. 配置 Alembic。
6. 添加基础健康检查接口。
7. 添加基础 README。

### 接口

```http
GET /health
```

### 不要做

```text
不要实现微信通道。
不要实现 Web 前端。
不要实现完整 Agent。
不要实现业务接口。
```

### 验收标准

```text
uvicorn app.main:app --reload 可以启动。
GET /health 返回 ok。
alembic 可正常运行。
```

## 4. Task 2：实现数据库模型和迁移

### 目标

根据数据库设计文档实现所有核心表。

### 范围

```text
users
user_settings
invite_codes
invite_code_usages
channel_identities
wechat_login_sessions
channel_message_logs
calendar_events
task_items
day_plans
plan_items
schedule_conflicts
reminder_jobs
agent_run_logs
agent_pending_states
system_settings
```

### 要求

1. 使用 UUID 主键。
2. 使用 TIMESTAMPTZ 时间。
3. 使用 JSONB 保存 Agent trace、tool_results、pending_state。
4. 添加必要索引。
5. 添加 user_id 数据隔离字段。
6. 使用 Alembic migration 管理表结构。

### 不要做

```text
不要实现业务逻辑。
不要实现接口。
```

### 验收标准

```text
alembic upgrade head 成功。
数据库中创建所有表和索引。
```

## 5. Task 3：实现用户、认证、权限和 owner 初始化

### 目标

建立系统基础身份体系，保证后续 Agent 工具调用有 user_id 上下文。

### 接口

```http
GET /api/setup/status
POST /api/setup/owner
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
```

### 要求

1. 支持 owner 初始化。
2. 支持 JWT 登录。
3. 密码使用 argon2 或 bcrypt。
4. JWT 中包含 user_id 和 role。
5. 实现 current_user dependency。
6. 实现 require_owner dependency。
7. 初始化 user_settings。

### 不要做

```text
不要实现邀请码注册。
不要实现微信绑定。
不要实现 Agent。
```

### 验收标准

```text
系统可以创建 owner。
owner 可以登录。
受保护接口可以获取 current_user。
member 访问 owner 接口会被拒绝。
```

## 6. Task 4：实现邀请码注册和 RBAC

### 目标

支持 owner 生成邀请码，member 通过邀请码注册。

### 接口

```http
POST /api/admin/invite-codes
GET /api/admin/invite-codes
PATCH /api/admin/invite-codes/{id}/disable
GET /api/admin/invite-codes/{id}/usages
POST /api/auth/register-with-invite
```

### 要求

1. 只有 owner 可以创建邀请码。
2. 邀请码支持 max_uses、expires_at、status。
3. member 必须通过邀请码注册。
4. 注册成功后创建 user_settings。
5. 记录 invite_code_usages。
6. member 不能访问 admin 接口。

### 验收标准

```text
owner 可以生成邀请码。
新用户可以使用邀请码注册为 member。
member 无法访问 owner 接口。
```

## 7. Task 5：实现日程、任务、计划、提醒的基础业务服务

### 目标

先实现业务服务层，不接 Agent。

### 服务

```text
CalendarEventService
TaskService
DayPlanService
ReminderService
ConflictService
```

### 接口

```http
GET /api/calendar-events
POST /api/calendar-events
PATCH /api/calendar-events/{id}
DELETE /api/calendar-events/{id}

GET /api/tasks
POST /api/tasks
PATCH /api/tasks/{id}
DELETE /api/tasks/{id}
PATCH /api/tasks/{id}/complete

GET /api/day-plans/{date}
POST /api/day-plans/{date}/generate
POST /api/day-plans/{id}/confirm

GET /api/reminders
PATCH /api/reminders/{id}/cancel
```

### 要求

1. 所有数据必须按 current_user.id 隔离。
2. 创建日程时可创建 reminder_job。
3. 删除日程时取消 reminder_job。
4. 创建任务时保存 estimated_minutes、deadline、priority。
5. 生成计划草案时写入 `day_plans.status = draft`。
6. 确认计划时 `day_plans.status = confirmed`。

### 不要做

```text
不要实现 LangGraph。
不要实现 LLM。
不要实现微信通道。
```

### 验收标准

```text
用户可以通过 REST API 创建日程、任务和计划草案。
member A 看不到 member B 的数据。
```

## 8. Task 6：实现确定性冲突检测

### 目标

实现 ConflictService，确保冲突判断不依赖 LLM。

### 冲突类型

```text
time_overlap
too_many_tasks
deadline_risk
insufficient_free_time
missing_time
ambiguous_intent
```

### 接口

```http
GET /api/conflicts
POST /api/conflicts/detect
PATCH /api/conflicts/{id}/ignore
PATCH /api/conflicts/{id}/resolve
```

### 要求

1. 检测固定日程时间重叠。
2. 检测计划任务总时长是否超过可用时间。
3. 检测 deadline 风险。
4. 检测任务缺少时间或耗时。
5. 将冲突写入 schedule_conflicts。
6. 支持忽略和标记解决。

### 验收标准

```text
创建两个重叠日程后，POST /api/conflicts/detect 可以生成 time_overlap 冲突。
```

## 9. Task 7：实现 Reminder Worker

### 目标

实现 APScheduler 提醒调度。

### 要求

1. 使用 APScheduler 定时扫描 reminder_jobs。
2. 每 10 秒扫描 status = pending 且 trigger_time <= now 的任务。
3. 到点后生成提醒文本。
4. 首版先 console.log 模拟发送。
5. 发送成功后 status = fired。
6. 发送失败 retry_count + 1。
7. 超过 max_retries 后 status = failed。

### 不要做

```text
不要接真实微信通道。
不要让提醒经过 LLM。
```

### 验收标准

```text
创建一个 1 分钟后的 reminder_job，到点后控制台输出提醒内容。
```

## 10. Task 8：实现 ToolRegistry 和 ToolExecutor

### 目标

建立 Agent 调用业务服务的工具层。

### 工具

```text
create_event
query_events
update_event
delete_event
search_event_candidates
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

### 要求

1. 实现 ToolRegistry。
2. 实现 ToolExecutor。
3. ToolExecutor 自动注入 user_id。
4. ToolExecutor 不信任模型传入的 user_id。
5. 每个工具使用 Pydantic schema 校验参数。
6. 工具返回统一 ToolResult。

### 不要做

```text
不要实现 LLM。
不要实现 LangGraph。
```

### 验收标准

```text
可以在测试中手动调用 create_event 工具。
工具调用后写入 calendar_events 和 reminder_jobs。
```

## 11. Task 9：实现 LLMClient 和结构化输出

### 目标

封装 OpenAI-compatible LLM 调用。

### 要求

1. 支持 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL。
2. 实现 `chat_json` 方法。
3. 支持 Pydantic schema 校验 LLM 输出。
4. JSON 解析失败时返回可控错误。
5. 添加基础 prompt 模板。

### 不要做

```text
不要实现完整 LangGraph。
不要接微信。
```

### 验收标准

```text
输入“明天下午 3 点开会”，LLMClient 可以返回结构化 intent 和 extracted 信息。
```

## 12. Task 10：实现 SchedulePlanningGraph 基础版

### 目标

实现 LangGraph Agent 第一版，支持创建日程和查询日程。

### 节点

```text
load_context
check_pending_state
classify_intent
extract_info
route_intent
handle_create_event
handle_query_events
generate_response
save_agent_log
```

### 支持意图

```text
create_event
query_events
unknown
```

### 调试接口

```http
POST /api/agent/debug/message
```

请求：

```json
{
  "message": "明天下午 3 点开会"
}
```

### 要求

1. Debug API 必须走真实 SchedulePlanningGraph。
2. 创建日程必须通过 ToolExecutor。
3. 查询日程必须通过 ToolExecutor。
4. 每次运行必须写 agent_run_logs。
5. 不接微信通道。

### 验收标准

```text
通过 Debug API 输入“明天下午 3 点开会”，能创建日程。
输入“明天有什么安排？”，能查询日程。
```

## 13. Task 11：扩展 Agent 支持任务和每日计划

### 目标

让 Agent 能识别弹性任务，并生成每日计划草案。

### 新增意图

```text
create_task
plan_day
confirm_plan
```

### 新增节点

```text
handle_create_task
handle_plan_day
handle_confirm
save_pending_state
clear_pending_state
```

### 要求

1. “明天写论文 2 小时”能创建 task_item。
2. “帮我安排明天的计划”能生成 day_plan draft。
3. 复杂规划必须保存 agent_pending_state。
4. 用户回复“确认”后，写入正式 day_plan / plan_items。
5. 用户回复“取消”后，取消 pending_state。

### 验收标准

```text
Debug API 输入“明天写论文 2 小时，帮我安排一下”
返回计划草案并等待确认。
继续输入“确认”
系统确认计划并写入 plan_items。
```

## 14. Task 12：扩展 Agent 支持冲突处理

### 目标

Agent 能处理冲突，并将冲突转换为用户可选方案。

### 要求

1. 创建日程后调用 detect_conflicts。
2. 如果无冲突，正常回复。
3. 如果有冲突，保存 waiting_conflict_resolution pending_state。
4. 回复中列出冲突和选项。
5. 用户回复 1/2/3 后，执行对应处理。

### 验收标准

```text
已有 15:00-16:00 日程时，
Debug API 输入“明天下午 3 点开会”
系统提示冲突并给出选项。
```

## 15. Task 13：扩展 Agent 支持修改和删除

### 目标

Agent 能自然语言修改和删除日程。

### 新增意图

```text
update_event
delete_event
```

### 要求

1. 修改前调用 search_event_candidates。
2. 删除前调用 search_event_candidates。
3. 唯一匹配时直接操作。
4. 多候选时保存 waiting_event_selection。
5. 用户回复序号后继续修改或删除。
6. 修改日程后更新 reminder_job。
7. 删除日程后取消 reminder_job。

### 验收标准

```text
输入“把明天下午 3 点的会议改到 4 点”可以修改日程。
输入“取消明天下午 4 点的会议”可以删除日程。
多个候选时可以通过序号选择。
```

## 16. Task 14：Agent 能力总体验收

### 目标

在不接微信的情况下，完整验证 Agent 能力。

### 必须通过的 Debug API 用例

```text
1. 明天下午 3 点开会
2. 明天有什么安排？
3. 明天写论文 2 小时
4. 帮我安排明天的计划
5. 确认
6. 把明天下午 3 点的会议改到 4 点
7. 删除明天下午 4 点的会议
8. 明天下午 3 点开会，但已有冲突
9. 提醒我写论文，但未指定时间
10. 取消
```

### 验收标准

```text
所有用例通过。
agent_run_logs 中能看到 intent、tool_calls、tool_results、final_response。
数据库中数据正确。
```

## 17. Task 15：实现 Web Dashboard 基础页面

### 目标

实现 Web 可视化，查看 Agent 生成的数据。

### 页面

```text
登录页
邀请码注册页
今日计划页
日历视图页
任务池页
冲突事项页
提醒任务页
Agent 日志页
微信绑定页
个人设置页
```

### 要求

1. Next.js + Ant Design。
2. owner/member 登录。
3. member 只能看到自己的数据。
4. 能通过 Web 调用 Agent Debug API。
5. 能查看 Agent 运行结果。

### 验收标准

```text
Web 可以查看日程、任务、计划、冲突和 Agent 日志。
```

## 18. Task 16：实现 owner 管理页面

### 页面

```text
邀请码管理
用户管理
系统设置
模型配置
全局消息日志
全局 Agent 日志
```

### 要求

1. 仅 owner 可见。
2. member 访问返回 403。
3. LLM_API_KEY 不明文展示。

### 验收标准

```text
owner 可以创建邀请码、禁用用户、修改系统设置。
member 无法访问。
```

## 19. Task 17：实现微信绑定和微信入站接口

### 目标

在 Agent 已经稳定后，实现微信入口适配。

### 接口

```http
POST /api/me/wechat-login-sessions
GET /api/me/channel-identities
DELETE /api/me/channel-identities/{id}
POST /api/wechat/inbound
```

### 要求

1. 用户可创建二维码登录会话。
2. 用户扫码并确认后可完成通道绑定。
3. 未绑定用户发送消息返回绑定提示。
4. 已绑定用户消息进入 SchedulePlanningGraph。
5. 微信入站和 Debug API 使用同一个 Agent 流程。
6. 写 channel_message_logs。

### 不要做

```text
暂时不接真实微信通道。
先用 curl 模拟微信入站。
```

### 验收标准

```text
curl 调用 /api/wechat/inbound，传入已绑定用户消息，能创建日程并返回 reply。
```

## 20. Task 18：接入微信通道服务

### 目标

将真实微信消息通道接入系统。

### 要求

1. 适配微信通道服务原始消息格式。
2. 将消息转发到 `/api/wechat/inbound`。
3. 实现文本消息发送。
4. Reminder Worker 使用真实微信发送。
5. 保留 Debug API。

### 验收标准

```text
微信发送“明天下午 3 点开会”，系统创建日程并回复微信。
到点后，微信收到提醒。
```

## 21. Task 19：测试和文档完善

### 测试范围

```text
认证
邀请码
权限
数据隔离
日程 CRUD
任务
每日计划
冲突检测
Reminder Worker
ToolExecutor
SchedulePlanningGraph
pending_state
微信入站
Web 权限
```

### 文档

```text
README
.env.example
开发说明
部署说明
常见问题
```

## 22. 修正后的任务顺序结论

最终 Codex 任务顺序：

```text
1. FastAPI 基础工程
2. 数据库模型
3. 用户认证和权限
4. 邀请码注册
5. 日程 / 任务 / 计划 / 提醒业务服务
6. 冲突检测
7. Reminder Worker
8. ToolExecutor
9. LLMClient
10. SchedulePlanningGraph 基础版
11. Agent 支持任务和计划
12. Agent 支持冲突处理
13. Agent 支持修改和删除
14. Agent 总体验收
15. Web Dashboard 基础页面
16. owner 管理页面
17. 微信绑定和入站接口
18. 接入微信通道服务
19. 测试和文档
```

最重要原则：

```text
Agent 先行，消息通道后置。
```

也就是：

```text
先保证 SchedulePlanningGraph 能识别日程并完成相关操作；
再让微信消息进入这个已经稳定的 Agent。
```
