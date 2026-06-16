# PersonDate

> WeChat-native AI schedule planner for people who want to manage time by chatting naturally.

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](./LICENSE)
[![WeChat-first](https://img.shields.io/badge/WeChat--first-0A84FF.svg?style=for-the-badge)](./README.md)
[![LangGraph ReAct](https://img.shields.io/badge/LangGraph-ReAct-111827.svg?style=for-the-badge)](./README.md)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=for-the-badge)](./README.md)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791.svg?style=for-the-badge)](./README.md)

PersonDate is a self-hostable, multi-user intelligent scheduling system. You can tell it things like "Tomorrow at 3 PM meeting" or "Plan 2 hours for writing tomorrow," and it will understand the message, create or adjust schedules, detect conflicts, generate a daily plan, and send reminders back to WeChat.

## What makes it different

Most scheduling tools stop at reminders or calendar CRUD. PersonDate is designed as a real planning assistant:

- **It starts from chat, not forms** - users can describe intent naturally
- **It can reason over time** - tasks, free slots, conflicts, and daily plans are handled together
- **It has a real execution loop** - the agent calls tools, tools call services, services write data
- **It keeps control deterministic** - conflict detection and reminders are not left to the model
- **It works as a system, not a widget** - web dashboard, permissions, binding, logs, and reminders all fit together

## Preview

<table>
  <tr>
    <td width="50%">
      <img src="./public/readme/persondate-hero-top.png" alt="PersonDate landing page preview" />
      <br />
      <sub>Landing page preview</sub>
    </td>
    <td width="50%">
      <img src="./public/readme/persondate-dashboard-viewport.png" alt="PersonDate dashboard preview" />
      <br />
      <sub>Dashboard preview</sub>
    </td>
  </tr>
</table>

This project is built for developers who want:

- a practical AI assistant instead of a demo chatbot
- a WeChat-first scheduling experience
- LangGraph ReAct agent flows with tool calling and confirmation
- deterministic conflict detection and reminder delivery
- a full web dashboard for review and administration

## Why this project is worth a star

- **WeChat as the main entry** - chat with your schedule where your attention already is
- **Agent-first architecture** - the core workflow is a real planning graph, not keyword matching
- **Deterministic business logic** - conflict detection and reminders are handled by services, not by guesswork
- **Multi-user ready** - owner/member roles, invite codes, binding, RBAC, and data isolation
- **Self-hostable** - FastAPI, PostgreSQL, Redis, Next.js, Docker Compose
- **Built for extension** - clear boundaries for tools, services, and dashboards

## What it can do

- Create schedules from natural language
- Create flexible tasks and turn them into time blocks
- Generate daily plans from available time slots
- Detect conflicts and suggest rescheduling options
- Send reminders through WeChat
- Review schedules, tasks, conflicts, reminders, and Agent logs in a web dashboard
- Support invite-code registration and WeChat binding
- Separate owner and member permissions cleanly

## Best for

- solo users who want a serious AI time assistant
- developers exploring LangGraph and tool calling in a real product
- self-hosters who want control over data and workflow
- teams looking for an opinionated scheduling system they can extend

## Example flows

```text
明天下午 3 点开会
明天有什么安排？
明天写论文 2 小时，帮我安排一下
把明天下午 3 点的会议改到 4 点
删除明天下午 4 点的会议
```

## Tech Stack

| Layer | Stack |
| --- | --- |
| Backend | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic |
| Agent | LangGraph / langchain_openai.ChatOpenAI / LangChain tools |
| Database | PostgreSQL |
| Cache | Redis 7+ |
| Scheduler | APScheduler |
| Frontend | Next.js / React / TypeScript / Ant Design |
| Channel | openclaw-weixin as message transport only |
| Deployment | Docker Compose |

## Architecture

```text
WeChat User
  ↓
openclaw-weixin
  ↓
WeChat Channel Adapter
  ↓
FastAPI Schedule Agent Service
  ↓
LangGraph SchedulePlanningGraph
  ↓
Tool calls → Business services → PostgreSQL / Redis
  ↓
APScheduler Reminder Worker
  ↓
WeChat User
```

Web access path:

```text
Next.js Web Dashboard → FastAPI REST API → PostgreSQL / Redis
```

## Getting Started

### Requirements

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- pnpm recommended
- uv recommended

### Start with Docker Compose

```bash
docker compose up -d --build
```

Expected entry points:

- Backend API: `http://localhost:8000`
- Web Dashboard: `http://localhost:3000`

### Local backend development

```bash
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Local frontend development

```bash
cd web
pnpm install
pnpm dev
```

## Environment Variables

Create `backend/.env` based on `.env.example`.

```env
DATABASE_URL=postgresql://user:password@localhost:5432/persondate
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4o
DEFAULT_TIMEZONE=Asia/Shanghai
REMINDER_SCAN_INTERVAL_SECONDS=60
WECHAT_CHANNEL_TOKEN=your-wechat-token
ADMIN_PASSWORD=your-admin-password
```

## Repository Layout

```text
PersonDate/
├── backend/       FastAPI backend, agent, services, workers, migrations
├── web/           Next.js dashboard
├── docs/          Design docs and implementation references
├── docker-compose.yml
└── README*.md
```

## Documentation

The design docs under `docs/` are the source of truth for architecture, data model, API design, agent flow, WeChat channel boundaries, dashboard pages, and implementation order.

- [Requirements](./docs/01-requirements.md)
- [Architecture](./docs/02-architecture-design.md)
- [Database](./docs/03-database-design.md)
- [API](./docs/04-api-design.md)
- [Agent](./docs/05-agent-langgraph-design.md)
- [WeChat Channel](./docs/06-wechat-channel-design.md)
- [Web Dashboard](./docs/07-web-dashboard-design.md)
- [Codex Tasks](./docs/08-codex-tasks.md)

## Roadmap

- Agent capability loop
- Web dashboard and role-based pages
- WeChat channel integration
- Reminder and conflict polishing
- Documentation and test coverage
- GitHub release polish, badges, and onboarding improvements

## Contributing

Issues and pull requests are welcome.

If you want to help, the best starting points are:

1. improve the README and onboarding flow
2. strengthen agent behavior and confirmation logic
3. add tests for scheduling, conflicts, and reminders
4. refine the dashboard UX

## License

This repository is intended to be published as an open-source project, but the final license has not been added yet. Add a LICENSE file before public release to match your preferred distribution terms.
