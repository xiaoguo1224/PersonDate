"use client";

import {
  CalendarOutlined,
  ExpandOutlined,
  PlusOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  DatePicker,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Segmented,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import dayjs, { type Dayjs } from "dayjs";
import "dayjs/locale/zh-cn";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import GanttChart from "@/components/gantt-chart";
import { requestJson } from "@/lib/api";
import {
  confirmDayDrafts,
  createScheduledItem,
  deleteScheduledItem,
  formatRange,
  formatClock,
  generateDayDrafts,
  getDateKey,
  getTodayDateKey,
  loadScheduledItems,
  updateScheduledItem,
  type ScheduledItem,
} from "@/lib/dashboard";

dayjs.locale("zh-cn");

const { Title, Paragraph, Text } = Typography;
const DEFAULT_TIMEZONE = "Asia/Shanghai";

type CalendarViewMode = "month" | "week" | "day";

type ScheduledItemFormValues = {
  title: string;
  description?: string | null;
  start_time: Dayjs;
  end_time?: Dayjs | null;
  timezone: string;
  location?: string | null;
  remind_before_minutes?: number | null;
};

type WeekTimelineEventSegment = {
  event: ScheduledItem;
  top: number;
  height: number;
  laneIndex: number;
  laneCount: number;
  startLabel: string;
  endLabel: string;
};

type WeekTimelineDay = {
  day: Dayjs;
  dayKey: string;
  segments: WeekTimelineEventSegment[];
};

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];
const WEEK_TIMELINE_HOUR_HEIGHT = 64;
const WEEK_TIMELINE_MIN_EVENT_HEIGHT = 40;
const WEEK_TIMELINE_GUTTER_WIDTH = 76;
const WEEK_TIMELINE_BODY_HEIGHT = WEEK_TIMELINE_HOUR_HEIGHT * 24;
const WEEK_TIMELINE_MIN_COLUMN_WIDTH = 152;

function toDateKey(value: Dayjs) {
  return value.format("YYYY-MM-DD");
}

function buildDemoCalendarEvents(focusDate: Dayjs): ScheduledItem[] {
  const base = focusDate.startOf("day");
  const at = (hour: number, minute: number) => base.hour(hour).minute(minute).second(0).millisecond(0).toISOString();
  return [
    {
      id: "demo-cal-1",
      title: "团队站会",
      description: "每日同步进展",
      start_time: at(9, 0),
      end_time: at(9, 30),
      timezone: "Asia/Shanghai",
      location: "会议室 A",
      source: "manual",
      source_task_id: null,
      status: "active",
      sort_order: 1,
      remind_before_minutes: 10,
    },
    {
      id: "demo-cal-2",
      title: "需求评审会",
      description: "评审 Q3 需求方案",
      start_time: at(10, 0),
      end_time: at(11, 30),
      timezone: "Asia/Shanghai",
      location: "会议室 B",
      source: "manual",
      source_task_id: null,
      status: "active",
      sort_order: 2,
      remind_before_minutes: 15,
    },
    {
      id: "demo-cal-3",
      title: "午餐",
      description: "休息",
      start_time: at(12, 0),
      end_time: at(13, 0),
      timezone: "Asia/Shanghai",
      location: "",
      source: "manual",
      source_task_id: null,
      status: "active",
      sort_order: 3,
      remind_before_minutes: 0,
    },
    {
      id: "demo-cal-4",
      title: "代码审查",
      description: "审查 PR #128",
      start_time: at(14, 0),
      end_time: at(15, 0),
      timezone: "Asia/Shanghai",
      location: "工位",
      source: "manual",
      source_task_id: null,
      status: "active",
      sort_order: 4,
      remind_before_minutes: 5,
    },
    {
      id: "demo-cal-5",
      title: "写周报",
      description: "总结本周工作",
      start_time: at(16, 0),
      end_time: at(17, 0),
      timezone: "Asia/Shanghai",
      location: "",
      source: "manual",
      source_task_id: null,
      status: "active",
      sort_order: 5,
      remind_before_minutes: 10,
    },
  ];
}

function toDisplayDate(value: Dayjs) {
  return value.format("YYYY年M月D日");
}

