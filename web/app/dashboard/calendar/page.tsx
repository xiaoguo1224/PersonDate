"use client";

import {
  CalendarOutlined,
  DeleteOutlined,
  EditOutlined,
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
  Divider,
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
  Timeline,
  Typography,
  message,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import dayjs, { type Dayjs } from "dayjs";
import "dayjs/locale/zh-cn";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import {
  confirmDayPlan,
  createCalendarEvent,
  deleteCalendarEvent,
  formatRange,
  generateDayPlan,
  loadCalendarEvents,
  loadDayPlan,
  type CalendarEventItem,
  type CalendarEventUpsertPayload,
  type DayPlan,
} from "@/lib/dashboard";

dayjs.locale("zh-cn");

const { Title, Paragraph, Text } = Typography;
const DEFAULT_TIMEZONE = "Asia/Shanghai";

type CalendarViewMode = "month" | "week" | "day";

type CalendarEventFormValues = {
  title: string;
  description?: string | null;
  start_time: Dayjs;
  end_time?: Dayjs | null;
  timezone: string;
  location?: string | null;
  remind_before_minutes?: number | null;
};

type WeekTimelineEventSegment = {
  event: CalendarEventItem;
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

function toDisplayDate(value: Dayjs) {
  return value.format("YYYY年M月D日");
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

function isEventInRange(event: CalendarEventItem, start: Dayjs, end: Dayjs) {
  const eventStart = dayjs(event.start_time);
  const eventEnd = event.end_time ? dayjs(event.end_time) : eventStart;
  return eventStart.isBefore(end) && eventEnd.isAfter(start);
}

function sortEvents(items: CalendarEventItem[]) {
  return [...items].sort((left, right) => {
    const startDiff = dayjs(left.start_time).valueOf() - dayjs(right.start_time).valueOf();
    if (startDiff !== 0) {
      return startDiff;
    }
    return left.title.localeCompare(right.title, "zh-CN");
  });
}

function getEventColor(status: string) {
  if (status === "deleted") {
    return "default";
  }
  if (status === "completed") {
    return "green";
  }
  return "cyan";
}

function getPlanColor(status: string) {
  if (status === "confirmed") {
    return "green";
  }
  if (status === "draft") {
    return "gold";
  }
  return "blue";
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
      background: "linear-gradient(180deg, rgba(52, 211, 153, 0.22), rgba(8, 15, 27, 0.94))",
    };
  }
  if (status === "deleted") {
    return {
      accent: "#94a3b8",
      background: "linear-gradient(180deg, rgba(148, 163, 184, 0.16), rgba(8, 15, 27, 0.92))",
    };
  }
  return {
    accent: "#7dd3fc",
    background: "linear-gradient(180deg, rgba(125, 211, 252, 0.22), rgba(8, 15, 27, 0.94))",
  };
}

function getEffectiveEventEnd(event: CalendarEventItem) {
  const eventStart = dayjs(event.start_time);
  const rawEnd = event.end_time ? dayjs(event.end_time) : eventStart.add(30, "minute");
  return rawEnd.isAfter(eventStart) ? rawEnd : eventStart.add(30, "minute");
}

function buildWeekTimelineDays(weekDays: Dayjs[], events: CalendarEventItem[]): WeekTimelineDay[] {
  return weekDays.map((day) => {
    const dayStart = day.startOf("day");
    const dayEnd = day.add(1, "day");
    const segments: WeekTimelineEventSegment[] = [];

    events
      .filter((event) => event.status !== "deleted")
      .filter((event) => isEventInRange(event, dayStart, dayEnd))
      .forEach((event) => {
        const eventStart = dayjs(event.start_time);
        const eventEnd = getEffectiveEventEnd(event);
        const segmentStart = eventStart.isBefore(dayStart) ? dayStart : eventStart;
        const segmentEnd = eventEnd.isAfter(dayEnd) ? dayEnd : eventEnd;
        const topMinutes = segmentStart.diff(dayStart, "minute", true);
        const durationMinutes = Math.max(1, segmentEnd.diff(segmentStart, "minute", true));
        segments.push({
          event,
          top: (topMinutes / 60) * WEEK_TIMELINE_HOUR_HEIGHT,
          height: Math.max(
            (durationMinutes / 60) * WEEK_TIMELINE_HOUR_HEIGHT,
            WEEK_TIMELINE_MIN_EVENT_HEIGHT,
          ),
          laneIndex: 0,
          laneCount: 1,
          startLabel: segmentStart.format("HH:mm"),
          endLabel: segmentEnd.format("HH:mm"),
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

    const laneEnds: number[] = [];
    segments.forEach((segment) => {
      let laneIndex = laneEnds.findIndex((end) => end <= segment.top);
      if (laneIndex === -1) {
        laneIndex = laneEnds.length;
        laneEnds.push(segment.top + segment.height);
      } else {
        laneEnds[laneIndex] = segment.top + segment.height;
      }
      segment.laneIndex = laneIndex;
    });

    const laneCount = Math.max(1, laneEnds.length);
    segments.forEach((segment) => {
      segment.laneCount = laneCount;
    });

    return {
      day,
      dayKey: day.format("YYYY-MM-DD"),
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
  const [form] = Form.useForm<CalendarEventFormValues>();
  const [messageApi, contextHolder] = message.useMessage();
  const detailAnchorRef = useRef<HTMLDivElement | null>(null);

  const [viewMode, setViewMode] = useState<CalendarViewMode>("month");
  const [focusDate, setFocusDate] = useState(() => dayjs());
  const [events, setEvents] = useState<CalendarEventItem[]>([]);
  const [dayPlan, setDayPlan] = useState<DayPlan | null>(null);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [planLoading, setPlanLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEventItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [planSubmitting, setPlanSubmitting] = useState(false);

  const fetchEvents = useCallback(async () => {
    if (!accessToken) {
      setEventsLoading(false);
      return;
    }
    setEventsLoading(true);
    setEventsError(null);
    try {
      const result = await loadCalendarEvents(accessToken);
      setEvents(sortEvents(result.items));
    } catch (caughtError: unknown) {
      setEventsError(caughtError instanceof Error ? caughtError.message : "未知错误");
    } finally {
      setEventsLoading(false);
    }
  }, [accessToken]);

  const fetchDayPlan = useCallback(async () => {
    if (!accessToken) {
      setPlanLoading(false);
      return;
    }
    setPlanLoading(true);
    setPlanError(null);
    try {
      const result = await loadDayPlan(accessToken, toDateKey(focusDate));
      setDayPlan(result);
    } catch (caughtError: unknown) {
      setPlanError(caughtError instanceof Error ? caughtError.message : "未知错误");
    } finally {
      setPlanLoading(false);
    }
  }, [accessToken, focusDate]);

  useEffect(() => {
    if (!accessToken) {
      setEventsLoading(false);
      setPlanLoading(false);
      setEventsError("请先登录后查看日程总览");
      return;
    }
    void fetchEvents();
  }, [accessToken, fetchEvents]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    void fetchDayPlan();
  }, [accessToken, fetchDayPlan]);

  const viewRange = useMemo(() => getViewRange(viewMode, focusDate), [focusDate, viewMode]);
  const visibleEvents = useMemo(
    () => sortEvents(events.filter((event) => isEventInRange(event, viewRange.start, viewRange.end))),
    [events, viewRange.end, viewRange.start],
  );
  const selectedDayEvents = useMemo(
    () =>
      sortEvents(
        events.filter((event) =>
          isEventInRange(event, focusDate.startOf("day"), focusDate.endOf("day")),
        ),
      ),
    [events, focusDate],
  );
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, index) => startOfWeek(focusDate).add(index, "day")),
    [focusDate],
  );
  const weekTimelineDays = useMemo(
    () => buildWeekTimelineDays(weekDays, events),
    [events, weekDays],
  );
  const monthGridDays = useMemo(() => buildMonthGridDays(focusDate), [focusDate]);
  const monthEventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEventItem[]>();
    events
      .filter((event) => event.status !== "deleted")
      .forEach((event) => {
        const key = dayjs(event.start_time).format("YYYY-MM-DD");
        const next = map.get(key) ?? [];
        next.push(event);
        map.set(key, next);
      });
    return map;
  }, [events]);
  const selectedDateKey = focusDate.format("YYYY-MM-DD");
  const todayKey = dayjs().format("YYYY-MM-DD");

  const summary = useMemo(() => {
    const plannedItems = dayPlan?.items ?? [];
    const activeEvents = events.filter((event) => event.status !== "deleted");
    return {
      totalEvents: activeEvents.length,
      visibleEvents: visibleEvents.length,
      selectedEvents: selectedDayEvents.length,
      planItems: plannedItems.length,
      planStatus: dayPlan?.status ?? "none",
    };
  }, [dayPlan, events, selectedDayEvents.length, visibleEvents.length]);

  const openCreateModal = useCallback(
    (initialDate?: Dayjs) => {
      const baseDate = (initialDate ?? focusDate).hour(9).minute(0).second(0).millisecond(0);
      form.setFieldsValue({
        title: "",
        description: "",
        start_time: baseDate,
        end_time: baseDate.add(1, "hour"),
        timezone: DEFAULT_TIMEZONE,
        location: "",
        remind_before_minutes: 10,
      });
      setEditingEvent(null);
      setModalOpen(true);
    },
    [focusDate, form],
  );

  const openEditModal = useCallback(
    (event: CalendarEventItem) => {
      setEditingEvent(event);
      form.setFieldsValue({
        title: event.title,
        description: event.description ?? "",
        start_time: dayjs(event.start_time),
        end_time: event.end_time ? dayjs(event.end_time) : null,
        timezone: event.timezone || DEFAULT_TIMEZONE,
        location: event.location ?? "",
        remind_before_minutes: event.remind_before_minutes ?? 0,
      });
      setModalOpen(true);
    },
    [form],
  );

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setEditingEvent(null);
    form.resetFields();
  }, [form]);

  const refreshData = useCallback(async () => {
    await Promise.all([fetchEvents(), fetchDayPlan()]);
  }, [fetchDayPlan, fetchEvents]);

  const handleSubmit = useCallback(
    async (values: CalendarEventFormValues) => {
      if (!accessToken) {
        return;
      }
      if (values.end_time && values.end_time.isBefore(values.start_time)) {
        messageApi.error("结束时间不能早于开始时间");
        return;
      }
      const payload: CalendarEventUpsertPayload = {
        title: values.title.trim(),
        description: values.description?.trim() || null,
        start_time: values.start_time.toISOString(),
        end_time: values.end_time ? values.end_time.toISOString() : null,
        timezone: values.timezone || DEFAULT_TIMEZONE,
        location: values.location?.trim() || null,
        remind_before_minutes: values.remind_before_minutes ?? 0,
      };

      setSubmitting(true);
      try {
        if (editingEvent) {
          await requestJson(
            `/api/calendar-events/${editingEvent.id}`,
            {
              method: "PATCH",
              body: JSON.stringify(payload),
            },
            accessToken,
          );
          messageApi.success("日程已更新");
        } else {
          await createCalendarEvent(accessToken, payload);
          messageApi.success("日程已创建");
        }
        closeModal();
        await refreshData();
      } catch (caughtError: unknown) {
        messageApi.error(caughtError instanceof Error ? caughtError.message : "保存失败");
      } finally {
        setSubmitting(false);
      }
    },
    [accessToken, closeModal, editingEvent, messageApi, refreshData],
  );

  const handleDelete = useCallback(
    (event: CalendarEventItem) => {
      if (!accessToken) {
        return;
      }
      Modal.confirm({
        title: "删除日程",
        content: `确认删除「${event.title}」吗？`,
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        centered: true,
        onOk: async () => {
          await deleteCalendarEvent(accessToken, event.id);
          messageApi.success("日程已删除");
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
      const result = await generateDayPlan(accessToken, toDateKey(focusDate));
      setDayPlan(result);
      messageApi.success("计划草案已生成");
    } catch (caughtError: unknown) {
      messageApi.error(caughtError instanceof Error ? caughtError.message : "生成失败");
    } finally {
      setPlanSubmitting(false);
      await fetchDayPlan();
    }
  }, [accessToken, fetchDayPlan, focusDate, messageApi]);

  const handleConfirmPlan = useCallback(async () => {
    if (!accessToken || !dayPlan) {
      return;
    }
    setPlanSubmitting(true);
    try {
      await confirmDayPlan(accessToken, dayPlan.id);
      messageApi.success("计划已确认");
      await fetchDayPlan();
    } catch (caughtError: unknown) {
      messageApi.error(caughtError instanceof Error ? caughtError.message : "确认失败");
    } finally {
      setPlanSubmitting(false);
    }
  }, [accessToken, dayPlan, fetchDayPlan, messageApi]);

  const selectedDayPlanItems = dayPlan?.items ?? [];

  const heroTags = [
    { color: "cyan", label: `${summary.totalEvents} 条日程` },
    { color: "orange", label: `${summary.visibleEvents} 条当前视图` },
    { color: "gold", label: `${summary.planItems} 条计划项` },
    { color: "green", label: summary.planStatus === "none" ? "未生成计划" : summary.planStatus },
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
            <Title style={{ color: "var(--text-primary)", margin: 0 }}>日程总览</Title>
            <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
              这里已经接入后端的 `calendar_events` 列表，并补齐了月/周/日视图、创建、编辑、删除，以及当日计划草案和确认入口。
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
        {planError ? (
          <Alert type="warning" showIcon message="加载计划失败" description={planError} />
        ) : null}

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
                  新建日程
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
              <Text className="muted-text">计划状态</Text>
              <Title level={4} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                {summary.planStatus === "none" ? "未生成" : summary.planStatus}
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
                      <Tag color="cyan">{visibleEvents.length} 条当前月日程</Tag>
                      <Tag color="gold">{selectedDayEvents.length} 条选中日程</Tag>
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
                                  ? "linear-gradient(135deg, rgba(125, 211, 252, 0.95), rgba(59, 130, 246, 0.82))"
                                  : isToday
                                    ? "rgba(251, 191, 36, 0.2)"
                                    : "rgba(255, 255, 255, 0.04)",
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
                            {!items.length ? <span className="calendar-month-cell__empty">暂无日程</span> : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : viewMode === "week" ? (
                <Space direction="vertical" size={16} style={{ width: "100%" }} className="calendar-week-shell">
                  <div
                    className="calendar-week-scroll"
                    style={{ minWidth: WEEK_TIMELINE_GUTTER_WIDTH + weekDays.length * WEEK_TIMELINE_MIN_COLUMN_WIDTH }}
                  >
                    <div className="calendar-week-header-grid">
                      <div className="calendar-week-gutter calendar-week-gutter--header">
                        <Text className="muted-text">时间</Text>
                      </div>
                      {weekTimelineDays.map(({ day, dayKey, segments }) => {
                        const isSelected = day.isSame(focusDate, "day");
                        const isToday = day.isSame(dayjs(), "day");
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
                        const isToday = day.isSame(dayjs(), "day");
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
                              {segments.map((segment) => {
                                const theme = getWeekEventTheme(segment.event.status);
                                return (
                                  <button
                                    key={`${segment.event.id}-${dayKey}-${segment.startLabel}`}
                                    type="button"
                                    className="calendar-week-event"
                                    onClick={(eventClick) => {
                                      eventClick.stopPropagation();
                                      setFocusDate(day);
                                      openEditModal(segment.event);
                                    }}
                                    style={{
                                      top: segment.top,
                                      height: segment.height,
                                      left: `calc(${(segment.laneIndex / segment.laneCount) * 100}% + 4px)`,
                                      width: `calc(${100 / segment.laneCount}% - 8px)`,
                                      borderColor: theme.accent,
                                      background: theme.background,
                                    }}
                                  >
                                    <span
                                      className="calendar-week-event__accent"
                                      style={{ background: theme.accent }}
                                    />
                                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                                      <Text strong ellipsis className="calendar-week-event__title">
                                        {segment.event.title}
                                      </Text>
                                      <Text className="calendar-week-event__time">
                                        {segment.startLabel} - {segment.endLabel}
                                      </Text>
                                      {segment.event.location ? (
                                        <Text className="calendar-week-event__location" ellipsis>
                                          {segment.event.location}
                                        </Text>
                                      ) : null}
                                    </Space>
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <Text className="muted-text">
                    点击某个日期标题可切换右侧详情，点击日程块可直接编辑。
                  </Text>
                </Space>
              ) : selectedDayEvents.length ? (
                <Timeline
                  className="calendar-day-timeline"
                  items={selectedDayEvents.map((event) => ({
                    color: getEventColor(event.status),
                    children: (
                      <Space direction="vertical" size={6} style={{ width: "100%" }}>
                        <Space wrap align="center">
                          <Text strong>{event.title}</Text>
                          <Tag color={getEventColor(event.status)}>{event.status}</Tag>
                          {event.location ? <Tag>{event.location}</Tag> : null}
                        </Space>
                        <Text className="muted-text">{formatRange(event.start_time, event.end_time)} · 日程详情</Text>
                        <Space wrap>
                          <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(event)}>
                            编辑
                          </Button>
                          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(event)}>
                            删除
                          </Button>
                        </Space>
                      </Space>
                    ),
                  }))}
                />
              ) : (
                <EmptyPanel title="这一天还没有安排日程" />
              )}
            </Card>
          </Col>

          <Col xs={24} xl={8}>
            <div ref={detailAnchorRef}>
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card
                  className="section-card"
                  bordered={false}
                  title={`${toDisplayDate(focusDate)} 的计划`}
                  extra={
                    <Space wrap>
                      {dayPlan?.status === "draft" ? (
                        <Button type="primary" loading={planSubmitting} onClick={() => void handleConfirmPlan()}>
                          确认计划
                        </Button>
                      ) : null}
                      {!dayPlan ? (
                        <Button loading={planSubmitting} onClick={() => void handleGeneratePlan()}>
                          生成草案
                        </Button>
                      ) : null}
                    </Space>
                  }
                >
                  {planLoading ? (
                    <CalendarLoading />
                  ) : dayPlan ? (
                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                      <Space wrap>
                        <Tag color={getPlanColor(dayPlan.status)}>{dayPlan.status}</Tag>
                        <Tag color="cyan">{dayPlan.items.length} 条计划项</Tag>
                      </Space>
                      <Text className="muted-text">{dayPlan.summary || "暂无计划摘要"}</Text>
                      <Divider style={{ margin: "8px 0" }} />
                      {selectedDayPlanItems.length ? (
                        <Timeline
                          items={selectedDayPlanItems.map((item) => ({
                            color: item.status === "completed" ? "green" : "gold",
                            children: (
                              <Space direction="vertical" size={2}>
                                <Text strong>{item.title}</Text>
                                <Text className="muted-text">
                                  {formatRange(item.start_time, item.end_time)} · {item.item_type} · {item.status}
                                </Text>
                              </Space>
                            ),
                          }))}
                        />
                      ) : (
                        <Empty description="这一天还没有计划项" />
                      )}
                    </Space>
                  ) : (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Text className="muted-text">当前日期还没有生成正式计划。</Text>
                      <Text className="muted-text">你可以先生成计划草案，系统会自动把任务填进这一天。</Text>
                    </Space>
                  )}
                </Card>

                <Card className="section-card" bordered={false} title="当日日程">
                  {selectedDayEvents.length ? (
                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                      {selectedDayEvents.map((event) => (
                        <Card
                          key={event.id}
                          size="small"
                          bordered={false}
                          style={{
                            background: "rgba(255,255,255,0.04)",
                            cursor: "pointer",
                          }}
                          onClick={() => openEditModal(event)}
                          extra={
                            <Space>
                              <Button
                                size="small"
                                icon={<EditOutlined />}
                                onClick={(eventClick) => {
                                  eventClick.stopPropagation();
                                  openEditModal(event);
                                }}
                              >
                                编辑
                              </Button>
                              <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={(eventClick) => {
                                  eventClick.stopPropagation();
                                  handleDelete(event);
                                }}
                              >
                                删除
                              </Button>
                            </Space>
                          }
                        >
                          <Space direction="vertical" size={6} style={{ width: "100%" }}>
                            <Space wrap>
                              <Text strong>{event.title}</Text>
                              <Tag color={getEventColor(event.status)}>{event.status}</Tag>
                              {event.location ? <Tag>{event.location}</Tag> : null}
                            </Space>
                            <Text className="muted-text">
                              {formatRange(event.start_time, event.end_time)} · 提醒{" "}
                              {event.remind_before_minutes ?? 0} 分钟
                            </Text>
                            {event.description ? <Text className="muted-text">{event.description}</Text> : null}
                          </Space>
                        </Card>
                      ))}
                    </Space>
                  ) : (
                    <EmptyPanel title="选中日期暂无日程" />
                  )}
                </Card>
              </Space>
            </div>
          </Col>
        </Row>

        <Modal
          title={editingEvent ? "编辑日程" : "新建日程"}
          open={modalOpen}
          onCancel={closeModal}
          destroyOnClose
          okText={editingEvent ? "保存修改" : "创建日程"}
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
              rules={[{ required: true, message: "请输入日程标题" }]}
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
      </Space>
    </ConfigProvider>
  );
}
