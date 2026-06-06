# API 接口设计文档 v1.0

## 1. 接口设计原则

后端采用 FastAPI，所有业务接口统一以 `/api` 为前缀。

接口设计遵守以下原则：

1. Web Dashboard 通过 REST API 访问后端。
2. 微信通道通过专用接口将消息转发给后端。
3. Agent 工具调用通过内部 Tool Executor 完成，首版不直接暴露给外部用户。
4. owner 和 member 共享个人业务接口，但返回数据必须按 `user_id` 隔离。
5. owner 专属接口必须做 RBAC 校验。
6. 所有写操作需要认证，除登录、注册、owner 初始化、微信入站回调外。
7. 所有分页接口统一使用 `page` / `page_size`。
8. 所有时间统一使用 ISO 8601 字符串。

## 2. 通用响应格式

成功响应：

```json
{
  "success": true,
  "data": {},
  "message": "ok"
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误说明"
  }
}
```

分页响应：

```json
{
  "success": true,
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100
  },
  "message": "ok"
}
```

## 3. 认证接口

### 3.1 登录

```http
POST /api/auth/login
```

请求：

```json
{
  "username": "owner",
  "password": "password"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "access_token": "jwt_token",
    "token_type": "bearer",
    "user": {
      "id": "uuid",
      "username": "owner",
      "display_name": "主用户",
      "role": "owner"
    }
  }
}
```

### 3.2 邀请码注册

```http
POST /api/auth/register-with-invite
```

请求：

```json
{
  "invite_code": "ABCD-1234",
  "username": "user1",
  "password": "password",
  "display_name": "用户1",
  "email": "user1@example.com"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "role": "member"
  },
  "message": "注册成功"
}
```

### 3.3 当前用户信息

```http
GET /api/auth/me
```

权限：登录用户。

### 3.4 登出

```http
POST /api/auth/logout
```

权限：登录用户。

## 4. owner 初始化接口

### 4.1 检查系统是否已初始化

```http
GET /api/setup/status
```

响应：

```json
{
  "success": true,
  "data": {
    "initialized": false
  }
}
```

### 4.2 初始化 owner

```http
POST /api/setup/owner
```

仅系统未初始化时可用。

请求：

```json
{
  "username": "owner",
  "password": "password",
  "display_name": "主用户",
  "email": "owner@example.com"
}
```

## 5. 邀请码接口

### 5.1 创建邀请码

```http
POST /api/admin/invite-codes
```

权限：owner。

请求：

```json
{
  "max_uses": 1,
  "expires_at": "2026-12-31T23:59:59+08:00",
  "remark": "给朋友使用"
}
```

### 5.2 邀请码列表

```http
GET /api/admin/invite-codes?page=1&page_size=20
```

权限：owner。

### 5.3 禁用邀请码

```http
PATCH /api/admin/invite-codes/{id}/disable
```

权限：owner。

### 5.4 邀请码使用记录

```http
GET /api/admin/invite-codes/{id}/usages
```

权限：owner。

## 6. 用户管理接口

### 6.1 用户列表

```http
GET /api/admin/users?page=1&page_size=20
```

权限：owner。

### 6.2 禁用用户

```http
PATCH /api/admin/users/{id}/disable
```

权限：owner。

### 6.3 启用用户

```http
PATCH /api/admin/users/{id}/enable
```

权限：owner。

### 6.4 查看用户微信绑定

```http
GET /api/admin/users/{id}/channel-identities
```

权限：owner。

## 7. 个人设置接口

### 7.1 获取个人设置

```http
GET /api/me/settings
```

权限：owner/member。

### 7.2 修改个人设置

```http
PATCH /api/me/settings
```

权限：owner/member。

请求：

```json
{
  "default_timezone": "Asia/Shanghai",
  "workday_start_time": "09:00:00",
  "workday_end_time": "18:00:00",
  "daily_plan_push_time": "08:00:00",
  "daily_plan_push_enabled": true,
  "default_remind_before_minutes": 10
}
```

## 8. 微信绑定接口

### 8.1 创建微信二维码登录会话

```http
POST /api/me/wechat-login-sessions
```

权限：owner/member。

响应：

```json
{
  "success": true,
  "data": {
    "login_session_id": "login_001",
    "qr_payload": "wechat-qr-payload",
    "expires_at": "2026-06-04T21:00:00+08:00",
    "status": "qr_created"
  },
  "message": "请使用微信扫码完成登录"
}
```

### 8.2 查看二维码登录会话状态

```http
GET /api/me/wechat-login-sessions/{id}
```

权限：owner/member。

### 8.3 确认二维码登录会话

```http
POST /api/me/wechat-login-sessions/{id}/confirm
```

