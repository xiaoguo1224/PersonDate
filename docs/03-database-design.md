# 数据库设计文档 v1.0

## 1. 数据库设计目标

本系统使用 PostgreSQL 作为主数据库，负责保存用户、邀请码、微信身份绑定、日程、任务、每日计划、冲突事项、提醒任务、Agent 执行日志、微信消息日志、系统设置等数据。

系统定位为：

```text
FastAPI 后端
+
PostgreSQL
+
SQLAlchemy 2.0
+
Alembic
+
LangGraph SchedulePlanningGraph
+
自研微信通道服务
```

数据库设计需要满足以下目标：

1. 支持 owner / member 轻量多用户体系。
2. 支持邀请码注册。
3. 支持每个用户绑定微信身份。
4. 支持用户数据隔离。
5. 支持固定日程、弹性任务、每日计划。
6. 支持日程冲突检测和冲突记录。
7. 支持到点提醒和提醒重试。
8. 支持 Agent 多轮对话 pending state。
9. 支持 Agent 执行日志和工具调用记录。
10. 支持 Web Dashboard 查询展示。
11. 预留外部日历同步扩展。

## 2. 数据库总体分区

```text
用户与权限域：
- users
- user_settings
- invite_codes
- invite_code_usages

微信通道域：
- wechat_accounts
- channel_identities
- channel_message_logs
- wechat_channel_outbound_messages
- wechat_login_sessions

日程业务域：
- calendar_events
- task_items
- day_plans
- plan_items
- schedule_conflicts
- reminder_jobs

Agent 域：
- agent_run_logs
- agent_pending_states

系统配置域：
- system_settings
```

## 3. 通用字段规范

除特殊说明外，主要业务表建议包含：

```text
id
created_at
updated_at
```

推荐类型：

```text
id：UUID，主键
created_at：TIMESTAMP WITH TIME ZONE
updated_at：TIMESTAMP WITH TIME ZONE
```

时间字段统一使用：

```text
TIMESTAMP WITH TIME ZONE
```

业务层默认时区：

```text
Asia/Shanghai
```

数据库中建议统一保存 UTC 时间，展示时按用户时区转换。

## 4. 枚举设计

### 4.1 user_role

```text
owner
member
```

### 4.2 user_status

```text
active
disabled
deleted
```

### 4.3 invite_code_status

```text
active
used_up
expired
disabled
```

### 4.4 channel_type

```text
wechat
```

后续可扩展：

```text
telegram
email
web
```

### 4.5 message_direction

```text
inbound
outbound
```

### 4.6 content_type

```text
text
image
voice
file
unknown
```

首版只使用：

```text
text
```

### 4.7 event_status

```text
active
completed
cancelled
deleted
```

### 4.8 task_priority

```text
low
medium
high
urgent
```

### 4.9 task_status

```text
pending
planned
in_progress
completed
cancelled
deleted
```

### 4.10 day_plan_status

```text
draft
confirmed
active
completed
cancelled
```

### 4.11 plan_item_type

```text
event
task
break
manual
```

### 4.12 plan_item_status

```text
planned
in_progress
completed
cancelled
skipped
```

### 4.13 conflict_type

```text
time_overlap
too_many_tasks
deadline_risk
insufficient_free_time
missing_time
ambiguous_intent
```

### 4.14 conflict_severity

```text
low
medium
high
critical
```

### 4.15 conflict_status

```text
open
ignored
resolved
```

### 4.16 reminder_target_type

```text
calendar_event
task_item
plan_item
day_plan
```

### 4.17 reminder_status

```text
pending
fired
cancelled
failed
```

### 4.18 pending_state_type

```text
waiting_plan_confirmation
waiting_event_selection
waiting_conflict_resolution
waiting_missing_info
waiting_delete_confirmation
waiting_update_confirmation
```

## 5. 用户与权限域

## 5.1 users

用户表，保存 owner 和 member。

