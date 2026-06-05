import { requestJson } from "@/lib/api";

export type DayPlanItem = {
  id: string;
  title: string;
  item_type: string;
  start_time: string;
  end_time: string;
  status: string;
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

export type TaskItem = {
  id: string;
  title: string;
  description?: string | null;
  estimated_minutes?: number | null;
  deadline?: string | null;
  priority: string;
  status: string;
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
  const [plan, events, tasks, conflicts, reminders] = await Promise.all([
    requestJson<DayPlan | null>(`/api/day-plans/${planDate}`, {}, accessToken),
    requestJson<CalendarEventsResponse>("/api/calendar-events", {}, accessToken),
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

export type DashboardSummary = {
  eventsCount: number;
  tasksCount: number;
  conflictsCount: number;
  remindersCount: number;
};

export function buildDashboardSummary(data: TodayDashboardData): DashboardSummary {
  return {
    eventsCount: data.events.length,
    tasksCount: data.tasks.filter((item) => item.status !== "completed").length,
    conflictsCount: data.conflicts.length,
    remindersCount: data.reminders.length,
  };
}

export function formatClock(value: string) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDateTime(value: string) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatRange(start: string, end?: string | null) {
  if (!end) {
    return formatClock(start);
  }
  return `${formatClock(start)} - ${formatClock(end)}`;
}