请求：

```json
{
  "account_id": "wx_account_001",
  "wechat_user_id": "wx_user_001",
  "bot_token": "token_001",
  "base_url": "https://wechat.example.com",
  "remark": "测试账号"
}
```

### 8.4 查看我的通道账号

```http
GET /api/me/wechat-accounts
```

权限：owner/member。

### 8.5 查看我的微信绑定

```http
GET /api/me/channel-identities
```

权限：owner/member。

### 8.6 解绑微信

```http
DELETE /api/me/channel-identities/{id}
```

权限：owner/member，仅能解绑自己的绑定。

## 9. 微信通道接口

### 9.1 微信入站消息

```http
POST /api/wechat/inbound
```

用途：微信通道服务或 WeChat Channel Adapter 将微信消息转发给后端。

请求：

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

响应：

```json
{
  "success": true,
  "data": {
    "handled": true,
    "reply": "已为你创建安排：开会，时间为明天下午 3 点。"
  }
}
```

说明：

1. 如果消息来自未绑定账号，返回绑定提示。
2. 如果用户已绑定，进入 SchedulePlanningGraph。
3. 该接口需要验证来自微信通道的签名或内部 token。

### 9.2 微信发送调试接口

```http
POST /api/admin/wechat/send-test
```

权限：owner。

### 9.3 微信通道状态

```http
GET /api/admin/wechat/status
```

权限：owner。

响应建议包含：

```text
connected
channel_token_configured
total_accounts
active_accounts
queued_outbound_messages
sent_outbound_messages
failed_outbound_messages
total_identities
active_identities
bound_users
last_message_at
recent_inbound_messages
recent_outbound_messages
```

## 10. 安排接口

### 10.1 创建固定安排

```http
POST /api/calendar-events
```

权限：owner/member。

请求：

```json
{
  "title": "项目会议",
  "description": "",
  "start_time": "2026-06-05T15:00:00+08:00",
  "end_time": "2026-06-05T16:00:00+08:00",
  "timezone": "Asia/Shanghai",
  "location": "",
  "remind_before_minutes": 10
}
```