### 字段设计

```text
id UUID PK
username VARCHAR(64) NOT NULL UNIQUE
display_name VARCHAR(128)
email VARCHAR(255) UNIQUE
password_hash TEXT NOT NULL
role VARCHAR(32) NOT NULL
status VARCHAR(32) NOT NULL DEFAULT 'active'
last_login_at TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
UNIQUE(username)
UNIQUE(email)
INDEX(role)
INDEX(status)
```

### 约束

```text
role IN ('owner', 'member')
status IN ('active', 'disabled', 'deleted')
```

### 设计说明

系统默认只有一个 owner。member 必须通过邀请码注册。被禁用用户不能登录，也不能通过微信使用 Agent。

## 5.2 user_settings

用户个人设置表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
default_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai'
workday_start_time TIME DEFAULT '09:00:00'
workday_end_time TIME DEFAULT '18:00:00'
daily_plan_push_time TIME DEFAULT '08:00:00'
default_remind_before_minutes INTEGER DEFAULT 0
daily_plan_push_enabled BOOLEAN DEFAULT false
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
UNIQUE(user_id)
```

### 设计说明

member 可以修改自己的 user_settings。系统级配置不放在这里，而放在 system_settings。

## 5.3 invite_codes

邀请码表。

### 字段设计

```text
id UUID PK
code VARCHAR(64) NOT NULL UNIQUE
created_by_user_id UUID NOT NULL FK -> users.id
max_uses INTEGER NOT NULL DEFAULT 1
used_count INTEGER NOT NULL DEFAULT 0
expires_at TIMESTAMPTZ
status VARCHAR(32) NOT NULL DEFAULT 'active'
remark TEXT
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
UNIQUE(code)
INDEX(status)
INDEX(created_by_user_id)
INDEX(expires_at)
```

### 约束

```text
status IN ('active', 'used_up', 'expired', 'disabled')
max_uses >= 1
used_count >= 0
used_count <= max_uses
```

## 5.4 invite_code_usages

邀请码使用记录表。

### 字段设计

```text
id UUID PK
invite_code_id UUID NOT NULL FK -> invite_codes.id
used_by_user_id UUID NOT NULL FK -> users.id
used_at TIMESTAMPTZ NOT NULL
ip_address VARCHAR(64)
user_agent TEXT
created_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(invite_code_id)
INDEX(used_by_user_id)
INDEX(used_at)
```

## 6. 微信通道域

## 6.1 wechat_accounts

微信通道账号表，用于保存扫码登录后的通道凭证、游标和连接状态。

### 字段设计

```text
id UUID PK
owner_user_id UUID NOT NULL FK -> users.id
account_id VARCHAR(255) NOT NULL UNIQUE
wechat_user_id VARCHAR(255)
bot_token TEXT NOT NULL
base_url VARCHAR(512) NOT NULL
cursor TEXT
remark TEXT
status VARCHAR(32) NOT NULL DEFAULT 'active'
bind_time TIMESTAMPTZ
last_active_time TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
UNIQUE(account_id)
INDEX(owner_user_id)
INDEX(status)
INDEX(last_active_time)
```

### 约束

```text
status IN ('active', 'binding', 'expired', 'disabled', 'error')
```

## 6.2 channel_identities

微信身份绑定表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
channel VARCHAR(32) NOT NULL DEFAULT 'wechat'
channel_user_id VARCHAR(255) NOT NULL
conversation_id VARCHAR(255) NOT NULL
display_name VARCHAR(255)
avatar_url TEXT
status VARCHAR(32) NOT NULL DEFAULT 'active'
bound_at TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
UNIQUE(channel, channel_user_id)
UNIQUE(channel, conversation_id)
INDEX(user_id)
INDEX(status)
```

### 设计说明

微信消息进入后，通过 channel_user_id 或 conversation_id 查找 user_id。未绑定用户不能使用 Agent。

## 6.3 wechat_login_sessions

