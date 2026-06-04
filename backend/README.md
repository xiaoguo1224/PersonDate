# 微信智能日程规划 Agent 后端

## 本地运行

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## 环境变量

```text
DATABASE_URL
JWT_SECRET
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
DEFAULT_TIMEZONE
REMINDER_SCAN_INTERVAL_SECONDS
WECHAT_CHANNEL_TOKEN
```
