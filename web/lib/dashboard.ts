import { requestJson } from "@/lib/api";

export type DayPlanItem = {
  id: string;
  day_plan_id: string;
  title: string;
  item_type: string;
  start_time: string;
  end_time: string;
  status: string;
  is_flexible: boolean;
  sort_order?: number | null;
  ref_id?: string | null;
};

export type DayPlan = {
  id: string;
  plan_date: string;
  summary?: string | null;
  status: string;
  items: DayPlanItem[];
};

export type CalendarEventItem = {
  id: string;
  title: string;
  description?: string | null;
  start_time: string;
  end_time?: string | null;
  timezone: string;
  location?: string | null;
  status: string;
  remind_before_minutes?: number | null;
};

export type CalendarEventsResponse = {
  items: CalendarEventItem[];
};

export type CalendarEventUpsertPayload = {
  title: string;
  description?: string | null;
  start_time: string;
  end_time?: string | null;
  timezone: string;
  location?: string | null;
  remind_before_minutes?: number | null;
};

export type PlanItemUpsertPayload = {
  plan_date: string;
  title: string;
  item_type: string;
  start_time: string;
  end_time: string;
  status: string;
  is_flexible: boolean;
  sort_order?: number | null;
  ref_id?: string | null;
};

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

export type ConflictItem = {
  id: string;
  conflict_type: string;
  severity: string;
  title: string;
  description?: string | null;
  related_item_ids?: string[];
  suggestion?: string | null;
  status: string;
  detected_at: string;
};

export type ConflictListResponse = {
  items: ConflictItem[];
};

export type ReminderItem = {
  id: string;
  target_type: string;
  target_id: string;
  title: string;
  conversation_id: string;
  trigger_time: string;
  status: string;
  retry_count: number;
  max_retries: number;
};

export type ReminderListResponse = {
  items: ReminderItem[];
};

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

export type TodayDashboardData = {
  plan: DayPlan | null;
  events: CalendarEventItem[];
  tasks: TaskItem[];
  conflicts: ConflictItem[];
  reminders: ReminderItem[];
};

export async function loadTodayDashboard(
  accessToken: string,
  planDate: string,
): Promise<TodayDashboardData> {
  const todayEventsPath = `/api/calendar-events?start_date=${encodeURIComponent(planDate)}&end_date=${encodeURIComponent(planDate)}`;
  const [plan, events, tasks, conflicts, reminders] = await Promise.all([
    requestJson<DayPlan | null>(`/api/day-plans/${planDate}`, {}, accessToken),
    requestJson<CalendarEventsResponse>(todayEventsPath, {}, accessToken),
    requestJson<TaskListResponse>("/api/tasks", {}, accessToken),
    requestJson<ConflictListResponse>("/api/conflicts?status=open", {}, accessToken),
    requestJson<ReminderListResponse>("/api/reminders?status=pending", {}, accessToken),
  ]);

  return {
    plan,
    events: events.items,
    tasks: tasks.items,
    conflicts: conflicts.items,
    reminders: reminders.items,
  };
}

export async function loadCalendarEvents(accessToken: string): Promise<CalendarEventsResponse> {
  return requestJson<CalendarEventsResponse>("/api/calendar-events", {}, accessToken);
}

export async function createTask(
  accessToken: string,
  payload: TaskCreatePayload,
): Promise<TaskItem> {
  return requestJson<TaskItem>(
    "/api/tasks",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function loadDayPlan(accessToken: string, planDate: string): Promise<DayPlan | null> {
  return requestJson<DayPlan | null>(`/api/day-plans/${planDate}`, {}, accessToken);
}

export async function createCalendarEvent(
  accessToken: string,
  payload: CalendarEventUpsertPayload,
): Promise<CalendarEventItem> {
  return requestJson<CalendarEventItem>(
    "/api/calendar-events",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function updateCalendarEvent(
  accessToken: string,
  eventId: string,
  payload: CalendarEventUpsertPayload,
): Promise<CalendarEventItem> {
  return requestJson<CalendarEventItem>(
    `/api/calendar-events/${eventId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function deleteCalendarEvent(accessToken: string, eventId: string): Promise<{ id: string }> {
  return requestJson<{ id: string }>(
    `/api/calendar-events/${eventId}`,
    {
      method: "DELETE",
    },
    accessToken,
  );
}

export async function generateDayPlan(accessToken: string, planDate: string): Promise<DayPlan> {
  return requestJson<DayPlan>(
    `/api/day-plans/${planDate}/generate`,
    {
      method: "POST",
      body: JSON.stringify({
        include_pending_tasks: true,
        auto_detect_conflicts: true,
      }),
    },
    accessToken,
  );
}

export async function confirmDayPlan(
  accessToken: string,
  planId: string,
): Promise<{ id: string; plan_date: string; status: string }> {
  return requestJson<{ id: string; plan_date: string; status: string }>(
    `/api/day-plans/${planId}/confirm`,
    {
      method: "POST",
    },
    accessToken,
  );
}

export async function createPlanItem(
  accessToken: string,
  payload: PlanItemUpsertPayload,
): Promise<DayPlanItem> {
  return requestJson<DayPlanItem>(
    "/api/plan-items",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function updatePlanItem(
  accessToken: string,
  planItemId: string,
  payload: PlanItemUpsertPayload,
): Promise<DayPlanItem> {
  return requestJson<DayPlanItem>(
    `/api/plan-items/${planItemId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function completePlanItem(accessToken: string, planItemId: string): Promise<DayPlanItem> {
  return requestJson<DayPlanItem>(
    `/api/plan-items/${planItemId}/complete`,
    {
      method: "PATCH",
    },
    accessToken,
  );
}

export async function deletePlanItem(accessToken: string, planItemId: string): Promise<DayPlanItem> {
  return requestJson<DayPlanItem>(
    `/api/plan-items/${planItemId}`,
    {
      method: "DELETE",
    },
    accessToken,
  );
}

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

export type DashboardSummary = {
  eventsCount: number;
  tasksCount: number;
  conflictsCount: number;
  remindersCount: number;
};

function getDateParts(value: string | Date, timeZone?: string) {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = formatter.formatToParts(new Date(value));
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
  };
}

export function getDateKey(value: string | Date, timeZone?: string) {
  const parts = getDateParts(value, timeZone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function getTodayDateKey(timeZone?: string) {
  return getDateKey(new Date(), timeZone);
}

export function buildDashboardSummary(data: TodayDashboardData): DashboardSummary {
  return {
    eventsCount: data.events.length,
    tasksCount: data.tasks.filter((item) => item.status !== "completed").length,
    conflictsCount: data.conflicts.length,
    remindersCount: data.reminders.length,
  };
}

export function formatClock(value: string, timeZone?: string) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

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

export function formatRange(start: string, end?: string | null, timeZone?: string) {
  if (!end) {
    return formatClock(start, timeZone);
  }
  return `${formatClock(start, timeZone)} - ${formatClock(end, timeZone)}`;
}