微信二维码登录会话表，用于保存二维码、状态和过期时间。

### 字段设计

```text
id UUID PK
owner_user_id UUID NOT NULL FK -> users.id
login_session_id VARCHAR(255) NOT NULL UNIQUE
qr_payload TEXT NOT NULL
status VARCHAR(32) NOT NULL DEFAULT 'active'
expires_at TIMESTAMPTZ NOT NULL
confirmed_at TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 状态

```text
active
qr_created
wait_scan
scanned
confirmed
expired
failed
```

### 索引

```text
UNIQUE(login_session_id)
INDEX(owner_user_id)
INDEX(status)
INDEX(expires_at)
```

## 6.4 channel_message_logs

微信消息日志表。

### 字段设计

```text
id UUID PK
user_id UUID FK -> users.id
channel VARCHAR(32) NOT NULL DEFAULT 'wechat'
account_id VARCHAR(255)
message_id VARCHAR(255)
conversation_id VARCHAR(255) NOT NULL
channel_user_id VARCHAR(255)
direction VARCHAR(32) NOT NULL
content_type VARCHAR(32) NOT NULL DEFAULT 'text'
content TEXT
context_token TEXT
raw_payload JSONB
status VARCHAR(32) NOT NULL DEFAULT 'received'
retry_count INTEGER NOT NULL DEFAULT 0
error_code VARCHAR(64)
error_message TEXT
created_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id)
INDEX(channel)
INDEX(account_id)
INDEX(conversation_id)
INDEX(channel_user_id)
INDEX(direction)
INDEX(created_at)
UNIQUE(channel, account_id, message_id) WHERE message_id IS NOT NULL
```

## 6.5 wechat_channel_outbound_messages

微信通道出站消息表，用于记录通道侧接收并准备发送的消息。

### 字段设计

```text
id UUID PK
account_id VARCHAR(255) NOT NULL
message_id VARCHAR(255) NOT NULL
to_user_id VARCHAR(255) NOT NULL
conversation_id VARCHAR(255) NOT NULL
content TEXT NOT NULL
context_token TEXT
raw_payload JSONB
status VARCHAR(32) NOT NULL DEFAULT 'queued'
retry_count INTEGER NOT NULL DEFAULT 0
error_code VARCHAR(64)
error_message TEXT
sent_at TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(account_id)
INDEX(to_user_id)
INDEX(conversation_id)
INDEX(status)
INDEX(sent_at)
UNIQUE(account_id, message_id)
```

### 状态说明

```text
queued
sent
failed
```

### 设计说明

`sendmessage` 先把消息写入 `wechat_channel_outbound_messages`，状态为 `queued`。  
`wechat-channel` 进程中的调度任务会周期性扫描 queued 消息，派发成功后改为 `sent`，派发失败则改为 `failed` 并记录错误信息。  
同一条出站消息的最终状态会同步回写到 `channel_message_logs`，方便 Web Dashboard 和审计日志查看。  
这样可以把“协议接收”与“实际发送执行”拆开，避免通道接口和发送状态强耦合。

## 7. 日程业务域

## 7.1 calendar_events

固定时间日程表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
title VARCHAR(255) NOT NULL
description TEXT
start_time TIMESTAMPTZ NOT NULL
end_time TIMESTAMPTZ
timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai'
location VARCHAR(255)
source VARCHAR(32) NOT NULL DEFAULT 'agent'
status VARCHAR(32) NOT NULL DEFAULT 'active'
repeat_rule TEXT
external_calendar_id VARCHAR(255)
external_event_id VARCHAR(255)
created_by_channel VARCHAR(32)
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id, start_time)
INDEX(user_id, end_time)
INDEX(user_id, status)
INDEX(source)
INDEX(external_calendar_id)
INDEX(external_event_id)
```

### 约束

```text
status IN ('active', 'completed', 'cancelled', 'deleted')
end_time IS NULL OR end_time > start_time
```

