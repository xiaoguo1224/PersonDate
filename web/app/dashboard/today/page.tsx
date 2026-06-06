"use client";

import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CoffeeOutlined,
  FireOutlined,
  RobotOutlined,
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Button, Card, Empty, Input, Progress, Space, Spin, Tag, Typography, message } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  buildDashboardSummary,
  formatRange,
  loadTodayDashboard,
  sendAgentMessage,
  type CalendarEventItem,
  type ConflictItem,
  type DayPlan,
  type DayPlanItem,
  type ReminderItem,
  type TaskItem,
  type TodayDashboardData,
} from "@/lib/dashboard";

const { Title, Paragraph, Text } = Typography;

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

function getTodayString() {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

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
    content: "你可以直接告诉我今天要做什么，我会帮你整理日程、任务、计划和冲突。",
    meta: "支持创建、修改、删除、规划和冲突处理",
    timestamp: getChatTimeLabel(),
  };
}

function startOfMonthGrid(value: Dayjs) {
  const firstDayOfMonth = value.startOf("month");
  const weekday = firstDayOfMonth.day();
  const diff = weekday === 0 ? -6 : 1 - weekday;
  return firstDayOfMonth.add(diff, "day").startOf("day");
}

function buildMonthGrid(value: Dayjs) {
  const gridStart = startOfMonthGrid(value);
  return Array.from({ length: 42 }, (_, index) => gridStart.add(index, "day"));
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

function buildDemoDashboardData(planDate: string): DemoDashboard {
  const base = dayjs(planDate);
  const at = (hour: number, minute: number) => base.hour(hour).minute(minute).second(0).millisecond(0).toISOString();
  const events: CalendarEventItem[] = [
    {
      id: "demo-event-1",
      title: "团队晨会",
      description: "同步进度与风险",
      start_time: at(9, 0),
      end_time: at(9, 30),
      timezone: "Asia/Shanghai",
      location: "线上会议",
      status: "active",
      remind_before_minutes: 10,
    },
    {
      id: "demo-event-2",
      title: "产品需求评审",
      description: "Q3 重点方案对齐",
      start_time: at(10, 0),
      end_time: at(11, 30),
      timezone: "Asia/Shanghai",
      location: "会议室 A",
      status: "active",
      remind_before_minutes: 10,
    },
    {
      id: "demo-event-3",
      title: "专注工作：文档撰写",
      description: "深度工作",
      start_time: at(13, 30),
      end_time: at(15, 30),
      timezone: "Asia/Shanghai",
      location: "工作区",
      status: "active",
      remind_before_minutes: 15,
    },
    {
      id: "demo-event-4",
      title: "运动健身",
      description: "保持状态",
      start_time: at(16, 0),
      end_time: at(17, 0),
      timezone: "Asia/Shanghai",
      location: "健身房",
      status: "active",
      remind_before_minutes: 20,
    },
    {
      id: "demo-event-5",
      title: "阅读与复盘",
      description: "日终整理",
      start_time: at(20, 0),
      end_time: at(21, 0),
      timezone: "Asia/Shanghai",
      location: "家中",
      status: "active",
      remind_before_minutes: 30,
    },
  ];

  const tasks: TaskItem[] = [
    { id: "demo-task-1", title: "写论文", description: "每日推进", estimated_minutes: 120, deadline: at(23, 59), priority: "medium", status: "pending" },
    { id: "demo-task-2", title: "整理竞品分析报告", description: "补充图表", estimated_minutes: 90, deadline: at(18, 0), priority: "high", status: "pending" },
    { id: "demo-task-3", title: "设计评审准备", description: "对齐文档", estimated_minutes: 60, deadline: at(12, 0), priority: "medium", status: "pending" },
    { id: "demo-task-4", title: "用户调研计划", description: "可后置", estimated_minutes: 45, deadline: at(19, 0), priority: "low", status: "pending" },
    { id: "demo-task-5", title: "运营数据复盘", description: "周报准备", estimated_minutes: 60, deadline: at(21, 0), priority: "low", status: "pending" },
  ];

  const conflicts: ConflictItem[] = [
    {
      id: "demo-conflict-1",
      conflict_type: "time_overlap",
      severity: "high",
      title: "团队晨会与需求评审存在 30 分钟重叠",
      description: "09:30 - 10:00 时间段已被晨会占用。",
      related_item_ids: ["demo-event-1", "demo-event-2"],
      suggestion: "将需求评审顺延 30 分钟，或缩短晨会时长。",
      status: "open",
      detected_at: at(8, 52),
    },
    {
      id: "demo-conflict-2",
      conflict_type: "deadline_risk",
      severity: "medium",
      title: "写论文进度略慢",
      description: "预计剩余 120 分钟，距离今晚截止较近。",
      related_item_ids: ["demo-task-1"],
      suggestion: "优先在下午深度工作时段推进。",
      status: "open",
      detected_at: at(8, 55),
    },
  ];

  const reminders: ReminderItem[] = [
    {
      id: "demo-reminder-1",
      target_type: "event",
      target_id: "demo-event-2",
      title: "产品需求评审提醒",
      conversation_id: "demo-conversation-1",
      trigger_time: at(9, 50),
      status: "pending",
      retry_count: 0,
      max_retries: 3,
    },
    {
      id: "demo-reminder-2",
      target_type: "task",
      target_id: "demo-task-1",
      title: "写论文开始提醒",
      conversation_id: "demo-conversation-1",
      trigger_time: at(13, 20),
      status: "pending",
      retry_count: 0,
      max_retries: 3,
    },
    {
      id: "demo-reminder-3",
      target_type: "event",
      target_id: "demo-event-4",
      title: "运动健身提醒",
      conversation_id: "demo-conversation-1",
      trigger_time: at(15, 40),
      status: "pending",
      retry_count: 0,
      max_retries: 3,
    },
  ];

  const planItems: DayPlanItem[] = [
    {
      id: "demo-plan-1",
      day_plan_id: "demo-plan",
      title: "团队晨会",
      item_type: "event",
      start_time: at(9, 0),
      end_time: at(9, 30),
      status: "completed",
      is_flexible: false,
      sort_order: 1,
    },
    {
      id: "demo-plan-2",
      day_plan_id: "demo-plan",
      title: "产品需求评审",
      item_type: "event",
      start_time: at(10, 0),
      end_time: at(11, 30),
      status: "planned",
      is_flexible: false,
      sort_order: 2,
    },
  ];

  return {
    plan: {
      id: "demo-plan",
      plan_date: planDate,
      summary: "先把高优先级事项稳住，再推进写论文与评审准备。",
      status: "confirmed",
      items: planItems,
    } as DayPlan,
    events,
    tasks,
    conflicts,
    reminders,
  };
}

function getPriorityColor(priority: string) {
  if (priority === "high") {
    return "red";
  }
  if (priority === "medium") {
    return "gold";
  }
  return "blue";
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

export default function TodayPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const planDate = useMemo(() => getTodayString(), []);
  const demoData = useMemo(() => buildDemoDashboardData(planDate), [planDate]);
  const [messageApi, contextHolder] = message.useMessage();
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const [data, setData] = useState<TodayDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentMessage, setAgentMessage] = useState("");
  const [agentSubmitting, setAgentSubmitting] = useState(false);
  const [agentMessages, setAgentMessages] = useState<ChatMessage[]>(() => [createWelcomeMessage()]);

  const fetchData = useCallback(async () => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看今日计划");
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
  }, [accessToken, planDate]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const viewData = data ?? demoData;

  const summary = useMemo(() => buildDashboardSummary(viewData), [viewData]);
  const combinedTimeline = useMemo(() => {
    const entries = [
      ...viewData.events.map((event) => ({ kind: "event" as const, ...event })),
      ...(viewData.plan?.items ?? []).map((item) => ({ kind: "plan_item" as const, ...item })),
    ];
    return sortTimelineEntries(entries);
  }, [viewData]);

  const monthDays = useMemo(() => buildMonthGrid(dayjs(planDate)), [planDate]);
  const selectedDate = dayjs(planDate);
  const selectedDateKey = selectedDate.format("YYYY-MM-DD");
  const monthEventMap = useMemo(() => {
    const map = new Map<string, CalendarEventItem[]>();
    viewData.events.forEach((event) => {
      const key = dayjs(event.start_time).format("YYYY-MM-DD");
      const next = map.get(key) ?? [];
      next.push(event);
      map.set(key, next);
    });
    return map;
  }, [viewData.events]);

  const progressPercent = useMemo(() => {
    const planItems = viewData.plan?.items ?? [];
    const total = planItems.length || 5;
    const completed = planItems.filter((item) => item.status === "completed").length || 2;
    return Math.min(100, Math.round((completed / total) * 100));
  }, [viewData.plan?.items]);

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

  return (
    <div className="today-page">
      {contextHolder}
      {error ? (
        <div className="today-page__notice">
          <Tag color="gold">示意数据</Tag>
          <Text className="muted-text">当前网络不可用，已切换为本地示意内容。</Text>
        </div>
      ) : null}
      {loading ? <TodayLoading /> : null}

      <Card className="section-card dashboard-hero today-hero" bordered={false}>
        <div className="today-hero__copy">
          <div className="today-hero__headline">
            <span className="hero-kicker">
              <FireOutlined />
              今日节奏 · 专注与平衡
            </span>
            <Title className="page-title today-hero__title">稳扎稳打，当日事当日毕。</Title>
            <Paragraph className="today-hero__lead">
              已完成 {Math.round((progressPercent / 100) * (viewData.plan?.items.length || 5))}/
              {viewData.plan?.items.length || 5} 项计划，保持节奏，继续推进。
            </Paragraph>
          </div>

          <div className="today-hero__progress">
            <Progress percent={progressPercent} showInfo={false} strokeWidth={12} />
            <Text className="muted-text">今天的重点不是做更多，而是把最重要的事情做稳。</Text>
          </div>
        </div>

        <div className="today-hero__art" />
      </Card>

      <div className="today-summary-grid">
        <Card className="section-card today-summary-card" bordered={false}>
          <div className="today-summary-card__icon">
            <CalendarOutlined />
          </div>
          <div>
            <div className="today-summary-card__label">今日日程</div>
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
            <CoffeeOutlined />
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

      <div className="today-grid">
        <div className="today-stack">
          <Card className="section-card" bordered={false}>
            <SectionHeader
              title="今日时间轴"
              extra={
                <Button icon={<ArrowRightOutlined />} type="text">
                  查看日历
                </Button>
              }
            />
            {combinedTimeline.length ? (
              <div className="today-timeline">
                {combinedTimeline.slice(0, 6).map((entry) => (
                  <div key={entry.id} className="today-timeline__item">
                    <Text className="today-timeline__time">{dayjs(entry.start_time).format("HH:mm")}</Text>
                    <span
                      className={[
                        "today-timeline__dot",
                        entry.kind === "plan_item" ? "today-timeline__dot--task" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    />
                    <Card className="section-card today-timeline__card" bordered={false}>
                      <Space direction="vertical" size={6} style={{ width: "100%" }}>
                        <Space wrap>
                          <Text strong>{entry.title}</Text>
                          <Tag color={entry.kind === "plan_item" ? "cyan" : "blue"}>
                            {entry.kind === "plan_item" ? entry.item_type : entry.status}
                          </Tag>
                        </Space>
                        <Text className="today-timeline__meta">
                          {formatRange(entry.start_time, entry.end_time)} ·{" "}
                          {entry.kind === "plan_item" ? "计划项" : "日程"}
                        </Text>
                        {entry.kind === "event" && entry.location ? (
                          <Text className="today-timeline__meta">{entry.location}</Text>
                        ) : null}
                      </Space>
                    </Card>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="今天还没有安排正式计划" />
            )}
          </Card>

          <Card className="section-card" bordered={false} title="任务概览">
            {viewData.tasks.length ? (
              <div className="today-timeline">
                {viewData.tasks.slice(0, 5).map((task) => (
                  <Card key={task.id} className="section-card today-timeline__card" bordered={false}>
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong>{task.title}</Text>
                        <Tag color={getPriorityColor(task.priority)}>{task.priority}</Tag>
                      </Space>
                      <Text className="today-timeline__meta">
                        {task.estimated_minutes ? `${task.estimated_minutes} 分钟` : "未设置时长"} · {task.status}
                      </Text>
                      {task.description ? <Text className="today-timeline__meta">{task.description}</Text> : null}
                    </Space>
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState title="任务池暂无任务" />
            )}
          </Card>

          <Card className="section-card" bordered={false} title={`冲突事项 (${viewData.conflicts.length})`}>
            {viewData.conflicts.length ? (
              <div className="today-timeline">
                {viewData.conflicts.slice(0, 3).map((conflict) => (
                  <Card key={conflict.id} className="section-card today-timeline__card" bordered={false}>
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong>{conflict.title}</Text>
                        <Tag color={getConflictColor(conflict.severity)}>{conflict.severity}</Tag>
                      </Space>
                      {conflict.description ? <Text className="today-timeline__meta">{conflict.description}</Text> : null}
                      {conflict.suggestion ? <Text className="today-timeline__meta">建议：{conflict.suggestion}</Text> : null}
                    </Space>
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState title="当前没有冲突事项" />
            )}
          </Card>
        </div>

        <div className="today-stack">
          <Card className="section-card" bordered={false}>
            <div className="today-mini-calendar">
              <div className="today-mini-calendar__header">
                <div>
                  <Title level={4} className="today-mini-calendar__title">
                    {selectedDate.format("YYYY年M月")}
                  </Title>
                  <Text className="muted-text">选中日期：{selectedDate.format("YYYY年M月D日")}</Text>
                </div>
                <Space>
                  <Button icon={<ArrowLeftOutlined />} />
                  <Button icon={<ArrowRightOutlined />} />
                </Space>
              </div>

              <div className="today-mini-calendar__grid">
                {["一", "二", "三", "四", "五", "六", "日"].map((weekday) => (
                  <div key={weekday} className="today-mini-calendar__weekday">
                    {weekday}
                  </div>
                ))}
                {monthDays.map((dayItem) => {
                  const key = dayItem.format("YYYY-MM-DD");
                  const isActive = key === selectedDateKey;
                  const isOutside = dayItem.month() !== selectedDate.month();
                  const eventCount = monthEventMap.get(key)?.length ?? 0;
                  const dots = Array.from({ length: Math.min(3, eventCount) }, (_, index) => index);

                  return (
                    <div
                      key={key}
                      className={[
                        "today-mini-calendar__day",
                        isActive ? "today-mini-calendar__day--active" : "",
                        isOutside ? "today-mini-calendar__day--outside" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      <span className="today-mini-calendar__day-number">{dayItem.date()}</span>
                      <div className="today-mini-calendar__dots">
                        {dots.map((dotIndex) => (
                          <span
                            key={dotIndex}
                            className={[
                              "today-mini-calendar__dot",
                              dotIndex === 0 ? "today-mini-calendar__dot--green" : "",
                              dotIndex === 1 ? "today-mini-calendar__dot--amber" : "",
                            ]
                              .filter(Boolean)
                              .join(" ")}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>

          <Card className="section-card" bordered={false} title="当日重点">
            {viewData.events.length ? (
              <div className="today-mini-calendar__list">
                {viewData.events.slice(0, 4).map((event) => (
                  <div key={event.id} className="today-mini-calendar__list-item">
                    <div>
                      <Text strong>{event.title}</Text>
                      <div className="today-timeline__meta">{formatRange(event.start_time, event.end_time)}</div>
                    </div>
                    <Tag color="blue">重点</Tag>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="今日重点为空" />
            )}
          </Card>

          <Card className="section-card" bordered={false}>
            <div className="today-assistant">
              <div className="today-assistant__status">
                <div>
                  <Title level={4} className="today-assistant__status-name">
                    智能助手
                  </Title>
                  <Space size={8} align="center">
                    <span className="today-assistant__status-indicator" />
                    <Text className="muted-text">在线</Text>
                  </Space>
                </div>
                <Space size={10}>
                  <Button icon={<ArrowLeftOutlined />} />
                  <Button icon={<ArrowRightOutlined />} />
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
            </div>
          </Card>

          <Card className="section-card" bordered={false} title="提醒任务">
            {viewData.reminders.length ? (
              <div className="today-timeline">
                {viewData.reminders.slice(0, 4).map((reminder) => (
                  <Card key={reminder.id} className="section-card today-timeline__card" bordered={false}>
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong>{reminder.title}</Text>
                        <Tag color={getReminderColor(reminder.status)}>{reminder.status}</Tag>
                      </Space>
                      <Text className="today-timeline__meta">{formatRange(reminder.trigger_time)}</Text>
                      <Text className="today-timeline__meta">
                        重试 {reminder.retry_count}/{reminder.max_retries}
                      </Text>
                    </Space>
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState title="当前没有提醒任务" />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
