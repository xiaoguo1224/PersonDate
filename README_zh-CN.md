# PersonDate

> 微信里的 AI 智能日程规划助手，聊天就能管理日程、待办、计划和提醒。

[![MIT 许可证](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](./LICENSE)
[![微信优先](https://img.shields.io/badge/WeChat--first-0A84FF.svg?style=for-the-badge)](./README_zh-CN.md)
[![LangGraph ReAct](https://img.shields.io/badge/LangGraph-ReAct-111827.svg?style=for-the-badge)](./README_zh-CN.md)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=for-the-badge)](./README_zh-CN.md)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791.svg?style=for-the-badge)](./README_zh-CN.md)

PersonDate 是一个可自托管的轻量多用户智能日程规划系统。你只需要在微信里说一句“明天下午 3 点开会”或者“明天写论文 2 小时，帮我安排一下”，系统就会理解你的自然语言，创建或调整安排，检测冲突，生成每日计划，并在合适的时间通过微信提醒你。

## 它和普通工具的区别

大多数日程工具只做提醒或日历增删改查。PersonDate 更像一个真正的安排助手：

- **从聊天开始** - 用户可以直接说自然语言，不需要填表
- **能理解时间** - 任务、空闲时间、冲突和每日计划一起处理
- **有真实执行链路** - Agent 调工具，工具调服务，服务落数据库
- **关键逻辑可控** - 冲突检测和提醒由程序负责，不把关键结果交给模型猜
- **不是一个单页小工具** - Web 驾驶舱、权限、绑定、日志、提醒都在同一套系统里

## 界面预览

<table>
  <tr>
    <td width="50%">
      <img src="./public/readme/persondate-hero-top.png" alt="PersonDate 首页预览" />
      <br />
      <sub>首页预览</sub>
    </td>
    <td width="50%">
      <img src="./public/readme/persondate-dashboard-viewport.png" alt="PersonDate 驾驶舱预览" />
      <br />
      <sub>驾驶舱预览</sub>
    </td>
  </tr>
</table>

这个项目适合想做这些事情的人：

- 把 AI 真正用在日程管理里，而不是只做演示聊天框
- 做一个微信优先的个人效率工具
- 研究 LangGraph ReAct、工具调用和确认流程
- 用确定性服务处理冲突检测和提醒，而不是把一切都交给大模型
- 自己部署一套完整的日程助手

## 为什么值得关注

- **微信是主入口** - 直接在你每天都在用的聊天场景里管理时间
- **Agent 先行** - 核心能力是一个真实的规划图，而不是关键词匹配器
- **业务逻辑确定性** - 冲突检测、提醒、数据隔离都由服务层完成
- **支持多用户** - owner/member、邀请码、绑定、RBAC、数据隔离一整套都有
- **可以自托管** - FastAPI、PostgreSQL、Redis、Next.js、Docker Compose
- **适合扩展** - 工具、服务、页面边界清晰，方便二次开发

## 它能做什么

- 用自然语言创建日程
- 创建待办任务并自动排进时间块
- 根据可用时间生成每日计划
- 检测冲突并给出调整建议
- 通过微信发送提醒
- 在 Web 驾驶舱里查看日程、待办、冲突、提醒和 Agent 日志
- 支持邀请码注册和微信绑定
- 清晰区分 owner 和 member 权限

## 适合谁

- 想要一个真正能用的 AI 时间助手的个人用户
- 想研究 LangGraph 和工具调用的开发者
- 想自托管、掌控数据和流程的人
- 想在现有项目基础上继续扩展的团队

## 示例输入

```text
明天下午 3 点开会
明天有什么安排？
明天写论文 2 小时，帮我安排一下
把明天下午 3 点的会议改到 4 点
删除明天下午 4 点的会议
```

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic |
| Agent | LangGraph / langchain_openai.ChatOpenAI / LangChain tools |
| 数据库 | PostgreSQL |
| 缓存 | Redis 7+ |
| 调度 | APScheduler |
| 前端 | Next.js / React / TypeScript / Ant Design |
| 通道 | openclaw-weixin，仅作为消息通道 |
| 部署 | Docker Compose |

## 系统架构

```text
微信用户
  ↓
openclaw-weixin
  ↓
WeChat Channel Adapter
  ↓
FastAPI Schedule Agent Service
  ↓
LangGraph SchedulePlanningGraph
  ↓
工具调用 → 业务服务 → PostgreSQL / Redis
  ↓
APScheduler Reminder Worker
  ↓
微信用户
```

Web 访问链路：

```text
Next.js Web Dashboard → FastAPI REST API → PostgreSQL / Redis
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- 推荐 `pnpm`
- 推荐 `uv`

### 使用 Docker Compose 启动

```bash
docker compose up -d --build
```

启动后可访问：

- 后端 API：`http://localhost:8000`
- Web 驾驶舱：`http://localhost:3000`

### 本地启动后端

```bash
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### 本地启动前端

```bash
cd web
pnpm install
pnpm dev
```

## 环境变量

根据 `backend/.env.example` 创建 `backend/.env`。

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

## 仓库结构

```text
PersonDate/
├── backend/       FastAPI 后端、Agent、业务服务、Worker、迁移
├── web/           Next.js 驾驶舱
├── docs/          设计文档和实现依据
├── docker-compose.yml
└── README*.md
```

## 文档

`docs/` 目录下的文档是本项目的实现依据，包含架构、数据模型、接口、Agent 流程、微信通道边界、Web 页面和开发顺序。

- [需求文档](./docs/01-requirements.md)
- [架构设计](./docs/02-architecture-design.md)
- [数据库设计](./docs/03-database-design.md)
- [接口设计](./docs/04-api-design.md)
- [Agent 设计](./docs/05-agent-langgraph-design.md)
- [微信通道设计](./docs/06-wechat-channel-design.md)
- [Web 驾驶舱设计](./docs/07-web-dashboard-design.md)
- [Codex 任务拆分](./docs/08-codex-tasks.md)

## 路线图

- 完成 Agent 能力闭环
- 完成 Web 驾驶舱和角色页面
- 接入微信通道
- 强化提醒和冲突处理体验
- 补充测试和文档
- 补全 GitHub 发布细节、徽章和新手引导

## 参与贡献

欢迎提交 Issue 和 Pull Request。

如果你想帮这个项目提速，可以从下面几个方向入手：

1. 优化 README 和上手流程
2. 强化 Agent 行为和确认逻辑
3. 补充日程、冲突和提醒测试
4. 打磨 Web 驾驶舱体验

## 许可证

这个仓库已经补充了 `MIT` 许可证，可以直接作为开源项目对外发布。
