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
WECHAT_CHANNEL_TOKEN
```