function getMinutesOfDay(value: string, timeZone: string) {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = formatter.formatToParts(new Date(value));
  const hour = Number(parts.find((part) => part.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((part) => part.type === "minute")?.value ?? "0");
  return hour * 60 + minute;
}

function startOfWeek(value: Dayjs) {
  const weekday = value.day();
  const diff = weekday === 0 ? -6 : 1 - weekday;
  return value.add(diff, "day").startOf("day");
}

function endOfWeek(value: Dayjs) {
  return startOfWeek(value).add(6, "day").endOf("day");
}

function startOfMonthGrid(value: Dayjs) {
  const firstDayOfMonth = value.startOf("month");
  const weekday = firstDayOfMonth.day();
  const diff = weekday === 0 ? -6 : 1 - weekday;
  return firstDayOfMonth.add(diff, "day").startOf("day");
}

function buildMonthGridDays(value: Dayjs) {
  const gridStart = startOfMonthGrid(value);
  return Array.from({ length: 42 }, (_, index) => gridStart.add(index, "day"));
}

function getViewRange(viewMode: CalendarViewMode, focusDate: Dayjs) {
  if (viewMode === "month") {
    return {
      start: focusDate.startOf("month").startOf("day"),
      end: focusDate.endOf("month").endOf("day"),
    };
  }
  if (viewMode === "week") {
    return {
      start: startOfWeek(focusDate),
      end: endOfWeek(focusDate),
    };
  }
  return {
    start: focusDate.startOf("day"),
    end: focusDate.endOf("day"),
  };
}

function isEventInRange(event: ScheduledItem, start: Dayjs, end: Dayjs, timeZone: string) {
  const eventStartKey = getDateKey(event.start_time, timeZone);
  const eventEndKey = getDateKey(event.end_time ?? event.start_time, timeZone);
  const startKey = start.format("YYYY-MM-DD");
  const endKey = end.format("YYYY-MM-DD");
  return eventStartKey <= endKey && eventEndKey >= startKey;
}

type SortableTimelineItem = {
  start_time: string;
  title: string;
};

function sortEvents<T extends SortableTimelineItem>(items: T[]) {
  return [...items].sort((left, right) => {
    const startDiff = dayjs(left.start_time).valueOf() - dayjs(right.start_time).valueOf();
    if (startDiff !== 0) {
      return startDiff;
    }
    return left.title.localeCompare(right.title, "zh-CN");
  });
}

function isPastTime(value: string, referenceTime = Date.now()) {
  return new Date(value).getTime() < referenceTime;
}

function getTimelineStatusLabel(
  entry: { status?: string; start_time: string; end_time?: string | null },
  referenceTime = Date.now(),
) {
  if (entry.status === "completed" || entry.status === "cancelled" || entry.status === "skipped") {
    return entry.status === "completed" ? "已完成" : entry.status === "cancelled" ? "已取消" : "已跳过";
  }
  if (isPastTime(entry.end_time ?? entry.start_time, referenceTime)) {
    return "已结束";
  }
  if (!isPastTime(entry.start_time, referenceTime)) {
    return "待开始";
  }
  return "进行中";
}

function getEventDotColor(status: string) {
  if (status === "completed") {
    return "#34d399";
  }
  if (status === "deleted") {
    return "#94a3b8";
  }
  return "#7dd3fc";
}

function getWeekEventTheme(status: string) {
  if (status === "completed") {
    return {
      accent: "#34d399",
      background: "linear-gradient(180deg, rgba(220, 252, 231, 0.96), rgba(255, 255, 255, 0.98))",
    };
  }
  if (status === "deleted") {
    return {
      accent: "#94a3b8",
      background: "linear-gradient(180deg, rgba(241, 245, 249, 0.96), rgba(255, 255, 255, 0.98))",
    };
  }
  return {
    accent: "#7dd3fc",
    background: "linear-gradient(180deg, rgba(219, 234, 254, 0.96), rgba(255, 255, 255, 0.98))",
  };
}

function WeekEventCard({
  segment,
  day,
  theme,
  openEditModal,
  setFocusDate,
}: {
  segment: WeekTimelineEventSegment;
  day: Dayjs;
  theme: ReturnType<typeof getWeekEventTheme>;
  openEditModal: (event: ScheduledItem) => void;
  setFocusDate: (d: Dayjs) => void;
}) {
  const cardRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  useGSAP(() => {
    if (!cardRef.current) return;
    if (isHovered) {
      gsap.to(cardRef.current, {
        scale: 1.08,
        y: -4,
        zIndex: 100,
        boxShadow: "0 20px 48px rgba(0,0,0,0.35)",
        duration: 0.25,
        ease: "power2.out",
        overwrite: "auto",
      });
      if (contentRef.current) {
        gsap.to(contentRef.current, {
          maxHeight: 200,
          opacity: 1,
          duration: 0.2,
          ease: "power1.out",
        });
      }
    } else {
      gsap.to(cardRef.current, {
        scale: 1,
        y: 0,
        zIndex: 1,
        boxShadow: "0 10px 26px rgba(0,0,0,0.2)",
        duration: 0.3,
        ease: "power2.out",
        overwrite: "auto",
      });
      if (contentRef.current) {
        gsap.to(contentRef.current, {
          maxHeight: segment.height < 60 ? 0 : 20,
          opacity: segment.height < 60 ? 0 : 1,
          duration: 0.2,
          ease: "power1.out",
        });
      }
    }
  }, { dependencies: [isHovered], scope: cardRef });

  const clickHandler = useCallback((eventClick: React.MouseEvent) => {
    eventClick.stopPropagation();
    setFocusDate(day);
    openEditModal(segment.event);
  }, [day, openEditModal, segment.event, setFocusDate]);

  return (
    <button
      ref={cardRef}
      type="button"
      className="calendar-week-event"
      onClick={clickHandler}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        top: segment.top,
        height: Math.max(segment.height, isHovered ? segment.height + 24 : segment.height),
        left: `${4 + segment.laneIndex * 10}px`,
        width: `calc(100% - ${8 + segment.laneIndex * 10}px)`,
        borderColor: theme.accent,
        background: theme.background,
        zIndex: isHovered ? 100 : 1,
      }}
    >
      <span
        className="calendar-week-event__accent"
        style={{ background: theme.accent }}
      />
      <Space direction="vertical" size={2} style={{ width: "100%", overflow: "hidden" }}>
        <Text strong ellipsis={!isHovered} className="calendar-week-event__title">
          {segment.event.title}
        </Text>
        <Text className="calendar-week-event__time">
          {segment.startLabel} - {segment.endLabel}
        </Text>
        <div ref={contentRef} style={{ maxHeight: segment.height < 60 ? 0 : 20, overflow: "hidden", opacity: segment.height < 60 ? 0 : 1 }}>
          {segment.event.location ? (
            <Text className="calendar-week-event__location" ellipsis={!isHovered}>
              {segment.event.location}
            </Text>
          ) : null}
          {segment.event.description ? (
            <Text className="calendar-week-event__location" ellipsis={!isHovered}>
              {segment.event.description}
            </Text>
          ) : null}
        </div>
      </Space>
      {segment.laneCount > 1 && segment.laneIndex === segment.laneCount - 1 && (
        <span
          className="calendar-week-event__stack"
          style={{ background: theme.accent }}
        />
      )}
    </button>
  );
}

