# Web Dashboard 页面与权限设计文档 v1.0

## 1. Web 定位

Web Dashboard 是系统的日程驾驶舱，不是主业务入口。

Web 负责：

1. 展示每日计划。
2. 展示日历视图。
3. 管理任务池。
4. 展示冲突事项。
5. 展示提醒任务。
6. 展示 Agent 日志。
7. 完成邀请码注册和用户管理。
8. 完成微信绑定。
9. 管理系统设置。

## 2. 技术栈

```text
Next.js
React
TypeScript
Ant Design
FullCalendar 或自定义时间轴
```

## 3. 角色菜单

### 3.1 owner 菜单

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

### 3.2 member 菜单

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

member 不显示：

```text
用户管理
邀请码管理
系统设置
模型配置
微信通道状态
全局消息日志
全局 Agent 日志
```

## 4. 页面设计

### 4.1 登录页

路径：

```text
/login
```

功能：

```text
用户名密码登录
跳转邀请码注册
```

调用 API：

```http
POST /api/auth/login
```

### 4.2 邀请码注册页

路径：

```text
/register
```

功能：

```text
输入邀请码
创建用户名和密码
注册为 member
```

调用 API：

```http
POST /api/auth/register-with-invite
```

### 4.3 今日计划页

路径：

```text
/dashboard/today
```

功能：

```text
展示今日时间轴
展示固定日程
展示弹性任务
展示空闲时间
展示冲突标记
展示 Agent 建议
支持标记完成
支持重新规划
支持直接新增和编辑计划项
```

调用 API：

```http
GET /api/day-plans/{date}
GET /api/conflicts?status=open
POST /api/day-plans/{id}/regenerate
PATCH /api/plan-items/{id}/complete
POST /api/plan-items
PATCH /api/plan-items/{id}
DELETE /api/plan-items/{id}
```

### 4.4 日历视图页

路径：

```text
/dashboard/calendar
```

功能：

```text
月视图
周视图
日视图
展示 calendar_events
展示 plan_items
点击查看详情
手动创建日程
编辑日程
删除日程
手动新增计划项
编辑计划项
完成计划项
删除计划项
```

调用 API：

```http
GET /api/calendar-events
POST /api/calendar-events
PATCH /api/calendar-events/{id}
DELETE /api/calendar-events/{id}
POST /api/plan-items
PATCH /api/plan-items/{id}
PATCH /api/plan-items/{id}/complete
DELETE /api/plan-items/{id}
```

### 4.5 任务池页

路径：

```text
/dashboard/tasks
```

功能：

```text
展示未安排任务
展示任务优先级
展示截止时间
创建任务
编辑任务
删除任务
标记完成
触发 Agent 安排任务
```

调用 API：

```http
GET /api/tasks
POST /api/tasks
PATCH /api/tasks/{id}
DELETE /api/tasks/{id}
PATCH /api/tasks/{id}/complete
POST /api/day-plans/{date}/generate
```

### 4.6 冲突事项页

路径：

```text
/dashboard/conflicts
```

功能：

```text
展示冲突列表
展示冲突严重程度
展示涉及事项
展示建议
忽略冲突
标记解决
重新规划
```

调用 API：

```http
GET /api/conflicts
PATCH /api/conflicts/{id}/ignore
PATCH /api/conflicts/{id}/resolve
POST /api/conflicts/detect
```

### 4.7 提醒任务页

路径：

```text
/dashboard/reminders
```

功能：

```text
展示 pending / fired / failed 提醒
查看失败原因
取消提醒
手动测试触发
```

调用 API：

```http
GET /api/reminders
PATCH /api/reminders/{id}/cancel
POST /api/reminders/{id}/test-fire
```

### 4.8 Agent 日志页

路径：

```text
/dashboard/agent-logs
```

member：只显示自己的 Agent 日志。

owner：可查看全局 Agent 日志。

调用 API：

```http
GET /api/my-agent-logs
GET /api/admin/agent-logs
```

展示字段：

```text
时间
用户输入
intent
工具调用
工具结果
最终回复
成功/失败
错误信息
```

### 4.9 微信绑定页

路径：

```text
/dashboard/wechat-binding
```

功能：

```text
查看当前微信绑定账号
创建二维码登录会话
展示二维码
刷新登录状态
查看通道账号
解绑微信
```

调用 API：

```http
POST /api/me/wechat-login-sessions
GET /api/me/wechat-login-sessions/{id}
POST /api/me/wechat-login-sessions/{id}/confirm
GET /api/me/wechat-accounts
GET /api/me/channel-identities
DELETE /api/me/channel-identities/{id}
```

### 4.10 邀请码管理页

路径：

```text
/admin/invite-codes
```

权限：owner。

功能：

```text
创建邀请码
查看邀请码
查看使用次数
禁用邀请码
查看使用记录
```

调用 API：

```http
POST /api/admin/invite-codes
GET /api/admin/invite-codes
PATCH /api/admin/invite-codes/{id}/disable
GET /api/admin/invite-codes/{id}/usages
```

### 4.11 用户管理页

路径：

```text
/admin/users
```

权限：owner。

功能：

```text
查看 member 用户
禁用用户
启用用户
查看微信绑定状态
```

调用 API：

```http
GET /api/admin/users
PATCH /api/admin/users/{id}/disable
PATCH /api/admin/users/{id}/enable
GET /api/admin/users/{id}/channel-identities
```

### 4.12 系统设置页

路径：

```text
/admin/settings
```

权限：owner。

功能：

```text
配置默认时区
配置提醒扫描间隔
配置系统默认提醒规则
配置 LLM Base URL
配置 LLM Model
配置 LLM API Key
```

调用 API：

```http
GET /api/admin/system-settings
PATCH /api/admin/system-settings
```

敏感信息：

```text
LLM_API_KEY 不明文展示，只显示是否已配置。
```

### 4.13 微信通道状态页

路径：

```text
/admin/wechat-status
```

权限：owner。

功能：

```text
查看通道连接状态
查看绑定账号列表
查看最近入站消息
查看最近出站消息
发送测试消息
```

调用 API：

```http
GET /api/admin/wechat/status
POST /api/admin/wechat/send-test
GET /api/admin/message-logs
```

## 5. 权限要求

前端按角色隐藏菜单，但后端必须强制校验。

权限规则：

1. owner 可访问 admin 页面。
2. member 不可访问 admin 页面。
3. member 所有数据查询仅限自己的 `user_id`。
4. 直接访问 admin URL 时，前端应跳转 403 页面。
5. 后端返回 403 时，前端展示无权限提示。

## 6. Web 设计结论

Web Dashboard 必须服务于两个目标：

1. 普通用户查看和管理自己的日程计划。
2. owner 管理系统、邀请码、用户和日志。
