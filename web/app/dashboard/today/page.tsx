"use client";

import {
  ArrowRightOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  BellOutlined,
  DeleteOutlined,
  EditOutlined,
  ExpandOutlined,
  RobotOutlined,
  ReloadOutlined,
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useGSAP } from "@gsap/react";
import { App, Button, Card, DatePicker, Empty, Form, Input, InputNumber, Modal, Popconfirm, Space, Spin, Tag, Typography } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import gsap from "gsap";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import ConflictResolutionModal from "@/components/conflict-resolution-modal";
import { useConflicts } from "@/hooks/useConflicts";
import { useReminders } from "@/hooks/useReminders";
import { useScheduledItems } from "@/hooks/useScheduledItems";
import { useTasks } from "@/hooks/useTasks";
import GanttChart from "@/components/gantt-chart";
import {
  createScheduledItem,
  deleteScheduledItem,
  updateScheduledItem,
  formatDateTime,
  formatRange,
  formatClock,
  getTodayDateKey,
  loadScheduledItem,
  sendAgentMessage,
  type ConflictItem,
  type DashboardSummary,
  type ReminderItem,
  type ScheduledItem,
  type TodayDashboardData,
} from "@/lib/dashboard";

const { Title, Text } = Typography;

gsap.registerPlugin(useGSAP);

function ConflictTimeDisplay({
  conflict,
  timezone,
  accessToken,
}: Readonly<{
  conflict: ConflictItem;
  timezone: string;
  accessToken: string;
}>) {
  const [items, setItems] = useState<{ current: ScheduledItem | null; other: ScheduledItem | null }>({
    current: null,
    other: null,
  });

  useEffect(() => {
    const ids = conflict.related_item_ids;
    if (!ids?.current || !ids?.other) return;
    let alive = true;
    Promise.all([
      loadScheduledItem(ids.current, accessToken).catch(() => null),
      loadScheduledItem(ids.other, accessToken).catch(() => null),
    ]).then(([current, other]) => {
      if (alive) setItems({ current, other });
    });
    return () => {
      alive = false;
    };
  }, [conflict.related_item_ids, accessToken]);

  if (!items.current || !items.other) return null;

  return (
    <Space direction="vertical" size={2} style={{ fontSize: 12 }}>
      <Text className="muted-text">
        {items.current.title}：{formatDateTime(items.current.start_time, timezone)} - {formatDateTime(items.current.end_time, timezone)}
      </Text>
      <Text className="muted-text">
        {items.other.title}：{formatDateTime(items.other.start_time, timezone)} - {formatDateTime(items.other.end_time, timezone)}
      </Text>
    </Space>
  );
}

type ChatRole = "assistant" | "user" | "system";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  meta?: string | null;
  pending?: boolean;
  timestamp: string;
};

type CalendarEventFormValues = {
  title: string;
  description?: string | null;
  start_time: Dayjs;
  end_time?: Dayjs | null;
  timezone: string;
  location?: string | null;
  remind_before_minutes?: number | null;
};

const DEFAULT_TIMEZONE = "Asia/Shanghai";

function getChatTimeLabel() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function createChatId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createWelcomeMessage(): ChatMessage {
  return {
    id: "welcome",
    role: "assistant",
    content: "你可以直接告诉我今天要做什么，我会帮你整理安排、待办和冲突。",
    meta: "支持创建、修改、删除、规划和冲突处理",
    timestamp: getChatTimeLabel(),
  };
}