function buildWeekTimelineDays(weekDays: Dayjs[], events: ScheduledItem[], timeZone: string): WeekTimelineDay[] {
  return weekDays.map((day) => {
    const dayKey = day.format("YYYY-MM-DD");
    const segments: WeekTimelineEventSegment[] = [];

    events
      .filter((event) => event.status !== "deleted")
      .filter((event) => isEventInRange(event, day.startOf("day"), day.endOf("day"), timeZone))
      .forEach((event) => {
        const eventStartKey = getDateKey(event.start_time, timeZone);
        const eventEndKey = getDateKey(event.end_time ?? event.start_time, timeZone);
        const eventStartMinutes = getMinutesOfDay(event.start_time, timeZone);
        const eventEndMinutes = getMinutesOfDay(event.end_time ?? event.start_time, timeZone);
        const segmentStartMinutes = eventStartKey < dayKey ? 0 : eventStartMinutes;
        const segmentEndMinutes = eventEndKey > dayKey ? 24 * 60 : Math.max(eventEndMinutes, segmentStartMinutes + 30);
        const topMinutes = segmentStartMinutes;
        const durationMinutes = Math.max(1, segmentEndMinutes - segmentStartMinutes);
        segments.push({
          event,
          top: (topMinutes / 60) * WEEK_TIMELINE_HOUR_HEIGHT,
          height: Math.max(
            (durationMinutes / 60) * WEEK_TIMELINE_HOUR_HEIGHT,
            WEEK_TIMELINE_MIN_EVENT_HEIGHT,
          ),
          laneIndex: 0,
          laneCount: 1,
          startLabel: formatClock(event.start_time, timeZone),
          endLabel: formatClock(event.end_time ?? event.start_time, timeZone),
        });
      });

    segments.sort((left, right) => {
      const topDiff = left.top - right.top;
      if (topDiff !== 0) {
        return topDiff;
      }
      const heightDiff = right.height - left.height;
      if (heightDiff !== 0) {
        return heightDiff;
      }
      return left.event.title.localeCompare(right.event.title, "zh-CN");
    });

    // Poker card style: group overlapping events, assign offset index
    const overlapGroups: number[] = [];
    segments.forEach((segment) => {
      let overlapIndex = 0;
      while (overlapIndex < overlapGroups.length && overlapGroups[overlapIndex] <= segment.top) {
        overlapIndex++;
      }
      if (overlapIndex >= overlapGroups.length) {
        overlapGroups.push(segment.top + segment.height);
      } else {
        overlapGroups[overlapIndex] = segment.top + segment.height;
      }
      segment.laneIndex = overlapIndex;
    });

    const laneCount = Math.max(1, overlapGroups.length);
    segments.forEach((segment) => {
      segment.laneCount = laneCount;
    });

    return {
      day,
      dayKey,
      segments,
    };
  });
}

function CalendarLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" tip="正在加载日历数据..." />
    </div>
  );
}

function CalendarError({ message }: Readonly<{ message: string }>) {
  return <Alert type="error" showIcon message="加载日历失败" description={message} />;
}

function EmptyPanel({ title }: Readonly<{ title: string }>) {
  return (
    <div className="dashboard-empty">
      <Empty description={title} />
    </div>
  );
}

