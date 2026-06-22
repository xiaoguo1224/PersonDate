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
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_MINUTES
AUTH_COOKIE_MAX_AGE_SECONDS
ADMIN_PASSWORD
DEFAULT_TIMEZONE
REMINDER_SCAN_INTERVAL_SECONDS
WECHAT_POLL_INTERVAL_SECONDS
WECHAT_CHANNEL_BASE_URL
```

## Docker 环境建议

- `JWT_SECRET` 建议至少 32 位，避免启动和测试时出现弱密钥警告。
- `ACCESS_TOKEN_EXPIRE_MINUTES` 默认 30 分钟。
- `REFRESH_TOKEN_EXPIRE_MINUTES` 默认 7 天，用于刷新 access token。
- `AUTH_COOKIE_MAX_AGE_SECONDS` 控制 Web 登录 cookie 的有效期，默认 604800 秒。
- `ADMIN_PASSWORD` 是初始化 `admin` 账号的密码。
- `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 只在需要真实模型能力时填写。
- `WECHAT_CHANNEL_BASE_URL` 是我们自研微信通道服务的地址，本地调试通常填 `http://127.0.0.1:18789`，Docker 内部互联使用 `http://wechat-channel:18789`。
