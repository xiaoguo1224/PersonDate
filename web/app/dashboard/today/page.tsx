"use client";

import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Timeline,
  Typography,
  message,
} from "antd";
import { RobotOutlined, SendOutlined, UserOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  buildDashboardSummary,
  formatRange,
  loadTodayDashboard,
  sendAgentMessage,
  type TodayDashboardData,
} from "@/lib/dashboard";

const { Title, Paragraph, Text } = Typography;

function getTodayString() {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function DashboardLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" tip="正在加载今日数据..." />
    </div>
  );
}

function DashboardError({ message }: Readonly<{ message: string }>) {
  return (
    <Alert
      type="error"
      showIcon
      message="加载今日面板失败"
      description={message}
    />
  );
}

function EmptyState({ title }: Readonly<{ title: string }>) {
  return (
    <div className="dashboard-empty">
      <Empty description={title} />
    </div>
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

export default function TodayPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const planDate = useMemo(() => getTodayString(), []);
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

  const summary = useMemo(() => (data ? buildDashboardSummary(data) : null), [data]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [agentMessages, agentSubmitting]);

  const resetChat = useCallback(() => {
    setAgentMessages([createWelcomeMessage()]);
    setAgentMessage("");
  }, []);

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
    setAgentMessages((prev) => [...prev, userMessage, { id: createChatId(), role: "assistant", content: "正在思考...", pending: true, timestamp: getChatTimeLabel() }]);
    try {
      const result = await sendAgentMessage(accessToken, content);
      setAgentMessages((prev) => {
        const next = prev.filter((messageItem) => !messageItem.pending);
        next.push({
          id: createChatId(),
          role: "assistant",
          content: result.final_response || "Agent 已处理",
          meta: [
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

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      {contextHolder}
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">今日计划</span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>今天的节奏</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里已经开始读取后端真实数据。你可以看到今日计划、日程、任务、冲突和提醒的汇总。
          </Paragraph>
          <Tag color="cyan" style={{ width: "fit-content" }}>
            {planDate}
          </Tag>
        </Space>
      </Card>

      {error ? <DashboardError message={error} /> : null}

      {loading ? (
        <DashboardLoading />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24}>
              <Card
                className="section-card dashboard-chat"
                bordered={false}
                title="Agent 对话"
                extra={<Tag color="cyan">聊天回复</Tag>}
              >
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
                          <div className="agent-chat-avatar">
                            {isUser ? <UserOutlined /> : <RobotOutlined />}
                          </div>
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
                            {messageItem.meta ? (
                              <Text className="agent-chat-bubble__meta">{messageItem.meta}</Text>
                            ) : null}
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
                      placeholder="例如：明天下午 3 点开会，提醒我提前 10 分钟；或者 明天写论文 2 小时，帮我安排一下"
                    />
                    <Space wrap className="agent-chat-actions">
                      <Button
                        type="primary"
                        icon={<SendOutlined />}
                        loading={agentSubmitting}
                        onClick={() => void handleAgentSubmit()}
                      >
                        发送给 Agent
                      </Button>
                      <Button onClick={resetChat}>清空聊天</Button>
                    </Space>
                  </div>
                </div>
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}>
              <Card className="section-card" bordered={false}>
                <Statistic title="今日日程" value={summary?.eventsCount ?? 0} />
              </Card>
            </Col>
            <Col xs={24} md={6}>
              <Card className="section-card" bordered={false}>
                <Statistic title="待办任务" value={summary?.tasksCount ?? 0} />
              </Card>
            </Col>
            <Col xs={24} md={6}>
              <Card className="section-card" bordered={false}>
                <Statistic title="开放冲突" value={summary?.conflictsCount ?? 0} valueStyle={{ color: "var(--danger)" }} />
              </Card>
            </Col>
            <Col xs={24} md={6}>
              <Card className="section-card" bordered={false}>
                <Statistic title="待触发提醒" value={summary?.remindersCount ?? 0} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={16}>
              <Card className="section-card" bordered={false} title="今日时间轴">
                {data?.plan?.items?.length ? (
                  <Timeline
                    items={data.plan.items.map((item) => ({
                      color: item.item_type === "event" ? "cyan" : item.status === "completed" ? "green" : "gold",
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
                  <EmptyState title="今天还没有生成正式计划" />
                )}
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card className="section-card" bordered={false} title="Agent 建议">
                {data?.conflicts?.length ? (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    {data.conflicts.slice(0, 3).map((conflict) => (
                      <Alert
                        key={conflict.id}
                        type={conflict.severity === "high" ? "error" : "warning"}
                        showIcon
                        message={conflict.title}
                        description={conflict.suggestion || conflict.description || "请尽快处理该冲突"}
                      />
                    ))}
                  </Space>
                ) : (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Tag color="cyan">优先处理优先级高的任务</Tag>
                    <Tag color="gold">如果有草案，先确认再推进</Tag>
                    <Tag color="blue">提醒任务会在 APScheduler 中执行</Tag>
                  </Space>
                )}
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card className="section-card" bordered={false} title="今日日程">
                {data?.events.length ? (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    {data.events.slice(0, 5).map((event) => (
                      <Card key={event.id} size="small" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Text strong>{event.title}</Text>
                          <Text className="muted-text">
                            {formatRange(event.start_time, event.end_time)} · {event.status}
                          </Text>
                        </Space>
                      </Card>
                    ))}
                  </Space>
                ) : (
                  <EmptyState title="今天没有安排日程" />
                )}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card className="section-card" bordered={false} title="待办任务">
                {data?.tasks.length ? (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    {data.tasks.slice(0, 5).map((task) => (
                      <Card key={task.id} size="small" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{task.title}</Text>
                            <Tag color={task.priority === "high" ? "red" : task.priority === "medium" ? "gold" : "blue"}>
                              {task.priority}
                            </Tag>
                          </Space>
                          <Text className="muted-text">
                            {task.estimated_minutes ? `${task.estimated_minutes} 分钟` : "未设置时长"} · {task.status}
                          </Text>
                        </Space>
                      </Card>
                    ))}
                  </Space>
                ) : (
                  <EmptyState title="任务池暂无任务" />
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Space>
  );
}