## 7.2 task_items

弹性任务表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
title VARCHAR(255) NOT NULL
description TEXT
estimated_minutes INTEGER
deadline TIMESTAMPTZ
priority VARCHAR(32) NOT NULL DEFAULT 'medium'
status VARCHAR(32) NOT NULL DEFAULT 'pending'
source VARCHAR(32) NOT NULL DEFAULT 'agent'
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id, status)
INDEX(user_id, deadline)
INDEX(user_id, priority)
INDEX(created_at)
```

### 约束

```text
estimated_minutes IS NULL OR estimated_minutes > 0
priority IN ('low', 'medium', 'high', 'urgent')
status IN ('pending', 'planned', 'in_progress', 'completed', 'cancelled', 'deleted')
```

## 7.3 day_plans

每日计划表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
plan_date DATE NOT NULL
summary TEXT
status VARCHAR(32) NOT NULL DEFAULT 'draft'
source VARCHAR(32) NOT NULL DEFAULT 'agent'
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
UNIQUE(user_id, plan_date, status) WHERE status IN ('draft', 'confirmed', 'active')
INDEX(user_id, plan_date)
INDEX(user_id, status)
```

## 7.4 plan_items

每日计划中的具体安排。

### 字段设计

```text
id UUID PK
day_plan_id UUID NOT NULL FK -> day_plans.id
user_id UUID NOT NULL FK -> users.id
item_type VARCHAR(32) NOT NULL
ref_id UUID
title VARCHAR(255) NOT NULL
start_time TIMESTAMPTZ NOT NULL
end_time TIMESTAMPTZ NOT NULL
status VARCHAR(32) NOT NULL DEFAULT 'planned'
is_flexible BOOLEAN NOT NULL DEFAULT false
sort_order INTEGER DEFAULT 0
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(day_plan_id)
INDEX(user_id, start_time)
INDEX(user_id, status)
INDEX(item_type, ref_id)
```

### 约束

```text
end_time > start_time
item_type IN ('event', 'task', 'break', 'manual')
status IN ('planned', 'in_progress', 'completed', 'cancelled', 'skipped')
```

## 7.5 schedule_conflicts

冲突记录表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
conflict_type VARCHAR(64) NOT NULL
severity VARCHAR(32) NOT NULL DEFAULT 'medium'
title VARCHAR(255) NOT NULL
description TEXT
related_item_ids JSONB
suggestion TEXT
status VARCHAR(32) NOT NULL DEFAULT 'open'
detected_at TIMESTAMPTZ NOT NULL
resolved_at TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id, status)
INDEX(user_id, conflict_type)
INDEX(user_id, severity)
INDEX(detected_at)
GIN(related_item_ids)
```

## 7.6 reminder_jobs

提醒任务表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
target_type VARCHAR(64) NOT NULL
target_id UUID NOT NULL
title VARCHAR(255) NOT NULL
conversation_id VARCHAR(255) NOT NULL
trigger_time TIMESTAMPTZ NOT NULL
status VARCHAR(32) NOT NULL DEFAULT 'pending'
retry_count INTEGER NOT NULL DEFAULT 0
max_retries INTEGER NOT NULL DEFAULT 3
fired_at TIMESTAMPTZ
error_message TEXT
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id, trigger_time)
INDEX(status, trigger_time)
INDEX(user_id, status)
INDEX(target_type, target_id)
```

## 8. Agent 域

## 8.1 agent_run_logs

Agent 执行日志表。

### 字段设计

```text
id UUID PK
user_id UUID FK -> users.id
channel VARCHAR(32) NOT NULL DEFAULT 'wechat'
conversation_id VARCHAR(255)
input_text TEXT NOT NULL
intent VARCHAR(128)
graph_trace JSONB
tools_called JSONB
tool_args JSONB
tool_results JSONB
final_response TEXT
success BOOLEAN NOT NULL DEFAULT false
error_message TEXT
created_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id, created_at)
INDEX(intent)
INDEX(success)
GIN(graph_trace)
GIN(tools_called)
```

