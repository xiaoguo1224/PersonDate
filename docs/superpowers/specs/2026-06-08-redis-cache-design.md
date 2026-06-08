# Redis 缓存层设计文档

## 1. 问题背景

Dashboard 今日页加载缓慢。根因分析：

- `ScheduledItem` 和 `TaskItem` 缺少 `user_id` 索引，每次查询全表扫描
- 冲突查询 `list_conflicts()` 全量加载到 Python 内存再过滤分页
- 无应用级缓存，每次页面加载触发 4 个并行请求直接查库
- 前端无客户端缓存，每次操作后全量重载

## 2. 设计目标

1. 引入 Redis 作为服务端缓存层，覆盖高频业务查询
2. 修复缺失的数据库索引，保证缓存 miss 时查询性能
3. 优化冲突查询，将分页逻辑下推到 SQL
4. 前端引入 SWR 做请求去重和客户端缓存
5. Redis 不可用时自动降级为直接查库

## 3. 架构概览

```
Next.js Dashboard
  ↓ (SWR 请求去重 + 客户端缓存)
FastAPI REST API
  ↓ (CacheManager 查询缓存)
Redis
  ↓ (cache miss 时)
SQLAlchemy → PostgreSQL
  ↓ (写操作时)
CacheInvalidator → Redis (主动失效)
```

## 4. 新增组件

| 组件 | 位置 | 职责 |
|---|---|---|
| `RedisClient` | `backend/app/core/redis.py` | Redis 连接管理，`redis-py` 同步客户端 |
| `CacheManager` | `backend/app/core/cache.py` | 统一缓存读写接口，封装 key 生成、序列化、TTL 兜底 |
| `CacheInvalidator` | `backend/app/core/cache_invalidator.py` | 写操作时按实体类型批量删除相关缓存 key |
| SWR Hooks | `web/hooks/use*.ts` | 前端请求缓存和去重 |

## 5. 缓存 Key 命名规范

```
schedule:user:{user_id}:events:date:{date}
schedule:user:{user_id}:events:range:{start}:{end}
schedule:user:{user_id}:tasks:status:{status}
schedule:user:{user_id}:conflicts:status:{status}
schedule:user:{user_id}:reminders:status:{status}
schedule:user:{user_id}:settings
schedule:system:settings
schedule:weather:{location_hash}
schedule:agent:pending:{conversation_id}
```

## 6. 各实体缓存策略

### 6.1 日程 (ScheduledItem)

- 缓存 key：`schedule:user:{user_id}:events:date:{date}` 和 `schedule:user:{user_id}:events:range:{start}:{end}`
- 读：`list_by_date()` 时先查 Redis，miss 则查库并回填
- 写失效：`create` / `update` / `delete` 时，删除该用户所有 `events:*` key
- TTL 兜底：10 分钟

### 6.2 任务 (TaskItem)

- 缓存 key：`schedule:user:{user_id}:tasks:status:{status}`
- 读：`list_tasks()` 时先查 Redis
- 写失效：`create` / `update` / `complete` / `delete` 时，删除该用户所有 `tasks:*` key
- TTL 兜底：10 分钟

### 6.3 冲突 (ScheduleConflict)

- 缓存 key：`schedule:user:{user_id}:conflicts:status:{status}`
- 读：`list_conflicts()` 时先查 Redis
- 写失效：`detect_item_conflicts()` / `resolve_conflict()` / `dismiss_conflict()` 时，删除该用户所有 `conflicts:*` key
- 冲突检测本身不缓存，只缓存查询结果
- TTL 兜底：10 分钟

### 6.4 提醒 (ReminderJob)

- 缓存 key：`schedule:user:{user_id}:reminders:status:{status}`
- 读：`list_jobs()` 时先查 Redis
- 写失效：`create` / `update` / `cancel` / `mark_sent` 时，删除该用户所有 `reminders:*` key
- TTL 兜底：10 分钟

### 6.5 用户配置 (UserSettings)

- 缓存 key：`schedule:user:{user_id}:settings`
- 读：`get_or_create()` 时先查 Redis
- 写失效：`update_settings()` 时删除对应 key
- TTL 兜底：30 分钟

### 6.6 系统设置 (SystemSetting)

- 缓存 key：`schedule:system:settings`
- 读：`list_settings()` / `get_value()` 时先查 Redis
- 写失效：`set_value()` / `update_settings()` 时删除 key
- TTL 兜底：30 分钟

### 6.7 天气 (Weather API)

- 缓存 key：`schedule:weather:{location_hash}`
- 迁移现有内存 dict 缓存到 Redis
- TTL 兜底：1 小时

### 6.8 Agent Pending State

- 缓存 key：`schedule:agent:pending:{conversation_id}`
- 写入 pending state 时同步写 Redis
- 读取时先查 Redis，miss 则查库
- 状态变更（confirmed / cancelled / expired）时删除 Redis key
- TTL 兜底：5 分钟

## 7. 缓存穿透防护

- 所有缓存 miss 后查库，查到结果（包括空列表）都回填 Redis
- 不缓存 `None` 或异常结果
- 查询参数为空或非法时不走缓存，直接查库

## 8. 数据库索引修复

缓存 miss 时仍需快速查库，补充缺失索引：

| 表 | 索引名 | 列 | 理由 |
|---|---|---|---|
| `scheduled_items` | `ix_scheduled_items_user_start` | `(user_id, start_time)` | 日程查询最高频路径 |
| `task_items` | `ix_task_items_user_status` | `(user_id, status)` | 任务列表按用户 + 状态过滤 |
| `channel_message_logs` | `ix_message_logs_conversation_dir_time` | `(conversation_id, direction, created_at)` | 消息日志查询 |

