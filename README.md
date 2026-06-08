# PersonDate - WeChat Smart Schedule Planning Agent

> A lightweight multi-user intelligent schedule planning system powered by WeChat and LangGraph Agent.

[English](#english) | [中文](#中文)

---

## English

### Overview

PersonDate is a WeChat-driven intelligent schedule planning system. Users interact via natural language through WeChat to create schedules, manage tasks, generate daily plans, detect conflicts, and receive reminders. A Web Dashboard serves as the command center for viewing schedules, tasks, conflicts, reminders, and Agent logs.

### Key Features

- **WeChat Natural Language Interaction** — Create schedules, tasks, and reminders by chatting with the Agent
- **LangGraph Agent** — Intent recognition, information extraction, multi-turn confirmation, conflict handling
- **Conflict Detection** — Automatic time overlap detection when creating or editing schedules, with interactive resolution flow
- **Daily Plan Generation** — Automatically arrange pending tasks into available time slots
- **Reminder System** — APScheduler-based reminders delivered via WeChat
- **Web Dashboard** — Today's schedule, calendar views, task pool, conflicts, reminders, Agent logs
- **Multi-user via Invite Codes** — Lightweight user system with owner/member roles
- **WeChat Binding** — Bind your WeChat account to the web system via binding codes

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic |
| Agent | LangGraph / OpenAI-compatible SDK / Pydantic v2 |
| Database | PostgreSQL |
| Reminders | APScheduler |
| Frontend | Next.js / React / TypeScript / Ant Design |
| WeChat Channel | openclaw-weixin (message channel only) |
| Deployment | Docker Compose |

### Architecture

```
WeChat User
  ↓
openclaw-weixin (message channel)
  ↓
WeChat Channel Adapter
  ↓
FastAPI Schedule Agent Service
  ↓
LangGraph SchedulePlanningGraph
  ↓
Tool Executor → Business Services → PostgreSQL
  ↓
APScheduler Reminder Worker
  ↓
WeChat Channel → WeChat User
```

Web access path:

```
Next.js Web Dashboard → FastAPI REST API → PostgreSQL
```

### Getting Started

#### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- pnpm (recommended) or npm
- uv (recommended) or pip

#### Docker Compose (Recommended)

```bash
docker compose up -d --build
```

Services will be available at:

- Backend API: `http://localhost:8000`
- Web Dashboard: `http://localhost:3000`

#### Backend Setup (Local Development)

```bash
cd backend
uv sync
cp .env.example .env  # Edit with your configuration
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

#### Frontend Setup (Local Development)

```bash
cd web
pnpm install
pnpm dev
```

### Environment Variables

Create a `.env` file in the `backend/` directory:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/persondate
JWT_SECRET=your-secret-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4o
DEFAULT_TIMEZONE=Asia/Shanghai
REMINDER_SCAN_INTERVAL_SECONDS=60
WECHAT_CHANNEL_TOKEN=your-wechat-token
ADMIN_PASSWORD=your-admin-password
```

### Default Admin Account

- Username: `admin`
- Password: Check `ADMIN_PASSWORD` in `backend/.env`

### Project Structure

```
PersonDate/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/routes/       # REST API endpoints
│   │   ├── agent/            # LangGraph Agent (graph, nodes, prompts)
│   │   ├── tools/            # Agent tool registry and executor
│   │   ├── services/         # Business logic services
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── workers/          # APScheduler reminder worker
│   └── alembic/              # Database migrations
├── web/                      # Next.js frontend
│   ├── app/
│   │   ├── dashboard/        # Dashboard pages (today, calendar, tasks, conflicts, etc.)
│   │   ├── login/            # Login page
│   │   └── register/         # Registration page
│   ├── components/           # Shared React components
│   └── lib/                  # API client, types, utilities
├── docs/                     # Project design documents
└── docker-compose.yml
```

### Testing

```bash
# Backend
cd backend
uv run pytest
uv run ruff check .
uv run mypy app

# Frontend
cd web
pnpm typecheck
pnpm lint
```

### License

Private project for personal use.

---

## 中文

### 项目概述

PersonDate 是一个基于微信消息通道的轻量多用户智能日程规划系统。用户通过微信自然语言输入日程、任务、提醒，系统由 Agent 进行理解、拆解、规划、冲突检测和提醒。Web Dashboard 作为安排驾驶舱，展示今日安排、日历视图、待办、冲突事项、提醒任务和 Agent 日志。

### 核心功能

- **微信自然语言交互** — 通过与 Agent 对话创建日程、任务和提醒
- **LangGraph Agent** — 意图识别、信息抽取、多轮确认、冲突处理
- **冲突检测** — 创建或编辑安排时自动检测时间重叠，交互式解决冲突
- **每日计划生成** — 自动将待办任务安排到可用时间段
- **提醒系统** — 基于 APScheduler 的提醒，通过微信发送
- **Web 驾驶舱** — 今日安排、日历视图、任务池、冲突事项、提醒任务、Agent 日志
- **邀请码多用户** — 轻量级用户体系，支持 owner/member 角色
- **微信绑定** — 通过绑定码将微信账号与 Web 系统关联

### 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic |
| Agent | LangGraph / OpenAI-compatible SDK / Pydantic v2 |
| 数据库 | PostgreSQL |
| 提醒调度 | APScheduler |
| 前端 | Next.js / React / TypeScript / Ant Design |
| 微信通道 | openclaw-weixin（仅作为消息通道） |
| 部署 | Docker Compose |

### 系统架构

```
微信用户
  ↓
openclaw-weixin（消息通道）
  ↓
WeChat Channel Adapter
  ↓
FastAPI Schedule Agent Service
  ↓
LangGraph SchedulePlanningGraph
  ↓
Tool Executor → Business Services → PostgreSQL
  ↓
APScheduler Reminder Worker
  ↓
WeChat Channel → 微信用户
```

Web 访问链路：

```
Next.js Web Dashboard → FastAPI REST API → PostgreSQL
```

### 快速开始

#### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- pnpm（推荐）或 npm
- uv（推荐）或 pip

#### Docker Compose 启动（推荐）

```bash
docker compose up -d --build
```

启动后可访问：

- 后端 API：`http://localhost:8000`
- Web 驾驶舱：`http://localhost:3000`

#### 后端启动（本地开发）

```bash
cd backend
uv sync
cp .env.example .env  # 编辑配置
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

#### 前端启动（本地开发）

```bash
cd web
pnpm install
pnpm dev
```

### 环境变量

在 `backend/` 目录下创建 `.env` 文件：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/persondate
JWT_SECRET=your-secret-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4o
DEFAULT_TIMEZONE=Asia/Shanghai
REMINDER_SCAN_INTERVAL_SECONDS=60
WECHAT_CHANNEL_TOKEN=your-wechat-token
ADMIN_PASSWORD=your-admin-password
```

### 默认管理员账号

- 用户名：`admin`
- 密码：查看 `backend/.env` 中的 `ADMIN_PASSWORD`

### 项目结构

```
PersonDate/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/routes/       # REST API 接口
│   │   ├── agent/            # LangGraph Agent（图、节点、提示词）
│   │   ├── tools/            # Agent 工具注册和执行器
│   │   ├── services/         # 业务逻辑服务
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应 Schema
│   │   └── workers/          # APScheduler 提醒 Worker
│   └── alembic/              # 数据库迁移
├── web/                      # Next.js 前端
│   ├── app/
│   │   ├── dashboard/        # 仪表盘页面（今日、日历、任务、冲突等）
│   │   ├── login/            # 登录页
│   │   └── register/         # 注册页
│   ├── components/           # 共享 React 组件
│   └── lib/                  # API 客户端、类型、工具函数
├── docs/                     # 项目设计文档
└── docker-compose.yml
```

### 测试

```bash
# 后端
cd backend
uv run pytest
uv run ruff check .
uv run mypy app

# 前端
cd web
pnpm typecheck
pnpm lint
```

### 开发说明

- Agent 先行，消息通道后置。必须先保证 Agent 能力闭环，再接入微信消息通道。
- 微信通道使用 `openclaw-weixin` 仅作为消息收发通道，不使用 OpenClaw Runtime。
- 新功能完成后需要先验证，再做独立 git 提交。

### 许可证

个人使用项目，非开源。