## 8.2 agent_pending_states

Agent 连续对话状态表。

### 字段设计

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id
conversation_id VARCHAR(255) NOT NULL
state_type VARCHAR(64) NOT NULL
state_payload JSONB NOT NULL
expires_at TIMESTAMPTZ NOT NULL
status VARCHAR(32) NOT NULL DEFAULT 'active'
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

### 索引

```text
INDEX(user_id, conversation_id, status)
INDEX(expires_at)
GIN(state_payload)
UNIQUE(user_id, conversation_id) WHERE status = 'active'
```

## 9. 系统配置域

## 9.1 system_settings

系统全局配置表，仅 owner 可管理。

### 字段设计

```text
id UUID PK
key VARCHAR(128) NOT NULL UNIQUE
value JSONB NOT NULL
description TEXT
is_sensitive BOOLEAN NOT NULL DEFAULT false
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

示例 key：

```text
LLM_BASE_URL
LLM_MODEL
LLM_API_KEY
DEFAULT_TIMEZONE
WECHAT_CHANNEL_CONFIG
SYSTEM_DAILY_PUSH_ENABLED
REMINDER_SCAN_INTERVAL_SECONDS
```

敏感字段如 LLM_API_KEY：

1. 存储时应加密。
2. 查询时不直接返回明文。
3. member 永远不可访问。

## 10. 数据关系总览

```text
users
  ├── user_settings
  ├── invite_codes.created_by_user_id
  ├── invite_code_usages.used_by_user_id
  ├── wechat_accounts
  ├── wechat_login_sessions
  ├── channel_identities
  ├── channel_message_logs
  ├── calendar_events
  ├── task_items
  ├── day_plans
  │     └── plan_items
  ├── schedule_conflicts
  ├── reminder_jobs
  ├── agent_run_logs
  └── agent_pending_states
```

## 11. 数据隔离规则

所有与业务相关的数据必须按 user_id 隔离。

必须隔离的表：

```text
calendar_events
task_items
day_plans
plan_items
schedule_conflicts
reminder_jobs
agent_run_logs
agent_pending_states
wechat_accounts
wechat_login_sessions
channel_message_logs
```

后端服务层必须保证：

```text
member 查询数据时强制附加 user_id = current_user.id
member 修改数据时必须验证数据归属
member 删除数据时必须验证数据归属
Agent 工具调用时 user_id 由系统注入
LLM 输出中的 user_id 必须忽略
```

## 12. 软删除策略

推荐使用状态字段实现软删除。

不建议物理删除核心业务数据。

例如：

```text
calendar_events.status = deleted
task_items.status = deleted
users.status = deleted
```

例外：短期验证码、过期登录会话可以定期物理清理。

## 13. 初始化要求

系统首次部署需要支持 owner 初始化。

推荐首版使用命令行脚本：

```text
python scripts/create_owner.py
```

系统启动时应写入默认配置：

```text
DEFAULT_TIMEZONE = Asia/Shanghai
REMINDER_SCAN_INTERVAL_SECONDS = 10
SYSTEM_DAILY_PUSH_ENABLED = false
```

## 14. 设计结论

最终数据库采用：

```text
PostgreSQL
+
SQLAlchemy 2.0
+
Alembic
+
UUID 主键
+
TIMESTAMPTZ 时间
+
JSONB 保存 Agent trace / tool results / pending state
```

核心原则：

1. 所有用户业务数据必须带 user_id。
2. member 只能访问自己的数据。
3. Agent 工具调用不能信任模型输出 user_id。
4. 日程、任务、计划、提醒、冲突全部可追踪。
5. Agent 执行过程必须可审计。
6. 微信消息必须记录。
7. 提醒任务必须可重试。
8. 外部日历同步预留字段。