## 9. 冲突查询优化

当前 `list_conflicts()` 问题：
- 全量加载到 Python 内存再过滤分页
- 每次调用还跑 `_resolve_stale_open_conflicts()`

优化方案：
- 分页逻辑下推到 SQL，不再全量加载
- `_resolve_stale_open_conflicts()` 移出读路径，仅在写操作时触发
- 对 `related_item_ids` JSON 字段的 Python 侧过滤评估是否可改为 SQL 条件

## 10. 前端 SWR 客户端缓存

引入 SWR 解决重复请求问题：

- `loadTodayDashboard()` 的 4 个请求改用 `useSWR` hook
- SWR 自动做请求去重、后台刷新、错误重试
- 页面切换回来时不重新请求，直接用缓存数据
- Agent 操作后通过 `mutate()` 精确失效相关 key，而非全量重载

新增 hooks：
- `web/hooks/useScheduledItems.ts`
- `web/hooks/useTasks.ts`
- `web/hooks/useConflicts.ts`
- `web/hooks/useReminders.ts`

改造：
- `web/lib/dashboard.ts` 中的 `loadTodayDashboard()` 逻辑
- 各页面组件改用 SWR hook 获取数据

## 11. 部署变更

### Docker Compose

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6380:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes
  restart: unless-stopped
```

外部端口 6380，内部 6379。

### 后端依赖

```
redis>=5.0
```

### 前端依赖

```
swr
```

### 环境变量

```
REDIS_URL=redis://redis:6379/0
```

## 12. 容错降级

Redis 不可用时系统不能崩溃，降级为直接查库：

- `CacheManager.get()` 捕获 `redis.ConnectionError` / `redis.TimeoutError`，降级返回 `None`
- `CacheManager.set()` 捕获异常，静默忽略
- `CacheInvalidator.invalidate()` 捕获异常，静默忽略
- 所有缓存操作对 Service 层透明

## 13. 文件变更清单

### 新增文件

| 文件 | 说明 |
|---|---|
| `backend/app/core/redis.py` | Redis 连接管理 |
| `backend/app/core/cache.py` | CacheManager |
| `backend/app/core/cache_invalidator.py` | 缓存失效逻辑 |
| `web/hooks/useScheduledItems.ts` | SWR hook |
| `web/hooks/useTasks.ts` | SWR hook |
| `web/hooks/useConflicts.ts` | SWR hook |
| `web/hooks/useReminders.ts` | SWR hook |
| `backend/alembic/versions/xxx_add_perf_indexes.py` | 索引迁移 |

### 修改文件

| 文件 | 变更内容 |
|---|---|
| `backend/app/core/config.py` | 新增 `REDIS_URL` |
| `backend/app/db/session.py` | 初始化 Redis 连接 |
| `backend/app/services/scheduled_item_service.py` | 缓存读写 + 失效 |
| `backend/app/services/task_service.py` | 缓存读写 + 失效 |
| `backend/app/services/conflict_service.py` | 缓存读写 + 失效 + 查询优化 |
| `backend/app/services/reminder_service.py` | 缓存读写 + 失效 |
| `backend/app/services/user_service.py` | UserSettings 缓存 |
| `backend/app/services/system_setting_service.py` | 系统设置缓存 |
| `backend/app/services/daily_notification_service.py` | 天气缓存迁移到 Redis |
| `backend/app/services/agent_pending_state_service.py` | Pending state 缓存 |
| `backend/app/models/scheduled_item.py` | 新增复合索引 |
| `backend/app/models/task_item.py` | 新增复合索引 |
| `backend/app/models/channel_message_log.py` | 新增复合索引 |
| `web/lib/dashboard.ts` | 改造为 SWR hook 调用 |
| `web/app/dashboard/today/page.tsx` | 使用 SWR hooks |
| `docker-compose.yml` | 新增 Redis 服务 |
| `backend/.env.example` | 新增 REDIS_URL |

## 14. 实现顺序

```
第 1 步：基础设施
  - Redis 连接管理 (core/redis.py)
  - CacheManager (core/cache.py)
  - CacheInvalidator (core/cache_invalidator.py)
  - 配置项 (config.py, .env.example)
  - docker-compose Redis 服务

第 2 步：数据库索引
  - Alembic 迁移：scheduled_items、task_items、channel_message_logs 索引

第 3 步：后端缓存接入（按服务逐个改造）
  - system_setting_service.py（最简单，先验证缓存层可用）
  - user_service.py (UserSettings)
  - scheduled_item_service.py
  - task_service.py
  - reminder_service.py
  - conflict_service.py（含查询优化）
  - daily_notification_service.py（天气缓存迁移）

第 4 步：Agent 缓存
  - agent_pending_state_service.py

第 5 步：前端 SWR
  - 新增 4 个 SWR hooks
  - 改造 dashboard.ts 和 today page
  - 改造其他页面

第 6 步：验证
  - Docker 构建 + 启动
  - 接口响应时间对比
  - Redis 缓存命中率检查
```

## 15. 测试策略

| 测试类型 | 覆盖范围 |
|---|---|
| 单元测试 | CacheManager key 生成、序列化、TTL 逻辑 |
| 单元测试 | CacheInvalidator 失效规则正确性 |
| 集成测试 | 各 Service 缓存读写 + 失效流程（fakeredis） |
| 集成测试 | 缓存 miss → 查库 → 回填完整链路 |
| 集成测试 | Redis 不可用时降级为直接查库 |
| 前端测试 | SWR hooks 数据获取和缓存行为 |
| 性能测试 | Dashboard 接口响应时间对比 |