function sortTimelineEntries<T extends { start_time: string; title: string }>(items: T[]) {
  return [...items].sort((left, right) => {
    const diff = dayjs(left.start_time).valueOf() - dayjs(right.start_time).valueOf();
    if (diff !== 0) {
      return diff;
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


function getConflictColor(severity: string) {
  if (severity === "high") {
    return "red";
  }
  if (severity === "medium") {
    return "gold";
  }
  return "blue";
}

function getReminderColor(status: string) {
  if (status === "fired") {
    return "green";
  }
  if (status === "failed") {
    return "red";
  }
  return "orange";
}

function buildEventFormDefaults(baseDate: Dayjs): CalendarEventFormValues {
  const startTime = baseDate.hour(9).minute(0).second(0).millisecond(0);
  return {
    title: "",
    description: "",
    start_time: startTime,
    end_time: startTime.add(1, "hour"),
    timezone: DEFAULT_TIMEZONE,
    location: "",
    remind_before_minutes: 10,
  };
}


type TodayPageViewProps = Readonly<{
  containerRef: React.RefObject<HTMLDivElement | null>;
  error: string | null;
  loading: boolean;
  timezone: string;
  summary: DashboardSummary;
  progressPercent: number;
  viewData: TodayDashboardData;
  combinedTimeline: Array<{
    id: string;
    start_time: string;
    end_time: string;
    title: string;
    status?: string;
    location?: string | null;
  }>;
  selectedDate: Dayjs;
  nextEvent: { title: string; start_time: string; end_time?: string | null } | null;
  nextReminder: ReminderItem | null;
  agentMessages: ChatMessage[];
  agentMessage: string;
  agentSubmitting: boolean;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
  setAgentMessage: React.Dispatch<React.SetStateAction<string>>;
  handleAgentSubmit: () => Promise<void>;
  resetChat: () => void;
  onNavigateCalendar: () => void;
  onNavigateConflicts: () => void;
  onNavigateReminders: () => void;
  onNavigateAgentLogs: () => void;
  onRefresh: () => void;
  onOpenEventModal: () => void;
  onEditEvent: (item: ScheduledItem) => void;
  onViewConflict: (conflict: ConflictItem) => void;
  onDeleteEvent: (id: string) => void;
  planDate: string;
  accessToken: string;
}>;

function TodayPageView({
  containerRef,
  error,
  loading,
  timezone,
  summary,
  viewData,
  combinedTimeline,
  selectedDate,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  nextEvent,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  nextReminder,
  agentMessages,
  agentMessage,
  agentSubmitting,
  chatEndRef,
  setAgentMessage,
  handleAgentSubmit,
  resetChat,
  onNavigateCalendar,
  onNavigateConflicts,
  onNavigateReminders,
  onNavigateAgentLogs,
  onRefresh,
  onOpenEventModal,
  onEditEvent,
  onViewConflict,
  onDeleteEvent,
  planDate,
  accessToken,
}: TodayPageViewProps) {
  const conflictRows = viewData.conflicts;
  const reminderRows = viewData.reminders;
  const [ganttModalOpen, setGanttModalOpen] = useState(false);
  const ganttItems = useMemo(
    () => combinedTimeline.map((item) => ({
      id: item.id,
      title: item.title,
      start_time: item.start_time,
      end_time: item.end_time,
      status: item.status,
      type: "event" as const,
    })),
    [combinedTimeline],
  );

  return (
    <div ref={containerRef} className="today-page today-page--refined">
      {error ? (
        <div className="today-page__notice today-animate">
          <Tag color="gold">示意数据</Tag>
          <Text className="muted-text">当前网络不可用，已切换为本地示意内容。</Text>
        </div>
      ) : null}
      {loading ? <TodayLoading /> : null}

      <div className="today-layout today-animate">
        <div className="today-main">

          <div className="today-summary-grid">
            <Card className="section-card today-summary-card" variant="borderless">
              <div className="today-summary-card__icon">
                <CalendarOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">今日安排</div>
                <Title level={2} className="today-summary-card__value">
                  {summary.eventsCount as number ?? 0}
                </Title>
                <Text className="muted-text">已排定的时间块</Text>
              </div>
            </Card>
            <Card className="section-card today-summary-card" variant="borderless">
              <div className="today-summary-card__icon">
                <CheckCircleOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">待办任务</div>
                <Title level={2} className="today-summary-card__value">
                  {(summary.tasksCount as number ?? 0)}
                </Title>
                <Text className="muted-text">等待安排的任务</Text>
              </div>
            </Card>
            <Card className="section-card today-summary-card" variant="borderless">
              <div className="today-summary-card__icon">
                <WarningOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">冲突事项</div>
                <Title level={2} className="today-summary-card__value">
                  {(summary.conflictsCount as number ?? 0)}
                </Title>
                <Text className="muted-text">需要处理的冲突</Text>
              </div>
            </Card>
            <Card className="section-card today-summary-card" variant="borderless">
              <div className="today-summary-card__icon">
                <BellOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">提醒任务</div>
                <Title level={2} className="today-summary-card__value">
                  {(summary.remindersCount as number) ?? 0}
                </Title>
                <Text className="muted-text">即将触发提醒</Text>
              </div>
            </Card>
          </div>

          <Card className="section-card today-panel" variant="borderless">
            <div className="today-panel__header today-timeline__header">
              <div>
                <Title level={4} className="today-panel__title">
                  今日时间轴
                </Title>
                <Text className="muted-text">日期：{selectedDate.format("YYYY年M月D日")}</Text>
              </div>
              <Space wrap size={10}>
                <Button icon={<ExpandOutlined />} size="small" onClick={() => setGanttModalOpen(true)}>
                  甘特图
                </Button>
                <Button icon={<ArrowRightOutlined />} type="text" onClick={onNavigateCalendar}>
                  查看日历
                </Button>
              </Space>
            </div>
            {combinedTimeline.length ? (
              <div className="today-timeline-scroll">
                <div className="today-timeline">
                  {combinedTimeline.map((entry) => (
                    <div key={entry.id} className="today-timeline__item">
                      <div className="today-timeline__time">{formatClock(entry.start_time, timezone)}</div>
                      <div className="today-timeline__dot" />
                      <Card className="today-timeline__card" variant="borderless">
                        <div className="today-timeline__head">
                          <Text strong className="today-timeline__title">
                            {entry.title}
                          </Text>
                          <Space size={4}>
                            <Tag color="blue">
                              安排 · {getTimelineStatusLabel(entry)}
                            </Tag>
                            <Button
                              type="text"
                              size="small"
                              icon={<EditOutlined />}
                              onClick={() => {
                                const item = viewData.events.find((e) => e.id === entry.id);
                                if (item) onEditEvent(item);
                              }}
                            />
                            <Popconfirm
                              title="确认删除此安排？"
                              description="删除后不可恢复"
                              onConfirm={() => onDeleteEvent(entry.id)}
                              okText="删除"
                              cancelText="取消"
                            >
                              <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                            </Popconfirm>
                          </Space>
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
              <EmptyState title="今天还没有正式安排" />
            )}
            <Button block className="today-ghost-button" type="default" onClick={onOpenEventModal}>
              + 新增安排
            </Button>

            <Modal
              title="甘特图 · 今日时间概览"
              open={ganttModalOpen}
              onCancel={() => setGanttModalOpen(false)}
              footer={null}
              width={960}
              destroyOnHidden
            >
              <GanttChart
                items={ganttItems}
                baseDate={planDate}
                timezone={timezone}
                maxHeight={280}
              />
            </Modal>
          </Card>
        </div>

        <div className="today-sidebar">
          <div className="today-sidebar__main">
            <Card className="section-card today-panel today-assistant-card" variant="borderless">
              <div className="today-assistant__header">
                <div>
                  <Title level={4} className="today-panel__title today-assistant__title">
                    智能助手
                  </Title>
                  <Space size={8} align="center">
                    <span className="today-assistant__status-indicator" />
                    <Text className="muted-text">在线</Text>
                  </Space>
                </div>
                <Space size={8}>
                  <Button icon={<ReloadOutlined />} type="text" onClick={onRefresh} aria-label="刷新今日数据" />
                  <Button icon={<ExpandOutlined />} type="text" onClick={onNavigateAgentLogs} aria-label="查看 Agent 日志" />
                </Space>
              </div>

              <div className="agent-chat-panel">
                <div className="agent-chat-stream">
                  {agentMessages.map((messageItem) => {
                    const isUser = messageItem.role === "user";
                    const isSystem = messageItem.role === "system";
                    return (
                      <div
                        key={messageItem.id}
                        className={[
                          "agent-chat-row",
                          isUser ? "agent-chat-row--user" : "agent-chat-row--assistant",
                          isSystem ? "agent-chat-row--system" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        <div className="agent-chat-avatar">{isUser ? <UserOutlined /> : <RobotOutlined />}</div>
                        <div
                          className={[
                            "agent-chat-bubble",
                            isUser ? "agent-chat-bubble--user" : "agent-chat-bubble--assistant",
                            isSystem ? "agent-chat-bubble--system" : "",
                            messageItem.pending ? "agent-chat-bubble--pending" : "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                        >
                          <div className="agent-chat-bubble__content">{messageItem.content}</div>
                          {messageItem.meta ? <Text className="agent-chat-bubble__meta">{messageItem.meta}</Text> : null}
                          <Text className="agent-chat-bubble__time">{messageItem.timestamp}</Text>
                        </div>
                      </div>
                    );
                  })}
                  {agentSubmitting ? (
                    <div className="agent-chat-row agent-chat-row--assistant">
                      <div className="agent-chat-avatar">
                        <RobotOutlined />
                      </div>
                      <div className="agent-chat-bubble agent-chat-bubble--assistant agent-chat-bubble--pending">
                        <div className="agent-chat-bubble__content">Agent 正在思考...</div>
                      </div>
                    </div>
                  ) : null}
                  <div ref={chatEndRef} />
                </div>

                <div className="agent-chat-composer">
                  <Input.TextArea
                    value={agentMessage}
                    onChange={(event) => setAgentMessage(event.target.value)}
                    rows={3}
                    autoSize={{ minRows: 3, maxRows: 5 }}
                    placeholder="例如：明天下午 3 点开会，提醒我提前 10 分钟"
                  />
                  <Space wrap className="agent-chat-actions">
                    <Button icon={<ThunderboltOutlined />} onClick={resetChat}>
                      重新开始
                    </Button>
                    <Button type="primary" icon={<SendOutlined />} loading={agentSubmitting} onClick={() => void handleAgentSubmit()}>
                      发送给 Agent
                    </Button>
                  </Space>
                </div>
              </div>
            </Card>
          </div>

          <div className="today-sidebar__foot">
            <Card className="section-card today-panel" variant="borderless">
              <SectionHeader title={`冲突事项 (${conflictRows.length})`} extra={<Button type="text" onClick={onNavigateConflicts}>全部</Button>} />
              {conflictRows.length ? (
                <div className="today-conflict-list">
                  {conflictRows.slice(0, 3).map((conflict) => (
                    <div key={conflict.id} className="today-conflict-item">
                      <span className="today-conflict-item__mark" />
                      <div className="today-conflict-item__content">
                        <div className="today-conflict-item__head">
                          <Text strong className="today-conflict-item__title">
                            {conflict.title}
                          </Text>
                          <Tag color={getConflictColor(conflict.severity)}>{conflict.severity}</Tag>
                        </div>
                        <ConflictTimeDisplay conflict={conflict} timezone={timezone} accessToken={accessToken ?? ""} />
                        {conflict.suggestion ? (
                          <Text className="today-conflict-item__meta">建议：{conflict.suggestion}</Text>
                        ) : null}
                      </div>
                      <Button size="small" onClick={() => onViewConflict(conflict)}>查看</Button>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="当前没有冲突事项" />
              )}
              <Button block className="today-ghost-button" type="default" onClick={onNavigateConflicts}>
                处理冲突
              </Button>
            </Card>

            <Card className="section-card today-panel" variant="borderless">
              <SectionHeader title={`提醒任务 (${reminderRows.length})`} extra={<Button type="text" onClick={onNavigateReminders}>全部</Button>} />
              {reminderRows.length ? (
                <div className="today-reminder-list">
                  {reminderRows.slice(0, 4).map((reminder) => (
                    <div key={reminder.id} className="today-reminder-item">
                      <span className="today-reminder-item__mark" />
                      <div className="today-reminder-item__content">
                        <div className="today-reminder-item__head">
                          <Text strong className="today-reminder-item__title">
                            {reminder.title}
                          </Text>
                          <Tag color={getReminderColor(reminder.status)}>{reminder.status}</Tag>
                        </div>
                        <Text className="today-reminder-item__meta">{formatDateTime(reminder.trigger_time, timezone)}</Text>
                        <Text className="today-reminder-item__meta">
                          重试 {reminder.retry_count}/{reminder.max_retries}
                        </Text>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="当前没有提醒任务" />
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

function TodayLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" />
    </div>
  );
}

function EmptyState({ title }: Readonly<{ title: string }>) {
  return (
    <div className="dashboard-empty">
      <Empty description={title} />
    </div>
  );
}

function SectionHeader({
  title,
  extra,
}: Readonly<{
  title: string;
  extra?: React.ReactNode;
}>) {
  return (
    <div className="today-panel__header">
      <Title level={4} className="today-panel__title">
        {title}
      </Title>
      {extra}
    </div>
  );
}


export default function TodayPage() {
  const { session } = useAuth();
  const router = useRouter();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const planDate = useMemo(() => getTodayDateKey(timezone), [timezone]);
  const selectedDate = useMemo(() => dayjs(planDate), [planDate]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { message } = App.useApp();
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const [agentMessage, setAgentMessage] = useState("");
  const [agentSubmitting, setAgentSubmitting] = useState(false);
  const [agentMessages, setAgentMessages] = useState<ChatMessage[]>(() => [createWelcomeMessage()]);
  const [eventForm] = Form.useForm<CalendarEventFormValues>();
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [eventSubmitting, setEventSubmitting] = useState(false);
  const [editingEvent, setEditingEvent] = useState<ScheduledItem | null>(null);
  const [conflictModalOpen, setConflictModalOpen] = useState(false);
  const [pendingConflicts, setPendingConflicts] = useState<ConflictItem[]>([]);
  const [conflictCurrentItemId, setConflictCurrentItemId] = useState<string>("");

  const { items: events, isLoading: eventsLoading, refresh: refreshEvents } = useScheduledItems({ date: planDate });
  const { items: tasks, isLoading: tasksLoading, refresh: refreshTasks } = useTasks();
  const { items: conflicts, isLoading: conflictsLoading, refresh: refreshConflicts } = useConflicts("open");
  const { items: reminders, isLoading: remindersLoading, refresh: refreshReminders } = useReminders("pending");

  const loading = eventsLoading || tasksLoading || conflictsLoading || remindersLoading;

  const viewData: TodayDashboardData = useMemo(() => ({
    events,
    tasks,
    conflicts,
    reminders,
  }), [events, tasks, conflicts, reminders]);

  const summary = useMemo(() => ({
    eventsCount: viewData.events.length,
    tasksCount: viewData.tasks.length,
    conflictsCount: viewData.conflicts.length,
    remindersCount: viewData.reminders.length,
  }), [viewData]);
  const combinedTimeline = useMemo(() => {
    const entries = viewData.events.map((event) => ({
      id: event.id,
      start_time: event.start_time,
      end_time: event.end_time,
      title: event.title,
      status: event.status,
      location: event.location,
    }));
    return sortTimelineEntries(entries);
  }, [viewData.events]);

  const progressPercent = useMemo(() => {
    const total = viewData.events.length || 5;
    const completed = viewData.events.filter((item) => item.status === "completed").length || 0;
    return Math.min(100, Math.round((completed / total) * 100));
  }, [viewData.events]);

  const nextEvent =
    viewData.events.find((event) => !isPastTime(event.end_time ?? event.start_time)) ?? null;
  const sortedReminders = [...viewData.reminders].sort(
    (left, right) => dayjs(left.trigger_time).valueOf() - dayjs(right.trigger_time).valueOf(),
  );
  const nextReminder = sortedReminders.find((reminder) => !isPastTime(reminder.trigger_time)) ?? null;

  const refreshData = useCallback(() => {
    refreshEvents();
    refreshTasks();
    refreshConflicts();
    refreshReminders();
  }, [refreshEvents, refreshTasks, refreshConflicts, refreshReminders]);

  const openEventModal = useCallback(() => {
    setEditingEvent(null);
    eventForm.setFieldsValue(buildEventFormDefaults(selectedDate));
    setEventModalOpen(true);
  }, [eventForm, selectedDate]);

  const handleNavigateCalendar = useCallback(() => {
    router.push("/dashboard/calendar");
  }, [router]);

  const handleNavigateConflicts = useCallback(() => {
    router.push("/dashboard/conflicts");
  }, [router]);

  const handleNavigateReminders = useCallback(() => {
    router.push("/dashboard/reminders");
  }, [router]);

  const handleNavigateAgentLogs = useCallback(() => {
    router.push("/dashboard/agent-logs");
  }, [router]);

  const handleViewConflict = useCallback(
    (conflict: ConflictItem) => {
      message.info(`已打开冲突列表：${conflict.title}`);
      router.push("/dashboard/conflicts");
    },
    [message, router],
  );

  const handleDeleteEvent = useCallback(
    async (id: string) => {
      if (!accessToken) {
        return;
      }
      try {
        await deleteScheduledItem(id, accessToken);
        message.success("安排已删除");
        refreshData();
      } catch (caughtError: unknown) {
        message.error(caughtError instanceof Error ? caughtError.message : "删除失败");
      }
    },
    [accessToken, refreshData, message],
  );

  const openEditModal = useCallback(
    (item: ScheduledItem) => {
      setEditingEvent(item);
      eventForm.setFieldsValue({
        title: item.title,
        description: item.description ?? "",
        start_time: dayjs(item.start_time),
        end_time: dayjs(item.end_time),
        timezone: item.timezone || timezone || DEFAULT_TIMEZONE,
        location: item.location ?? "",
        remind_before_minutes: item.remind_before_minutes ?? 0,
      });
      setEventModalOpen(true);
      setConflictModalOpen(false);
    },
    [eventForm, timezone],
  );

  const handleConflictEditItem = useCallback(
    (item: ScheduledItem) => {
      openEditModal(item);
    },
    [openEditModal],
  );

  const handleConflictIgnore = useCallback(() => {
    setConflictModalOpen(false);
    setPendingConflicts([]);
    setConflictCurrentItemId("");
  }, []);

  const handleCreateEvent = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const values = await eventForm.validateFields();
      setEventSubmitting(true);
      const endTime = values.end_time ? values.end_time.toISOString() : values.start_time.add(1, "hour").toISOString();
      const result = await createScheduledItem({
        title: values.title.trim(),
        description: values.description?.trim() ? values.description.trim() : null,
        start_time: values.start_time.toISOString(),
        end_time: endTime,
        timezone: values.timezone,
        location: values.location?.trim() ? values.location.trim() : null,
        remind_before_minutes: values.remind_before_minutes ?? 0,
      }, accessToken);
      setEventModalOpen(false);
      eventForm.resetFields();
      refreshData();
      if (result.conflicts && result.conflicts.length > 0) {
        setPendingConflicts(result.conflicts);
        setConflictCurrentItemId(result.item.id);
        setConflictModalOpen(true);
      } else {
        message.success("安排已创建");
      }
    } catch (caughtError: unknown) {
      if (caughtError && typeof caughtError === "object" && "errorFields" in caughtError) {
        return;
      }
      message.error(caughtError instanceof Error ? caughtError.message : "创建安排失败");
    } finally {
      setEventSubmitting(false);
    }
  }, [accessToken, eventForm, refreshData, message]);

  const handleUpdateEvent = useCallback(async () => {
    if (!accessToken || !editingEvent) {
      return;
    }
    try {
      const values = await eventForm.validateFields();
      setEventSubmitting(true);
      const endTime = values.end_time ? values.end_time.toISOString() : values.start_time.add(1, "hour").toISOString();
      const result = await updateScheduledItem(editingEvent.id, {
        title: values.title.trim(),
        description: values.description?.trim() ? values.description.trim() : null,
        start_time: values.start_time.toISOString(),
        end_time: endTime,
        timezone: values.timezone,
        location: values.location?.trim() ? values.location.trim() : null,
        remind_before_minutes: values.remind_before_minutes ?? 0,
      }, accessToken);
      setEventModalOpen(false);
      setEditingEvent(null);
      eventForm.resetFields();
      refreshData();
      if (result.conflicts && result.conflicts.length > 0) {
        setPendingConflicts(result.conflicts);
        setConflictCurrentItemId(result.item.id);
        setConflictModalOpen(true);
      } else {
        message.success("安排已更新");
      }
    } catch (caughtError: unknown) {
      if (caughtError && typeof caughtError === "object" && "errorFields" in caughtError) {
        return;
      }
      message.error(caughtError instanceof Error ? caughtError.message : "更新安排失败");
    } finally {
      setEventSubmitting(false);
    }
  }, [accessToken, editingEvent, eventForm, refreshData, message]);

  const handleAgentSubmit = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    const content = agentMessage.trim();
    if (!content) {
      message.warning("请输入一句话后再发送给 Agent");
      return;
    }
    setAgentSubmitting(true);
    const userMessage: ChatMessage = {
      id: createChatId(),
      role: "user",
      content,
      timestamp: getChatTimeLabel(),
    };
    setAgentMessages((prev) => [
      ...prev,
      userMessage,
      { id: createChatId(), role: "assistant", content: "正在思考...", pending: true, timestamp: getChatTimeLabel() },
    ]);

    try {
      const result = await sendAgentMessage(accessToken, content);
      setAgentMessages((prev) => {
        const next = prev.filter((messageItem) => !messageItem.pending);
        next.push({
          id: createChatId(),
          role: "assistant",
          content: result.final_response || "Agent 已处理",
          meta:
            [
              result.intent ? `intent: ${result.intent}` : null,
              result.pending_state ? "当前处于待处理状态" : null,
            ]
              .filter(Boolean)
              .join(" · ") || null,
          timestamp: getChatTimeLabel(),
        });
        return next;
      });
      if (result.success) {
        message.success(result.final_response || "Agent 已处理");
      } else {
        message.warning(result.final_response || "Agent 返回了待处理结果");
      }
      setAgentMessage("");
      refreshData();
    } catch (caughtError: unknown) {
      const errorMessage = caughtError instanceof Error ? caughtError.message : "发送失败";
      setAgentMessages((prev) => [
        ...prev.filter((messageItem) => !messageItem.pending),
        {
          id: createChatId(),
          role: "system",
          content: errorMessage,
          meta: "Agent 发送失败",
          timestamp: getChatTimeLabel(),
        },
      ]);
      message.error(errorMessage);
    } finally {
      setAgentSubmitting(false);
    }
  }, [accessToken, agentMessage, refreshData, message]);

  const resetChat = useCallback(() => {
    setAgentMessages([createWelcomeMessage()]);
    setAgentMessage("");
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [agentMessages, agentSubmitting]);

  useGSAP(
    () => {
      if (loading) {
        return;
      }

      gsap.from(".today-animate", {
        opacity: 0,
        y: 20,
        duration: 0.8,
        ease: "power3.out",
        stagger: 0.08,
      });
      gsap.from(".today-summary-card, .today-panel", {
        opacity: 0,
        y: 12,
        duration: 0.55,
        ease: "power2.out",
        stagger: 0.05,
      });
    },
    { scope: containerRef, dependencies: [loading], revertOnUpdate: true },
  );

  return (
    <>
      <TodayPageView
        containerRef={containerRef}
        error={null}
        loading={loading}
        timezone={timezone}
        summary={summary}
        progressPercent={progressPercent}
        viewData={viewData}
        combinedTimeline={combinedTimeline}
        selectedDate={selectedDate}
        nextEvent={nextEvent}
        nextReminder={nextReminder}
        agentMessages={agentMessages}
        agentMessage={agentMessage}
        agentSubmitting={agentSubmitting}
        chatEndRef={chatEndRef}
        setAgentMessage={setAgentMessage}
        handleAgentSubmit={handleAgentSubmit}
        resetChat={resetChat}
        onNavigateCalendar={handleNavigateCalendar}
        onNavigateConflicts={handleNavigateConflicts}
        onNavigateReminders={handleNavigateReminders}
        onNavigateAgentLogs={handleNavigateAgentLogs}
        onRefresh={refreshData}
        onOpenEventModal={openEventModal}
        onEditEvent={openEditModal}
        onViewConflict={handleViewConflict}
        onDeleteEvent={(id) => void handleDeleteEvent(id)}
        planDate={planDate}
        accessToken={accessToken ?? ""}
      />

      <Modal
        title={editingEvent ? "编辑安排" : "新建安排"}
        open={eventModalOpen}
        onCancel={() => {
          setEventModalOpen(false);
          setEditingEvent(null);
          eventForm.resetFields();
        }}
        onOk={() => void (editingEvent ? handleUpdateEvent() : handleCreateEvent())}
        okText={editingEvent ? "保存修改" : "创建安排"}
        cancelText="取消"
        confirmLoading={eventSubmitting}
        destroyOnHidden
      >
        <Form form={eventForm} layout="vertical" initialValues={buildEventFormDefaults(selectedDate)}>
          <Form.Item
            label="标题"
            name="title"
            rules={[{ required: true, message: "请输入安排标题" }]}
          >
            <Input placeholder="例如：项目会议" />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input.TextArea rows={3} placeholder="可选" />
          </Form.Item>
          <Form.Item
            label="开始时间"
            name="start_time"
            rules={[{ required: true, message: "请选择开始时间" }]}
          >
            <DatePicker
              showTime={{ format: "HH:mm" }}
              format="YYYY-MM-DD HH:mm"
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Form.Item
            label="结束时间"
            name="end_time"
            rules={[{ required: true, message: "请选择结束时间" }]}
          >
            <DatePicker
              showTime={{ format: "HH:mm" }}
              format="YYYY-MM-DD HH:mm"
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Form.Item label="地点" name="location">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item label="提醒分钟数" name="remind_before_minutes">
            <InputNumber min={0} max={24 * 60} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="时区" name="timezone">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <ConflictResolutionModal
        open={conflictModalOpen}
        conflicts={pendingConflicts}
        currentItemId={conflictCurrentItemId}
        onEditItem={handleConflictEditItem}
        onIgnore={handleConflictIgnore}
        onClose={handleConflictIgnore}
        accessToken={accessToken ?? ""}
        timezone={timezone}
      />

    </>
  );
}
