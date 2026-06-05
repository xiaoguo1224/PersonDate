# 微信智能日程规划 Agent 后端

## 推荐启动方式

```bash
docker compose up -d --build
```

## 说明

- 后端服务推荐由 `docker compose` 启动。
- 启动时会自动执行 Alembic 迁移并初始化 `admin` owner。
- 如需临时调试，也可以按本机环境单独启动，但日常验证优先走 Docker。

## 环境变量

```text
DATABASE_URL
JWT_SECRET
ADMIN_PASSWORD
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
DEFAULT_TIMEZONE
REMINDER_SCAN_INTERVAL_SECONDS
WECHAT_POLL_INTERVAL_SECONDS
WECHAT_CHANNEL_BASE_URL
WECHAT_CHANNEL_TOKEN
```

## Docker 环境建议

- `JWT_SECRET` 建议至少 32 位，避免启动和测试时出现弱密钥警告。
- `ADMIN_PASSWORD` 是初始化 `admin` 账号的密码。
- `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 只在需要真实模型能力时填写。
- `WECHAT_CHANNEL_BASE_URL` 可以先留空；当前 `wechat-channel` 进程在未配置外部通道时会保持空闲，不会阻塞 Docker 启动。
