"use client";

import {
  ArrowRightOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  BellOutlined,
  ExpandOutlined,
  RobotOutlined,
  ReloadOutlined,
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useGSAP } from "@gsap/react";
import { Button, Card, DatePicker, Empty, Form, Input, InputNumber, Modal, Space, Spin, Tag, Typography, message } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import gsap from "gsap";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import {
  formatRange,
  formatClock,
  getTodayDateKey,
  loadTodayDashboard,
  sendAgentMessage,
  type ConflictItem,
  type ReminderItem,
  type ScheduledItem,
  type TaskItem,
  type TodayDashboardData,
} from "@/lib/dashboard";

const { Title, Text } = Typography;

gsap.registerPlugin(useGSAP);

type ChatRole = "assistant" | "user" | "system";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  meta?: string | null;
  pending?: boolean;
  timestamp: string;
};

type DemoDashboard = TodayDashboardData;

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

type GanttRow = {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  status?: string;
  location?: string | null;
  startLabel: string;
  endLabel: string;
  barLeft: number;
  barWidth: number;
};

function buildGanttRows(
  items: Array<{
    id: string;
    title: string;
    start_time: string;
    end_time?: string | null;
    status?: string;
    location?: string | null;
  }>,
  selectedDate: Dayjs,
  timezone: string,
) {
  const dayStart = selectedDate.startOf("day");
  const nextDayStart = dayStart.add(1, "day");
  const totalMinutes = 24 * 60;

  return sortTimelineEntries(items)
    .map((item) => {
      const start = dayjs(item.start_time);
      const rawEnd = dayjs(item.end_time ?? item.start_time);
      const end = rawEnd.isAfter(start) ? rawEnd : start.add(60, "minute");

      if (end.isBefore(dayStart) || start.isAfter(nextDayStart)) {
        return null;
      }

      const clampedStart = start.isBefore(dayStart) ? dayStart : start;
      const clampedEnd = end.isAfter(nextDayStart) ? nextDayStart : end;
      const startMinutes = Math.max(0, clampedStart.diff(dayStart, "minute", true));
      const durationMinutes = Math.max(15, clampedEnd.diff(clampedStart, "minute", true));
      const barLeft = Math.min(100, (startMinutes / totalMinutes) * 100);
      const barWidth = Math.min(100 - barLeft, Math.max(2.5, (durationMinutes / totalMinutes) * 100));

      return {
        id: item.id,
        title: item.title,
        start_time: item.start_time,
        end_time: item.end_time ?? item.start_time,
        status: item.status,
        location: item.location,
        startLabel: formatClock(item.start_time, timezone),
        endLabel: formatClock(item.end_time ?? item.start_time, timezone),
        barLeft,
        barWidth,
      } as GanttRow;
    })
    .filter((item): item is GanttRow => item !== null);
}

