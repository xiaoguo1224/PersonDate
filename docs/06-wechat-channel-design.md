# 微信通道接入文档 v1.0

## 1. 接入目标

本系统不使用 OpenClaw Runtime，只使用 `openclaw-weixin` 相关微信消息能力作为微信通道。

微信通道目标：

1. 接收微信文本消息。
2. 将微信消息转发给 FastAPI 后端。
3. 接收 FastAPI 后端生成的回复。
4. 将回复发送给微信用户。
5. 支持 Reminder Worker 主动发送提醒消息。

## 2. 总体链路

```text
微信用户
  ↓
openclaw-weixin
  ↓
WeChat Channel Adapter
  ↓
POST /api/wechat/inbound
  ↓
FastAPI Schedule Agent Service
  ↓
SchedulePlanningGraph
  ↓
final_response
  ↓
WeChat Channel Adapter
  ↓
openclaw-weixin
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
  ↓
openclaw-weixin
  ↓
微信用户
```

## 3. WeChat Channel Adapter 职责

WeChat Channel Adapter 是本项目自己封装的适配层。

职责：

1. 适配 openclaw-weixin 的消息格式。
2. 转换为系统标准入站消息。
3. 调用 FastAPI 的 `/api/wechat/inbound`。
4. 接收后端返回的 reply。
5. 调用 openclaw-weixin 发送消息。
6. 提供发送接口给 Reminder Worker。
7. 记录发送结果。

## 4. 标准入站消息格式

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

字段说明：

```text
message_id：微信侧消息唯一 ID，用于去重。
conversation_id：会话 ID，用于后续回复和提醒。
channel_user_id：微信侧用户 ID，用于绑定系统用户。
display_name：微信昵称。
content_type：首版只支持 text。
content：文本内容。
raw_payload：原始消息。
```

## 5. 入站处理规则

FastAPI 收到 `/api/wechat/inbound` 后：

1. 写入 `channel_message_logs`，`direction = inbound`。
2. 根据 `message_id` 做幂等去重。
3. 如果 `content` 是“绑定 xxxxxx”，进入绑定流程。
4. 否则根据 `channel_user_id` / `conversation_id` 查找 `channel_identity`。
5. 如果未绑定，返回绑定提示。
6. 如果用户已禁用，返回账号不可用提示。
7. 如果绑定有效，进入 SchedulePlanningGraph。
8. 保存 agent_run_log。
9. 返回 final_response。

未绑定用户回复：

```text
你还没有绑定账号，请先在 Web 中使用邀请码注册并绑定微信。
```

禁用用户回复：

```text
你的账号当前不可用，请联系系统主用户。
```

## 6. 微信绑定流程

### 6.1 Web 生成绑定码

用户登录 Web 后调用：

```http
POST /api/me/wechat-binding-code
```

系统生成 6 位绑定码，例如：

```text
123456
```

Web 提示：

```text
请在微信中发送：绑定 123456
```

### 6.2 微信发送绑定码

用户在微信发送：

```text
绑定 123456
```

系统流程：

1. WeChat Channel Adapter 收到消息。
2. 调用 `/api/wechat/inbound`。
3. 后端识别绑定命令。
4. 查询 `wechat_binding_codes`。
5. 校验 code 是否存在、未使用、未过期。
6. 写入 `channel_identities`。
7. 更新 `binding_code.status = used`。
8. 回复微信绑定成功。

绑定成功回复：

```text
绑定成功，你现在可以通过微信使用日程 Agent 了。
```

绑定失败回复：

```text
绑定码无效或已过期，请在 Web 中重新生成。
```

## 7. 出站消息格式

FastAPI 内部统一使用：

```json
{
  "channel": "wechat",
  "conversation_id": "wx_user_001",
  "content_type": "text",
  "content": "已为你创建日程：开会，时间为明天下午 3 点。"
}
```

## 8. 消息发送接口

后端内部服务：

```text
WechatChannelService.send_text(conversation_id, content)
```

职责：

1. 调用 openclaw-weixin 发送能力。
2. 写入 `channel_message_logs`，`direction = outbound`。
3. 发送成功 `status = sent`。
4. 发送失败 `status = failed`，并记录 `error_message`。

## 9. 提醒发送规则

Reminder Worker 到点后：

1. 根据 `reminder_job.conversation_id` 找到会话。
2. 生成提醒内容。
3. 调用 `WechatChannelService.send_text`。
4. 成功后 `reminder_job.status = fired`。
5. 失败后 `retry_count + 1`。

提醒文本示例：

```text
提醒：15:00 项目会议即将开始。
```

## 10. 幂等和去重

微信入站消息必须基于：

```text
channel + message_id
```

做唯一约束。

如果收到重复消息：

1. 不重复进入 Agent。
2. 可返回之前的处理结果，或直接返回 success。
3. 不允许重复创建日程。

## 11. 安全要求

1. `/api/wechat/inbound` 应配置内部 token 或签名校验。
2. 不接受未知来源请求。
3. `raw_payload` 保存原始消息，便于排查。
4. 发送接口不暴露给 member。
5. owner 可在 Web 查看微信通道状态和消息日志。

## 12. 调试接口

为便于开发，保留调试接口：

```http
POST /api/agent/debug/message
```

它不经过 openclaw-weixin，但必须进入同一个 SchedulePlanningGraph。

同时可保留：

```http
POST /api/admin/wechat/send-test
```

用于 owner 测试微信发送。

## 13. 微信通道设计结论

最终链路：

```text
openclaw-weixin 只做消息收发。
WeChat Channel Adapter 负责格式转换和发送封装。
FastAPI 后端负责 Agent、用户、权限、日程和提醒。
```