export default function CalendarPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone, loading: timezoneLoading } = useDashboardTimezone();
  const [form] = Form.useForm<ScheduledItemFormValues>();
  const [messageApi, contextHolder] = message.useMessage();
  const detailAnchorRef = useRef<HTMLDivElement | null>(null);

  const [viewMode, setViewMode] = useState<CalendarViewMode>("month");
  const [dayViewMode, setDayViewMode] = useState<"timeline" | "gantt">("timeline");
  const [focusDate, setFocusDate] = useState(() => dayjs(getTodayDateKey()));
  const demoEvents = useMemo(() => buildDemoCalendarEvents(focusDate), [focusDate]);
  const [events, setEvents] = useState<ScheduledItem[]>([]);
  const [dayConflicts, setDayConflicts] = useState<ScheduledItem[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<ScheduledItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [planSubmitting, setPlanSubmitting] = useState(false);

  useEffect(() => {
    setFocusDate(dayjs(getTodayDateKey(timezone)));
  }, [timezone]);

  const fetchEvents = useCallback(async () => {
    if (!accessToken) {
      setEvents(sortEvents(demoEvents));
      setEventsLoading(false);
      return;
    }
    setEventsLoading(true);
    setEventsError(null);
    try {
      const range = getViewRange(viewMode, focusDate);
      const result = await loadScheduledItems({
        start_time: range.start.toISOString(),
        end_time: range.end.toISOString(),
      }, accessToken);
      setEvents(sortEvents(result));
    } catch (caughtError: unknown) {
      setEventsError(caughtError instanceof Error ? caughtError.message : "未知错误");
    } finally {
      setEventsLoading(false);
    }
  }, [accessToken, viewMode, focusDate]);

  useEffect(() => {
    if (!accessToken) {
      setEvents(sortEvents(demoEvents));
      setEventsLoading(false);
      return;
    }
    if (timezoneLoading) {
      return;
    }
    void fetchEvents();
  }, [accessToken, fetchEvents, timezoneLoading]);

  const fetchDayConflicts = useCallback(() => {
    if (!accessToken) return;
    requestJson<{ data?: { items?: { related_item_ids?: Record<string, string> }[] }; items?: { related_item_ids?: Record<string, string> }[] }>(
      "/api/conflicts?status=open",
      {},
      accessToken,
    ).then((result) => {
      const conflictItems = result.data?.items || result.items || [];
      const conflictItemIds = new Set<string>();
      for (const c of conflictItems) {
        const ids = c.related_item_ids;
        if (ids) {
          Object.values(ids).forEach((id) => conflictItemIds.add(id as string));
        }
      }
      const dayConflictItems = events.filter((e) => conflictItemIds.has(e.id));
      setDayConflicts(dayConflictItems);
    }).catch(() => setDayConflicts([]));
  }, [accessToken, events]);

  useEffect(() => {
    if (!accessToken || timezoneLoading) return;
    fetchDayConflicts();
  }, [accessToken, timezoneLoading, fetchDayConflicts]);

  const viewRange = useMemo(() => getViewRange(viewMode, focusDate), [focusDate, viewMode]);
  const visibleEvents = useMemo(
    () => sortEvents(events.filter((event) => isEventInRange(event, viewRange.start, viewRange.end, timezone))),
    [events, timezone, viewRange.end, viewRange.start],
  );
  const selectedDayEvents = useMemo(
    () =>
      sortEvents(
        events.filter((event) =>
          isEventInRange(event, focusDate.startOf("day"), focusDate.endOf("day"), timezone),
        ),
      ),
    [events, focusDate, timezone],
  );
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, index) => startOfWeek(focusDate).add(index, "day")),
    [focusDate],
  );
  const weekTimelineDays = useMemo(
    () => buildWeekTimelineDays(weekDays, events, timezone),
    [events, timezone, weekDays],
  );
  const monthGridDays = useMemo(() => buildMonthGridDays(focusDate), [focusDate]);
  const selectedDayTimelineEntries = useMemo(() => {
    const entries = [...selectedDayEvents];
    return sortEvents(entries);
  }, [selectedDayEvents]);
  const monthEventsByDate = useMemo(() => {
    const map = new Map<string, ScheduledItem[]>();
    events
      .filter((event) => event.status !== "deleted")
      .forEach((event) => {
        const key = getDateKey(event.start_time, timezone);
        const next = map.get(key) ?? [];
        next.push(event);
        map.set(key, next);
      });
    return map;
  }, [events, timezone]);
  const selectedDateKey = focusDate.format("YYYY-MM-DD");
  const todayKey = getTodayDateKey(timezone);

  const summary = useMemo(() => {
    const activeEvents = events.filter((event) => event.status !== "deleted");
    return {
      totalEvents: activeEvents.length,
      visibleEvents: visibleEvents.length,
      selectedEvents: selectedDayEvents.length,
    };
  }, [events, selectedDayEvents.length, visibleEvents.length]);

  const openCreateModal = useCallback(
    (initialDate?: Dayjs) => {
      const baseDate = (initialDate ?? focusDate).hour(9).minute(0).second(0).millisecond(0);
      form.setFieldsValue({
        title: "",
        description: "",
        start_time: baseDate,
        end_time: baseDate.add(1, "hour"),
        timezone,
        location: "",
        remind_before_minutes: 10,
      });
      setEditingEvent(null);
      setModalOpen(true);
    },
    [focusDate, form, timezone],
  );

  const openEditModal = useCallback(
    (event: ScheduledItem) => {
      setEditingEvent(event);
      form.setFieldsValue({
        title: event.title,
        description: event.description ?? "",
        start_time: dayjs(event.start_time),
        end_time: event.end_time ? dayjs(event.end_time) : null,
        timezone: event.timezone || timezone,
        location: event.location ?? "",
        remind_before_minutes: event.remind_before_minutes ?? 0,
      });
      setModalOpen(true);
    },
    [form, timezone],
  );

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setEditingEvent(null);
    form.resetFields();
  }, [form]);

  const refreshData = useCallback(async () => {
    await fetchEvents();
  }, [fetchEvents]);

  const handleSubmit = useCallback(
    async (values: ScheduledItemFormValues) => {
      if (!accessToken) {
        return;
      }
      if (values.end_time && values.end_time.isBefore(values.start_time)) {
        messageApi.error("结束时间不能早于开始时间");
        return;
      }
      const endTime = values.end_time ? values.end_time.toISOString() : values.start_time.add(1, "hour").toISOString();
      setSubmitting(true);
      try {
        if (editingEvent) {
          await updateScheduledItem(editingEvent.id, {
            title: values.title.trim(),
            description: values.description?.trim() || null,
            end_time: endTime,
            start_time: values.start_time.toISOString(),
            timezone: values.timezone || timezone || DEFAULT_TIMEZONE,
            location: values.location?.trim() || null,
            remind_before_minutes: values.remind_before_minutes ?? 0,
          }, accessToken);
          messageApi.success("安排已更新");
        } else {
          await createScheduledItem({
            title: values.title.trim(),
            description: values.description?.trim() || null,
            start_time: values.start_time.toISOString(),
            end_time: endTime,
            timezone: values.timezone || timezone || DEFAULT_TIMEZONE,
            location: values.location?.trim() || null,
            remind_before_minutes: values.remind_before_minutes ?? 0,
          }, accessToken);
          messageApi.success("安排已创建");
        }
        closeModal();
        await refreshData();
      } catch (caughtError: unknown) {
        messageApi.error(caughtError instanceof Error ? caughtError.message : "保存失败");
      } finally {
        setSubmitting(false);
      }
    },
    [accessToken, closeModal, editingEvent, messageApi, refreshData, timezone],
  );

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleDelete = useCallback(
    (event: ScheduledItem) => {
      if (!accessToken) {
        return;
      }
      Modal.confirm({
        title: "删除安排",
        content: `确认删除「${event.title}」吗？`,
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        centered: true,
        onOk: async () => {
          await deleteScheduledItem(event.id, accessToken);
          messageApi.success("安排已删除");
          await refreshData();
        },
      });
    },
    [accessToken, messageApi, refreshData],
  );

  const handleGeneratePlan = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setPlanSubmitting(true);
    try {
      await generateDayDrafts(toDateKey(focusDate), accessToken);
      await fetchEvents();
      messageApi.success("安排草案已生成");
    } catch (caughtError: unknown) {
      messageApi.error(caughtError instanceof Error ? caughtError.message : "生成失败");
    } finally {
      setPlanSubmitting(false);
    }
  }, [accessToken, fetchEvents, focusDate, messageApi]);

  const handleConfirmPlan = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setPlanSubmitting(true);
    try {
      await confirmDayDrafts(toDateKey(focusDate), accessToken);
      await fetchEvents();
      messageApi.success("安排已确认");
    } catch (caughtError: unknown) {
      messageApi.error(caughtError instanceof Error ? caughtError.message : "确认失败");
    } finally {
      setPlanSubmitting(false);
    }
  }, [accessToken, fetchEvents, focusDate, messageApi]);

  const heroTags = [
    { color: "cyan", label: `${summary.totalEvents} 条安排` },
    { color: "orange", label: `${summary.visibleEvents} 条当前视图` },
    { color: "gold", label: `${summary.totalEvents} 条安排` },
    { color: "green", label: "已加载" },
  ];

  return (
    <ConfigProvider locale={zhCN}>
      {contextHolder}
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <Card className="section-card dashboard-hero" bordered={false}>
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <span className="hero-kicker">
              <CalendarOutlined />
              日历视图
            </span>
            <Title style={{ color: "var(--text-primary)", margin: 0 }}>安排总览</Title>
            <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
              这里已经接入后端的 `calendar_events` 列表，并补齐了月/周/日视图、创建、编辑、删除，以及当日安排草案和确认入口。
            </Paragraph>
            <Space wrap>
              {heroTags.map((item) => (
                <Tag key={item.label} color={item.color}>
                  {item.label}
                </Tag>
              ))}
            </Space>
          </Space>
        </Card>

        {eventsError ? <CalendarError message={eventsError} /> : null}

        <Card className="section-card" bordered={false}>
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} lg={10}>
              <Space wrap>
                <Segmented
                  value={viewMode}
                  options={[
                    { label: "月视图", value: "month" },
                    { label: "周视图", value: "week" },
                    { label: "日视图", value: "day" },
                  ]}
                  onChange={(value) => setViewMode(value as CalendarViewMode)}
                />
                <DatePicker
                  value={focusDate}
                  onChange={(value) => {
                    if (value) {
                      setFocusDate(value);
                    }
                  }}
                  allowClear={false}
                />
              </Space>
            </Col>
            <Col xs={24} lg={14}>
              <Space wrap style={{ width: "100%", justifyContent: "flex-end" }}>
                <Button icon={<ReloadOutlined />} onClick={() => void refreshData()}>
                  刷新
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreateModal()}>
                  新增安排
                </Button>
              </Space>
            </Col>
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Card className="section-card" bordered={false}>
              <Text className="muted-text">当前视图范围</Text>
              <Title level={4} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                {viewMode === "month"
                  ? focusDate.format("YYYY年M月")
                  : viewMode === "week"
                    ? `${toDisplayDate(viewRange.start)} - ${toDisplayDate(viewRange.end)}`
                    : toDisplayDate(focusDate)}
              </Title>
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card className="section-card" bordered={false}>
              <Text className="muted-text">选中日期</Text>
              <Title level={4} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                {toDisplayDate(focusDate)}
              </Title>
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card className="section-card" bordered={false}>
              <Text className="muted-text">当日事件</Text>
              <Title level={4} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                {summary.selectedEvents} 条
              </Title>
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card className="section-card" bordered={false}>
              <Text className="muted-text">当前安排</Text>
              <Title level={4} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                {summary.totalEvents} 条
              </Title>
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={16}>
            <Card
              className="section-card"
              bordered={false}
              title={viewMode === "month" ? "月历总览" : viewMode === "week" ? "周视图" : "日视图"}
            >
              {eventsLoading ? (
                <CalendarLoading />
              ) : viewMode === "month" ? (
                <div className="calendar-month-shell">
                  <div className="calendar-month-shell__meta">
                    <div>
                      <Text className="muted-text">月视图</Text>
                      <Title level={4} style={{ color: "var(--text-primary)", margin: "6px 0 0" }}>
                        {focusDate.format("YYYY年M月")}
                      </Title>
                    </div>
                    <Space wrap>
                      <Tag color="cyan">{visibleEvents.length} 条当前月安排</Tag>
                      <Tag color="gold">{selectedDayEvents.length} 条选中安排</Tag>
                      <Tag color="default">{toDisplayDate(focusDate)}</Tag>
                    </Space>
                  </div>

                  <div className="calendar-month-shell__weekdays">
                    {WEEKDAY_LABELS.map((label) => (
                      <span key={label} className="calendar-month-weekday">
                        {label}
                      </span>
                    ))}
                  </div>

                  <div className="calendar-month-grid">
                    {monthGridDays.map((current) => {
                      const key = current.format("YYYY-MM-DD");
                      const items = monthEventsByDate.get(key) ?? [];
                      const isSelected = key === selectedDateKey;
                      const isToday = key === todayKey;
                      const isOutsideMonth = !current.isSame(focusDate, "month");
                      return (
                        <div
                          key={key}
                          role="button"
                          tabIndex={0}
                          className={[
                            "calendar-month-cell",
                            isSelected ? "calendar-month-cell--selected" : "",
                            isToday ? "calendar-month-cell--today" : "",
                            isOutsideMonth ? "calendar-month-cell--outside" : "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                          onClick={() => {
                            setFocusDate(current);
                            detailAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setFocusDate(current);
                              detailAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                            }
                          }}
                        >
                          <div className="calendar-month-cell__header">
                            <span
                              className="calendar-month-cell__date"
                              style={{
                                background: isSelected
                                  ? "linear-gradient(135deg, rgba(191, 219, 254, 0.96), rgba(59, 130, 246, 0.85))"
                                  : isToday
                                    ? "rgba(254, 243, 199, 0.9)"
                                    : "rgba(255, 255, 255, 0.92)",
                                color: isSelected ? "#06111f" : "var(--text-primary)",
                              }}
                            >
                              {current.date()}
                            </span>
                            <Space wrap size={6}>
                              {isToday ? <Tag color="gold">今天</Tag> : null}
                              {items.length ? <span className="calendar-month-cell__count">{items.length}</span> : null}
                            </Space>
                          </div>

                          <div className="calendar-month-cell__events">
                            {items.slice(0, 2).map((event) => (
                              <button
                                key={event.id}
                                type="button"
                                className="calendar-month-cell__event"
                                onClick={(eventClick) => {
                                  eventClick.stopPropagation();
                                  openEditModal(event);
                                }}
                              >
                                <span
                                  className="calendar-month-cell__event-dot"
                                  style={{ background: getEventDotColor(event.status) }}
                                />
                                <Text strong ellipsis className="calendar-month-cell__event-title">
                                  {event.title}
                                </Text>
                              </button>
                            ))}
                            {items.length > 2 ? (
                              <span className="calendar-month-cell__more">+{items.length - 2}</span>
                            ) : null}
                            {!items.length ? <span className="calendar-month-cell__empty">暂无安排</span> : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : viewMode === "week" ? (
                <Space direction="vertical" size={16} style={{ width: "100%" }} className="calendar-week-shell">
                  <div className="calendar-week-scroll">
                    <div
                      className="calendar-week-scroll__inner"
                      style={{ minWidth: WEEK_TIMELINE_GUTTER_WIDTH + weekDays.length * WEEK_TIMELINE_MIN_COLUMN_WIDTH }}
                    >
                      <div className="calendar-week-header-grid">
                        <div className="calendar-week-gutter calendar-week-gutter--header">
                          <Text className="muted-text">时间</Text>
                        </div>
                        {weekTimelineDays.map(({ day, dayKey, segments }) => {
                          const isSelected = day.isSame(focusDate, "day");
                          const isToday = day.format("YYYY-MM-DD") === todayKey;
                          return (
                            <button
                              key={dayKey}
                              type="button"
                              className={[
                                "calendar-week-day-header",
                                isSelected ? "calendar-week-day-header--selected" : "",
                                isToday ? "calendar-week-day-header--today" : "",
                              ]
                                .filter(Boolean)
                                .join(" ")}
                              onClick={() => {
                                setFocusDate(day);
                                detailAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                              }}
                            >
                              <span className="calendar-week-day-header__label">{day.format("ddd")}</span>
                              <span className="calendar-week-day-header__date">{day.format("MM/DD")}</span>
                              <Tag color={isSelected ? "cyan" : "default"} style={{ marginInlineEnd: 0 }}>
                                {segments.length} 条
                              </Tag>
                            </button>
                          );
                        })}
                      </div>

                      <div className="calendar-week-body-grid" style={{ height: WEEK_TIMELINE_BODY_HEIGHT }}>
                        <div className="calendar-week-gutter calendar-week-gutter--body">
                          {Array.from({ length: 24 }, (_, hour) => (
                            <div
                              key={hour}
                              className="calendar-week-hour"
                              style={{ height: WEEK_TIMELINE_HOUR_HEIGHT }}
                            >
                              <span>{`${String(hour).padStart(2, "0")}:00`}</span>
                            </div>
                          ))}
                        </div>

                        {weekTimelineDays.map(({ day, dayKey, segments }) => {
                          const isSelected = day.isSame(focusDate, "day");
                          const isToday = day.format("YYYY-MM-DD") === todayKey;
                          return (
                            <div
                              key={dayKey}
                              className={[
                                "calendar-week-column",
                                isSelected ? "calendar-week-column--selected" : "",
                                isToday ? "calendar-week-column--today" : "",
                              ]
                                .filter(Boolean)
                                .join(" ")}
                              role="button"
                              tabIndex={0}
                              onClick={() => {
                                setFocusDate(day);
                              }}
                              onKeyDown={(event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  setFocusDate(day);
                                }
                              }}
                            >
                              <div className="calendar-week-column__grid" />
                              <div className="calendar-week-column__events">
                                {segments.map((segment) => (
                                  <WeekEventCard
                                    key={`${segment.event.id}-${dayKey}-${segment.startLabel}`}
                                    segment={segment}
                                    day={day}
                                    theme={getWeekEventTheme(segment.event.status)}
                                    openEditModal={openEditModal}
                                    setFocusDate={setFocusDate}
                                  />
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                  <Text className="muted-text">
                    点击某个日期标题可切换右侧详情，点击安排块可直接编辑。
                  </Text>
                </Space>
              ) : selectedDayTimelineEntries.length ? (
                <div>
                  <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
                    <Segmented
                      size="small"
                      value={dayViewMode}
                      onChange={(val) => setDayViewMode(val as "timeline" | "gantt")}
                      options={[
                        { label: "时间轴", value: "timeline" },
                        { label: "甘特图", value: "gantt" },
                      ]}
                    />
                  </div>
                  {dayViewMode === "timeline" ? (
                    <div className="today-timeline-scroll">
                      <div className="today-timeline">
                        {selectedDayTimelineEntries.map((entry) => (
                          <div key={entry.id} className="today-timeline__item">
                            <div className="today-timeline__time">{formatClock(entry.start_time, timezone)}</div>
                            <div className="today-timeline__dot" />
                            <Card
                              className="today-timeline__card"
                              bordered={false}
                              hoverable
                              onClick={() => openEditModal(entry)}
                            >
                              <div className="today-timeline__head">
                                <Text strong className="today-timeline__title">
                                  {entry.title}
                                </Text>
                                <Tag color="blue">
                                  安排 · {getTimelineStatusLabel(entry)}
                                </Tag>
                              </div>
                              <Text className="today-timeline__meta">
                                {formatRange(entry.start_time, entry.end_time, timezone)}
                              </Text>
                              {entry.location ? (
                                <Text className="today-timeline__meta">{entry.location}</Text>
                              ) : null}
                            </Card>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <GanttChart
                      items={selectedDayTimelineEntries.map((e) => ({
                        id: e.id,
                        title: e.title,
                        start_time: e.start_time,
                        end_time: e.end_time,
                        type: "event" as const,
                      }))}
                      baseDate={focusDate.format("YYYY-MM-DD")}
                      timezone={timezone}
                      maxHeight={520}
                      onEventClick={(item) => {
                        const event = selectedDayTimelineEntries.find((e) => e.id === item.id);
                        if (event) openEditModal(event);
                      }}
                    />
                  )}
                </div>
              ) : (
                <EmptyPanel title="这一天还没有安排" />
              )}
            </Card>
          </Col>

          <Col xs={24} xl={8}>
            <div ref={detailAnchorRef}>
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card
                  className="section-card"
                  bordered={false}
                  title={`${toDisplayDate(focusDate)} 的安排`}
                  extra={
                    <Space wrap>
                      <Button loading={planSubmitting} onClick={() => void handleGeneratePlan()}>
                        安排任务
                      </Button>
                      <Button type="primary" loading={planSubmitting} onClick={() => void handleConfirmPlan()}>
                        确认安排
                      </Button>
                    </Space>
                  }
                >
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Text className="muted-text">安排任务会将待办填进空时段，确认安排将草稿转为正式。</Text>
                  </Space>
                </Card>

                <Card className="section-card" bordered={false} title={`${toDisplayDate(focusDate)} 安排事项`} style={{ overflow: "hidden" }}>
                  {selectedDayEvents.length ? (
                    <div className="today-timeline-scroll" style={{ maxHeight: 320 }}>
                      <div className="today-timeline">
                        {selectedDayEvents.map((entry) => (
                          <div key={entry.id} className="today-timeline__item">
                            <div className="today-timeline__time">{formatClock(entry.start_time, timezone)}</div>
                            <div className="today-timeline__dot" />
                            <Card
                              className="today-timeline__card"
                              bordered={false}
                              hoverable
                              onClick={() => openEditModal(entry)}
                            >
                              <div className="today-timeline__head">
                                <Text strong className="today-timeline__title">
                                  {entry.title}
                                </Text>
                                <Tag color="blue">
                                  安排 · {getTimelineStatusLabel(entry)}
                                </Tag>
                              </div>
                              <Text className="today-timeline__meta">
                                {formatRange(entry.start_time, entry.end_time, timezone)}
                              </Text>
                            </Card>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <EmptyPanel title="选中日期暂无安排" />
                  )}
                </Card>

                <Card className="section-card" bordered={false} title="冲突项管理">
                  {dayConflicts.length ? (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      {dayConflicts.map((conflict) => (
                        <div key={conflict.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <Text ellipsis style={{ maxWidth: 180 }}>{conflict.title}</Text>
                          <Tag color="red">冲突</Tag>
                        </div>
                      ))}
                    </Space>
                  ) : (
                    <Text className="muted-text">当前选中日期无冲突</Text>
                  )}
                </Card>
              </Space>
            </div>
          </Col>
        </Row>

        <Modal
          title={editingEvent ? "编辑安排" : "新建安排"}
          open={modalOpen}
          onCancel={closeModal}
          destroyOnClose
          okText={editingEvent ? "保存修改" : "创建安排"}
          cancelText="取消"
          confirmLoading={submitting}
          onOk={() => void form.submit()}
        >
          <Form
            form={form}
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => void handleSubmit(values)}
          >
            <Form.Item
              name="title"
              label="标题"
              rules={[{ required: true, message: "请输入安排标题" }]}
            >
              <Input placeholder="例如：项目会议" />
            </Form.Item>
            <Form.Item name="description" label="描述">
              <Input.TextArea rows={3} placeholder="可选描述" />
            </Form.Item>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item
                  name="start_time"
                  label="开始时间"
                  rules={[{ required: true, message: "请选择开始时间" }]}
                >
                  <DatePicker showTime style={{ width: "100%" }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="end_time" label="结束时间">
                  <DatePicker showTime style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="timezone"
              label="时区"
              rules={[{ required: true, message: "请输入时区" }]}
            >
              <Input placeholder="Asia/Shanghai" />
            </Form.Item>
            <Form.Item name="location" label="地点">
              <Input placeholder="可选地点" />
            </Form.Item>
            <Form.Item name="remind_before_minutes" label="提前提醒（分钟）">
              <InputNumber min={0} max={24 * 60} style={{ width: "100%" }} />
            </Form.Item>
          </Form>
        </Modal>

        <Modal
          title={`${focusDate.format("YYYY-MM-DD")} 的冲突项`}
          open={dayConflicts.length > 0}
          onCancel={() => setDayConflicts([])}
          footer={null}
          width={520}
        >
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Text className="muted-text">
              以下安排与当日其他安排存在时间重叠：
            </Text>
            {dayConflicts.map((event) => (
              <Card
                key={event.id}
                size="small"
                bordered={false}
                style={{ background: "rgba(255,255,255,0.04)", cursor: "pointer" }}
                onClick={() => openEditModal(event)}
              >
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Text strong>{event.title}</Text>
                  <Text className="muted-text">
                    {formatRange(event.start_time, event.end_time, timezone)}
                  </Text>
                  <Tag color="red">时间冲突</Tag>
                </Space>
              </Card>
            ))}
          </Space>
        </Modal>
      </Space>
    </ConfigProvider>
  );
}