function buildDemoDashboardData(planDate: string): DemoDashboard {
  const base = dayjs(planDate);
  const at = (hour: number, minute: number) => base.hour(hour).minute(minute).second(0).millisecond(0).toISOString();
  const events: ScheduledItem[] = [
    {
      id: "demo-event-1",
      title: "API自动化测试 安排 A",
      description: "安排",
      start_time: at(9, 0),
      end_time: at(10, 0),
      timezone: "Asia/Shanghai",
      location: "安排",
      status: "active",
      remind_before_minutes: 10,
    },
    {
      id: "demo-event-2",
      title: "API自动化测试 安排 B",
      description: "安排",
      start_time: at(9, 30),
      end_time: at(10, 30),
      timezone: "Asia/Shanghai",
      location: "安排",
      status: "active",
      remind_before_minutes: 10,
    },
    {
      id: "demo-event-3",
      title: "测试日报-提醒功能验证",
      description: "安排",
      start_time: at(16, 8),
      end_time: at(17, 8),
      timezone: "Asia/Shanghai",
      location: "安排",
      status: "active",
      remind_before_minutes: 5,
    },
    {
      id: "demo-event-4",
      title: "微信提醒测试",
      description: "安排",
      start_time: at(16, 17),
      end_time: at(17, 17),
      timezone: "Asia/Shanghai",
      location: "安排",
      status: "active",
      remind_before_minutes: 5,
    },
  ];

  const tasks: TaskItem[] = [
    { id: "demo-task-1", title: "写论文", description: "120 分钟 · pending", estimated_minutes: 120, deadline: at(23, 59), priority: "medium", status: "pending" },
    { id: "demo-task-2", title: "写论文", description: "120 分钟 · pending", estimated_minutes: 120, deadline: at(23, 59), priority: "medium", status: "pending" },
    { id: "demo-task-3", title: "写论文", description: "120 分钟 · pending", estimated_minutes: 120, deadline: at(23, 59), priority: "medium", status: "pending" },
    { id: "demo-task-4", title: "写论文", description: "120 分钟 · pending", estimated_minutes: 120, deadline: at(23, 59), priority: "medium", status: "pending" },
    { id: "demo-task-5", title: "API自动化测试 任务", description: "120 分钟 · pending · 自动化测试", estimated_minutes: 120, deadline: at(23, 59), priority: "high", status: "pending" },
  ];

  const conflicts: ConflictItem[] = [
    {
      id: "demo-conflict-1",
      conflict_type: "time_overlap",
      severity: "high",
      title: "安排冲突：API自动化测试 安排 A 与 API自动化测试 安排 B",
      description: "存在时间重叠，建议调整其中一个安排时间，或选择忽略冲突。",
      related_item_ids: ["demo-event-1", "demo-event-2"],
      suggestion: "建议：调整其中一个安排时间，或选择忽略冲突。",
      status: "open",
      detected_at: at(8, 52),
    },
  ];

  const reminders: ReminderItem[] = [
    {
      id: "demo-reminder-1",
      target_type: "task",
      target_id: "demo-task-5",
      title: "拍照",
      conversation_id: "demo-conversation-1",
      trigger_time: at(14, 0),
      status: "pending",
      retry_count: 0,
      max_retries: 3,
    },
  ];

  const planItems: ScheduledItem[] = [
    {
      id: "demo-plan-1",
      day_plan_id: "demo-plan",
      title: "API自动化测试 安排 A",
      item_type: "event",
      start_time: at(15, 0),
      end_time: at(16, 0),
      status: "completed",
      is_flexible: false,
      sort_order: 1,
    },
    {
      id: "demo-plan-2",
      day_plan_id: "demo-plan",
      title: "API自动化测试 安排 B",
      item_type: "event",
      start_time: at(15, 30),
      end_time: at(16, 30),
      status: "planned",
      is_flexible: false,
      sort_order: 2,
    },
    {
      id: "demo-plan-3",
      day_plan_id: "demo-plan",
      title: "测试日报-提醒功能验证",
      item_type: "event",
      start_time: at(16, 8),
      end_time: at(17, 8),
      status: "planned",
      is_flexible: false,
      sort_order: 3,
    },
    {
      id: "demo-plan-4",
      day_plan_id: "demo-plan",
      title: "微信提醒测试",
      item_type: "event",
      start_time: at(16, 17),
      end_time: at(17, 17),
      status: "planned",
      is_flexible: false,
      sort_order: 4,
    },
    {
      id: "demo-plan-5",
      day_plan_id: "demo-plan",
      title: "API自动化测试 任务",
      item_type: "task",
      start_time: at(17, 0),
      end_time: at(19, 0),
      status: "planned",
      is_flexible: true,
      sort_order: 5,
    },
  ];

  return {
    plan: {
      id: "demo-plan",
      plan_date: planDate,
      summary: "先把高优先级事项稳住，再推进写论文与评审准备。",
      status: "confirmed",
      items: planItems,
    } as ScheduledItem,
    events,
    tasks,
    conflicts,
    reminders,
  };
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
  contextHolder: React.ReactNode;
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
  onViewConflict: (conflict: ConflictItem) => void;
}>;

