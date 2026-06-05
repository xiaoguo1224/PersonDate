# 微信智能日程规划 Agent

本项目采用 `FastAPI + PostgreSQL + SQLAlchemy + Alembic + LangGraph + APScheduler + Next.js`。
日常开发推荐通过 Docker 启动，避免本机环境错乱。

## 启动

```bash
docker compose up -d --build
```

如果你需要做局部开发，也可以按各子目录的说明用本机环境启动，但默认建议优先走 Docker。

启动后可访问：

- 后端：`http://localhost:8000`
- Web：`http://localhost:3000`

## 停止

```bash
docker compose down
```

## 查看日志

```bash
docker compose logs -f backend
docker compose logs -f web
docker compose logs -f postgres
```

## 默认管理员

- 用户名：`admin`
- 密码：读取 `backend/.env` 里的 `ADMIN_PASSWORD`

## 开发说明

- `openclaw-weixin` 只作为微信消息通道，不使用 OpenClaw Runtime。
- Agent 先行，消息通道后置。
- 新功能完成后需要先验证，再做独立 git 提交。
