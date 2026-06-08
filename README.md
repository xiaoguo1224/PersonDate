# PersonDate

[简体中文](./README_zh-CN.md)

A lightweight multi-user intelligent schedule planning system powered by WeChat and LangGraph Agent.

Users interact via natural language through WeChat to create schedules, manage tasks, generate daily plans, detect conflicts, and receive reminders. A Web Dashboard serves as the command center for viewing schedules, tasks, conflicts, reminders, and Agent logs.

## Features

- **WeChat Natural Language Interaction** — Create schedules, tasks, and reminders by chatting with the Agent
- **LangGraph Agent** — Intent recognition, information extraction, multi-turn confirmation, conflict handling
- **Conflict Detection** — Automatic time overlap detection when creating or editing schedules, with interactive resolution flow
- **Daily Plan Generation** — Automatically arrange pending tasks into available time slots
- **Reminder System** — APScheduler-based reminders delivered via WeChat
- **Web Dashboard** — Today's schedule, calendar views, task pool, conflicts, reminders, Agent logs
- **Multi-user via Invite Codes** — Lightweight user system with owner/member roles
- **WeChat Binding** — Bind your WeChat account to the web system via binding codes

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic |
| Agent | LangGraph / OpenAI-compatible SDK / Pydantic v2 |
| Database | PostgreSQL |
| Reminders | APScheduler |
| Frontend | Next.js / React / TypeScript / Ant Design |
| WeChat Channel | openclaw-weixin (message channel only) |
| Deployment | Docker Compose |

## Architecture

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

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- pnpm (recommended) or npm
- uv (recommended) or pip

### Docker Compose (Recommended)

```bash
docker compose up -d --build
```

Services will be available at:

- Backend API: `http://localhost:8000`
- Web Dashboard: `http://localhost:3000`

### Backend Setup (Local Development)

```bash
cd backend
uv sync
cp .env.example .env  # Edit with your configuration
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Frontend Setup (Local Development)

```bash
cd web
pnpm install
pnpm dev
```

## Environment Variables

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

## Default Admin Account

- Username: `admin`
- Password: Check `ADMIN_PASSWORD` in `backend/.env`

## Project Structure

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

## Testing

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

## Development Notes

- Agent-first approach: ensure Agent capabilities are complete before integrating WeChat message channel.
- WeChat channel uses `openclaw-weixin` as a message transport only; OpenClaw Runtime is not used.
- Each completed feature should be verified independently before committing.

## License

Private project for personal use.