function TodayPageView({
  containerRef,
  contextHolder,
  error,
  loading,
  timezone,
  summary,
  progressPercent,
  viewData,
  combinedTimeline,
  selectedDate,
  nextEvent,
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
  onViewConflict,
}: TodayPageViewProps) {
  const conflictRows = viewData.conflicts;
  const reminderRows = viewData.reminders;
  const [ganttModalOpen, setGanttModalOpen] = useState(false);
  const ganttRows = useMemo(
    () => buildGanttRows(combinedTimeline, selectedDate, timezone),
    [combinedTimeline, selectedDate, timezone],
  );

  return (
    <div ref={containerRef} className="today-page today-page--refined">
      {contextHolder}
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
            <Card className="section-card today-summary-card" bordered={false}>
              <div className="today-summary-card__icon">
                <CalendarOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">今日安排</div>
                <Title level={2} className="today-summary-card__value">
                  {summary.eventsCount}
                </Title>
                <Text className="muted-text">已排定的时间块</Text>
              </div>
            </Card>
            <Card className="section-card today-summary-card" bordered={false}>
              <div className="today-summary-card__icon">
                <CheckCircleOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">待办任务</div>
                <Title level={2} className="today-summary-card__value">
                  {summary.tasksCount}
                </Title>
                <Text className="muted-text">等待安排的任务</Text>
              </div>
            </Card>
            <Card className="section-card today-summary-card" bordered={false}>
              <div className="today-summary-card__icon">
                <WarningOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">冲突事项</div>
                <Title level={2} className="today-summary-card__value">
                  {summary.conflictsCount}
                </Title>
                <Text className="muted-text">需要处理的冲突</Text>
              </div>
            </Card>
            <Card className="section-card today-summary-card" bordered={false}>
              <div className="today-summary-card__icon">
                <BellOutlined />
              </div>
              <div>
                <div className="today-summary-card__label">提醒任务</div>
                <Title level={2} className="today-summary-card__value">
                  {summary.remindersCount}
                </Title>
                <Text className="muted-text">即将触发提醒</Text>
              </div>
            </Card>
          </div>

          <Card className="section-card today-panel" bordered={false}>
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
                      <Card className="today-timeline__card" bordered={false}>
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
              destroyOnClose
            >
              <GanttChartAnimated rows={ganttRows} />
            </Modal>
          </Card>
        </div>

        <div className="today-sidebar">
          <div className="today-sidebar__main">
            <Card className="section-card today-panel today-assistant-card" bordered={false}>
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
            <Card className="section-card today-panel" bordered={false}>
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
                        {conflict.description ? (
                          <Text className="today-conflict-item__meta">{conflict.description}</Text>
                        ) : null}
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

            <Card className="section-card today-panel" bordered={false}>
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
                        <Text className="today-reminder-item__meta">{formatRange(reminder.trigger_time, undefined, timezone)}</Text>
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
      <Spin size="large" tip="正在加载今日数据..." />
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

function GanttChartAnimated({ rows }: Readonly<{ rows: GanttRow[] }>) {
  const ganttRef = useRef<HTMLDivElement | null>(null);

  useGSAP(
    () => {
      gsap.from(ganttRef.current?.querySelectorAll(".today-gantt__bar") ?? [], {
        scaleX: 0,
        transformOrigin: "left center",
        duration: 0.5,
        stagger: 0.06,
        ease: "power3.out",
        clearProps: "scaleX",
      });
    },
    { scope: ganttRef, dependencies: [] },
  );

  return (
    <div ref={ganttRef} className="today-gantt">
      <div className="today-gantt__axis">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
      <div className="today-gantt__bars">
        {rows.map((row) => (
          <div key={row.id} className="today-gantt__track">
            <div className="today-gantt__grid" />
            <div
              className="today-gantt__bar"
              style={{ left: `${row.barLeft}%`, width: `${Math.max(row.barWidth, 3)}%` }}
              title={`${row.title}\n${row.startLabel} - ${row.endLabel}`}
            >
              <span className="today-gantt__bar-title">{row.title}</span>
              <span className="today-gantt__bar-time">{row.startLabel}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TodayPage() {
  const { session } = useAuth();
  const router = useRouter();
  const accessToken = session?.accessToken;
  const { timezone, loading: timezoneLoading } = useDashboardTimezone();
  const planDate = useMemo(() => getTodayDateKey(timezone), [timezone]);
  const selectedDate = useMemo(() => dayjs(planDate), [planDate]);
  const demoData = useMemo(() => buildDemoDashboardData(planDate), [planDate]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const [data, setData] = useState<TodayDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentMessage, setAgentMessage] = useState("");
  const [agentSubmitting, setAgentSubmitting] = useState(false);
  const [agentMessages, setAgentMessages] = useState<ChatMessage[]>(() => [createWelcomeMessage()]);
  const [eventForm] = Form.useForm<CalendarEventFormValues>();
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [eventSubmitting, setEventSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看今日安排");
      return;
    }
    if (timezoneLoading) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await loadTodayDashboard(accessToken, planDate);
      setData(result);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "未知错误");
    } finally {
      setLoading(false);
    }
  }, [accessToken, planDate, timezoneLoading]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const viewData = data ?? demoData;

  const summary = useMemo(() => buildDashboardSummary(viewData), [viewData]);
  const sortedEvents = useMemo(
    () => [...viewData.events].sort((left, right) => dayjs(left.start_time).valueOf() - dayjs(right.start_time).valueOf()),
    [viewData.events],
  );
  const sortedReminders = useMemo(
    () =>
      [...viewData.reminders].sort(
        (left, right) => dayjs(left.trigger_time).valueOf() - dayjs(right.trigger_time).valueOf(),
      ),
    [viewData.reminders],
  );
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
  const nextReminder = sortedReminders.find((reminder) => !isPastTime(reminder.trigger_time)) ?? null;

  const refreshData = useCallback(() => {
    void fetchData();
  }, [fetchData]);

  const openEventModal = useCallback(() => {
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
      messageApi.info(`已打开冲突列表：${conflict.title}`);
      router.push("/dashboard/conflicts");
    },
    [messageApi, router],
  );

  const handleCreateEvent = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const values = await eventForm.validateFields();
      setEventSubmitting(true);
      await createCalendarEvent(accessToken, {
        title: values.title.trim(),
        description: values.description?.trim() ? values.description.trim() : null,
        start_time: values.start_time.toISOString(),
        end_time: values.end_time ? values.end_time.toISOString() : null,
        timezone: values.timezone,
        location: values.location?.trim() ? values.location.trim() : null,
        remind_before_minutes: values.remind_before_minutes ?? null,
      });
      messageApi.success("安排已创建");
      setEventModalOpen(false);
      eventForm.resetFields();
      await fetchData();
    } catch (caughtError: unknown) {
      if (caughtError && typeof caughtError === "object" && "errorFields" in caughtError) {
        return;
      }
      messageApi.error(caughtError instanceof Error ? caughtError.message : "创建安排失败");
    } finally {
      setEventSubmitting(false);
    }
  }, [accessToken, eventForm, fetchData, messageApi]);

  const handleAgentSubmit = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    const content = agentMessage.trim();
    if (!content) {
      messageApi.warning("请输入一句话后再发送给 Agent");
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
        messageApi.success(result.final_response || "Agent 已处理");
      } else {
        messageApi.warning(result.final_response || "Agent 返回了待处理结果");
      }
      setAgentMessage("");
      await fetchData();
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
      messageApi.error(errorMessage);
    } finally {
      setAgentSubmitting(false);
    }
  }, [accessToken, agentMessage, fetchData, messageApi]);

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
        contextHolder={contextHolder}
        error={error}
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
        onViewConflict={handleViewConflict}
      />

      <Modal
        title="新建安排"
        open={eventModalOpen}
        onCancel={() => {
          setEventModalOpen(false);
          eventForm.resetFields();
        }}
        onOk={() => void handleCreateEvent()}
        okText="创建安排"
        cancelText="取消"
        confirmLoading={eventSubmitting}
        destroyOnClose
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

    </>
  );
}