响应：

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "conflicts": [],
    "reminder_job_id": "uuid"
  }
}
```

### 10.2 查询安排

```http
GET /api/calendar-events?start_time=2026-06-05T00:00:00+08:00&end_time=2026-06-05T23:59:59+08:00
```

权限：owner/member。member 只能返回自己的安排。

### 10.3 修改安排

```http
PATCH /api/calendar-events/{id}
```

权限：owner/member，仅能修改自己的安排。

### 10.4 删除安排

```http
DELETE /api/calendar-events/{id}
```

权限：owner/member，仅能删除自己的安排。

### 10.5 搜索候选安排

```http
GET /api/calendar-events/search?keyword=会议&date=2026-06-05
```

权限：owner/member。

## 11. 任务接口

### 11.1 创建弹性任务

```http
POST /api/tasks
```

请求：

```json
{
  "title": "写论文",
  "description": "",
  "estimated_minutes": 120,
  "deadline": "2026-06-06T23:59:59+08:00",
  "priority": "high"
}
```

### 11.2 查询任务

```http
GET /api/tasks?status=pending&page=1&page_size=20
```

### 11.3 修改任务

```http
PATCH /api/tasks/{id}
```

### 11.4 删除任务

```http
DELETE /api/tasks/{id}
```

### 11.5 标记完成

```http
PATCH /api/tasks/{id}/complete
```

## 12. 每日计划接口

### 12.1 查询某日计划

```http
GET /api/day-plans/{date}
```

示例：

```http
GET /api/day-plans/2026-06-05
```

### 12.2 生成安排草案

```http
POST /api/day-plans/{date}/generate
```

请求：

```json
{
  "include_pending_tasks": true,
  "auto_detect_conflicts": true
}
```

### 12.3 确认计划

```http
POST /api/day-plans/{id}/confirm
```

### 12.4 重新生成计划

```http
POST /api/day-plans/{id}/regenerate
```

请求：

```json
{
  "feedback": "下午不要安排太满"
}
```

### 12.5 新增安排项

```http
POST /api/plan-items
```

请求：

```json
{
  "plan_date": "2026-06-05",
  "title": "写论文",
  "item_type": "task",
  "start_time": "2026-06-05T17:00:00+08:00",
  "end_time": "2026-06-05T19:00:00+08:00",
  "status": "planned",
  "is_flexible": true,
  "sort_order": 0
}
```

### 12.6 更新安排项

```http
PATCH /api/plan-items/{id}
```

### 12.7 标记安排项完成

```http
PATCH /api/plan-items/{id}/complete
```

### 12.8 删除安排项

```http
DELETE /api/plan-items/{id}
```

## 13. 冲突接口

### 13.1 查询冲突

```http
GET /api/conflicts?status=open&page=1&page_size=20
```

### 13.2 检测某日冲突

```http
POST /api/conflicts/detect
```

请求：

```json
{
  "date": "2026-06-05"
}
```

### 13.3 忽略冲突

```http
PATCH /api/conflicts/{id}/ignore
```

### 13.4 标记解决

```http
PATCH /api/conflicts/{id}/resolve
```

## 14. 提醒接口

### 14.1 查询提醒任务

```http
GET /api/reminders?status=pending&page=1&page_size=20
```

### 14.2 取消提醒

```http
PATCH /api/reminders/{id}/cancel
```

### 14.3 手动触发提醒测试

```http
POST /api/reminders/{id}/test-fire
```

权限：owner/member，仅能触发自己的提醒；owner 可触发全局用于调试。

## 15. Agent 调试接口

### 15.1 Web 模拟 Agent 消息

```http
POST /api/agent/debug/message
```

权限：owner/member。

请求：

```json
{
  "message": "明天写论文 2 小时，帮我安排一下"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "final_response": "我建议明天 09:00-11:00 写论文，是否确认？",
    "intent": "create_task",
    "tools_called": [],
    "pending_state": {}
  }
}
```

说明：该接口用于 Web 调试，应走与微信相同的 SchedulePlanningGraph，但 `channel = web`。

### 15.2 Web 正式 Agent 消息

```http
POST /api/me/agent/message
```

权限：登录用户。

请求：

```json
{
  "message": "明天写论文 2 小时，帮我安排一下"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "final_response": "我建议明天 09:00-11:00 写论文，是否确认？",
    "intent": "create_task",
    "tools_called": [],
    "pending_state": {}
  }
}
```

说明：

1. 该接口用于 Web Dashboard 的正式自然语言入口。
2. 该接口应走与微信相同的 SchedulePlanningGraph，但 `channel = web`。
3. 该接口的 `conversation_id` 由后端根据当前登录用户生成，避免与调试入口互相干扰。

### 15.3 我的 Agent 日志

```http
GET /api/my-agent-logs?page=1&page_size=20
```

### 15.4 全局 Agent 日志

```http
GET /api/admin/agent-logs?page=1&page_size=20
```

权限：owner。

## 16. 消息日志接口

### 16.1 我的微信消息日志

```http
GET /api/my-message-logs?page=1&page_size=20
```

### 16.2 全局微信消息日志

```http
GET /api/admin/message-logs?page=1&page_size=20
```

权限：owner。

### 16.3 微信出站队列

```http
GET /api/admin/wechat/outbound-queue?account_id=...&conversation_id=...&status=queued&limit=100
```

权限：owner。

## 17. 系统设置接口

### 17.1 获取系统设置

```http
GET /api/admin/system-settings
```

权限：owner。

### 17.2 修改系统设置

```http
PATCH /api/admin/system-settings
```

权限：owner。

请求：

```json
{
  "LLM_BASE_URL": "https://api.example.com",
  "LLM_MODEL": "deepseek-chat",
  "DEFAULT_TIMEZONE": "Asia/Shanghai",
  "REMINDER_SCAN_INTERVAL_SECONDS": 10
}
```

敏感字段如 `LLM_API_KEY` 不应在 GET 响应中明文返回。

## 18. 错误码

常用错误码：

```text
AUTH_INVALID_CREDENTIALS
AUTH_UNAUTHORIZED
AUTH_FORBIDDEN
USER_DISABLED
INVITE_CODE_INVALID
INVITE_CODE_EXPIRED
INVITE_CODE_USED_UP
WECHAT_NOT_BOUND
WECHAT_BIND_CODE_INVALID
RESOURCE_NOT_FOUND
RESOURCE_FORBIDDEN
AGENT_PARSE_FAILED
AGENT_PENDING_STATE_NOT_FOUND
SCHEDULE_CONFLICT
REMINDER_SEND_FAILED
VALIDATION_ERROR
INTERNAL_ERROR
```

## 19. API 设计结论

本系统 API 分为：

1. Auth API：登录、注册、当前用户。
2. Admin API：邀请码、用户管理、系统设置、全局日志。
3. Personal API：安排、待办、计划、冲突、提醒、个人设置。
4. WeChat API：微信入站、绑定、发送。
5. Agent API：调试与日志。

核心约束：

1. member 所有查询必须按当前 `user_id` 隔离。
2. owner 才能访问 admin 接口。
3. 微信入站接口必须先映射 `channel_identity`。
4. Web 调试 Agent 和微信 Agent 必须走同一套 SchedulePlanningGraph。
