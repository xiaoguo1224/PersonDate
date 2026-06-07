import { requestJson } from "@/lib/api";

// ── 新类型: ScheduledItem（统一安排） ──────────────────────────

export type ScheduledItem = {
  id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  timezone: string;
  location: string | null;
  source: string;
  source_task_id: string | null;
  remind_before_minutes: number | null;
  status: string;
  sort_order: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ScheduledItemCreatePayload = {
  title: string;
  description?: string | null;
  start_time: string;
  end_time: string;
  timezone?: string;
  location?: string | null;
  source_task_id?: string | null;
  remind_before_minutes?: number | null;
};

export type ScheduledItemUpdatePayload = {
  title?: string;
  description?: string | null;
  start_time?: string;
  end_time?: string;
  timezone?: string;
  location?: string | null;
  remind_before_minutes?: number | null;
  status?: string;
};

// ── 任务类型 ────────────────────────────────────────────────

export type TaskItem = {
  id: string;
  title: string;
  description?: string | null;
  estimated_minutes?: number | null;
  deadline?: string | null;
  priority: string;
  status: string;
};

export type TaskCreatePayload = {
  title: string;
  description?: string | null;
  estimated_minutes?: number | null;
  deadline?: string | null;
  priority: string;
};

export type TaskListResponse = {
  items: TaskItem[];
};

// ── 安排 API ──────────────────────────────────────────────

export async function loadScheduledItems(
  params: {
    start_time?: string;
    end_time?: string;
    date?: string;
    keyword?: string;
    status?: string;
  },
  accessToken?: string,
): Promise<ScheduledItem[]> {
  const query = new URLSearchParams();
  if (params.start_time) query.set("start_time", params.start_time);
  if (params.end_time) query.set("end_time", params.end_time);
  if (params.date) query.set("date", params.date);
  if (params.keyword) query.set("keyword", params.keyword);
  if (params.status) query.set("status", params.status);
  const resp = await requestJson<{ items: ScheduledItem[] }>(
    `/api/scheduled-items?${query.toString()}`,
    {},
    accessToken,
  );
  return resp.items;
}

export async function createScheduledItem(
  data: ScheduledItemCreatePayload,
  accessToken?: string,
): Promise<ScheduledItem> {
  return requestJson<ScheduledItem>("/api/scheduled-items", {
    method: "POST",
    body: JSON.stringify(data),
  }, accessToken);
}

export async function updateScheduledItem(
  id: string,
  data: ScheduledItemUpdatePayload,
  accessToken?: string,
): Promise<ScheduledItem> {
  return requestJson<ScheduledItem>(
    `/api/scheduled-items/${id}`,
    { method: "PATCH", body: JSON.stringify(data) },
    accessToken,
  );
}

export async function deleteScheduledItem(id: string, accessToken?: string): Promise<void> {
  await requestJson(`/api/scheduled-items/${id}`, { method: "DELETE" }, accessToken);
}

export async function completeScheduledItem(id: string, accessToken?: string): Promise<ScheduledItem> {
  return requestJson<ScheduledItem>(
    `/api/scheduled-items/${id}/complete`,
    { method: "PATCH" },
    accessToken,
  );
}

export async function generateDayDrafts(
  planDate: string,
  accessToken?: string,
  options?: { include_pending_tasks?: boolean; auto_detect_conflicts?: boolean }
): Promise<ScheduledItem[]> {
  const resp = await requestJson<{ items: ScheduledItem[] }>(
    `/api/scheduled-items/generate/${planDate}`,
    { method: "POST", body: JSON.stringify(options || {}) },
    accessToken,
  );
  return resp.items;
}

export async function confirmDayDrafts(planDate: string, accessToken?: string): Promise<void> {
  await requestJson("/api/scheduled-items/confirm", {
    method: "POST",
    body: JSON.stringify({ plan_date: planDate }),
  }, accessToken);
}

// ── 格式化工具 ───────────────────────────────────────────

export function formatDateTime(value: string, timeZone?: string) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

// ── 任务 API ─────────────────────────────────────────────

export async function loadTasks(status?: string, accessToken?: string): Promise<TaskItem[]> {
  const query = status ? `?status=${status}` : "";
  const resp = await requestJson<{ items: TaskItem[] }>(
    `/api/tasks${query}`,
    {},
    accessToken,
  );
  return resp.items;
}

export async function createTask(data: TaskCreatePayload): Promise<TaskItem> {
  return requestJson<TaskItem>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTask(
  id: string,
  data: Partial<TaskItem>
): Promise<TaskItem> {
  return requestJson<TaskItem>(`/api/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteTask(id: string): Promise<void> {
  await requestJson(`/api/tasks/${id}`, { method: "DELETE" });
}

export async function completeTask(id: string): Promise<TaskItem> {
  return requestJson<TaskItem>(`/api/tasks/${id}/complete`, {
    method: "PATCH",
  });
}

// ── 冲突 API ─────────────────────────────────────────────

export type ConflictItem = {
  id: string;
  conflict_type: string;
  severity: string;
  title: string;
  description?: string | null;
  related_item_ids?: Record<string, string> | null;
  suggestion?: string | null;
  status: string;
  detected_at: string;
  resolved_at?: string | null;
};

export async function loadConflicts(
  status?: string,
  accessToken?: string,
): Promise<ConflictItem[]> {
  const query = status ? `?status=${status}` : "";
  const resp = await requestJson<{ items: ConflictItem[] }>(
    `/api/conflicts${query}`,
    {},
    accessToken,
  );
  return resp.items;
}

export async function ignoreConflict(id: string): Promise<void> {
  await requestJson(`/api/conflicts/${id}/ignore`, { method: "POST" });
}

export async function resolveConflict(id: string): Promise<void> {
  await requestJson(`/api/conflicts/${id}/resolve`, { method: "POST" });
}

// ── 提醒 API ─────────────────────────────────────────────

export type ReminderItem = {
  id: string;
  target_type: string;
  target_id: string;
  title: string;
  trigger_time: string;
  status: string;
  retry_count?: number;
  max_retries?: number;
  error_message?: string | null;
  conversation_id?: string | null;
};

export async function loadReminders(status?: string, accessToken?: string): Promise<ReminderItem[]> {
  const query = status ? `?status=${status}` : "";
  const resp = await requestJson<{ items: ReminderItem[] }>(
    `/api/reminders${query}`,
    {},
    accessToken,
  );
  return resp.items;
}

export async function cancelReminder(id: string): Promise<void> {
  await requestJson(`/api/reminders/${id}/cancel`, { method: "POST" });
}

// ── Agent 消息 ──────────────────────────────────────────

export type AgentMessageResponse = {
  success: boolean;
  final_response?: string | null;
  intent?: string | null;
  tool_calls: Array<Record<string, unknown>>;
  tool_results: Array<Record<string, unknown>>;
  pending_state?: Record<string, unknown> | null;
  graph_trace: string[];
  error?: string | null;
};

export async function sendAgentMessage(
  accessToken: string,
  message: string,
): Promise<AgentMessageResponse> {
  return requestJson<AgentMessageResponse>(
    "/api/me/agent/message",
    {
      method: "POST",
      body: JSON.stringify({ message }),
    },
    accessToken,
  );
}

// ── 首页仪表盘 ───────────────────────────────────────────

export type DashboardSummary = Record<string, unknown>;

export type TodayDashboardData = {
  events: ScheduledItem[];
  tasks: TaskItem[];
  conflicts: ConflictItem[];
  reminders: ReminderItem[];
  summary?: DashboardSummary;
};

export async function loadTodayDashboard(accessToken?: string, timezone?: string): Promise<TodayDashboardData> {
  const today = getTodayDateKey(timezone);
  const [events, tasks, conflicts, reminders] = await Promise.all([
    loadScheduledItems({ date: today }, accessToken),
    loadTasks(undefined, accessToken),
    loadConflicts("open", accessToken),
    loadReminders("pending", accessToken),
  ]);
  return { events, tasks, conflicts, reminders };
}

export function formatRange(
  start: string,
  end: string | null | undefined,
  timezone?: string
): string {
  const s = new Date(start);
  const e = end ? new Date(end) : null;
  const fmt: Intl.DateTimeFormatOptions = {
    hour: "2-digit",
    minute: "2-digit",
  };
  if (timezone) fmt.timeZone = timezone;
  const startStr = s.toLocaleTimeString("zh-CN", fmt);
  const endStr = e ? e.toLocaleTimeString("zh-CN", fmt) : "";
  return endStr ? `${startStr} - ${endStr}` : startStr;
}

export function formatClock(value: string, timeZone?: string): string {
  const d = new Date(value);
  const fmt: Intl.DateTimeFormatOptions = {
    hour: "2-digit",
    minute: "2-digit",
  };
  if (timeZone) fmt.timeZone = timeZone;
  return d.toLocaleTimeString("zh-CN", fmt);
}

export function getDateKey(value: string | Date, timeZone?: string): string {
  const d = typeof value === "string" ? new Date(value) : value;
  const fmt: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: timeZone || "Asia/Shanghai",
  };
  return d.toLocaleDateString("en-CA", fmt);
}

export function getTodayDateKey(timeZone?: string): string {
  return getDateKey(new Date(), timeZone);
}
