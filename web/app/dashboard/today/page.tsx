"use client";

import {
  Alert,
  Card,
  Col,
  Empty,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  buildDashboardSummary,
  formatRange,
  loadTodayDashboard,
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

export default function TodayPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const planDate = useMemo(() => getTodayString(), []);
  const [data, setData] = useState<TodayDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看今日计划");
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    loadTodayDashboard(accessToken, planDate)
      .then((result) => {
        if (alive) {
          setData(result);
        }
      })
      .catch((caughtError: unknown) => {
        if (alive) {
          setError(caughtError instanceof Error ? caughtError.message : "未知错误");
        }
      })
      .finally(() => {
        if (alive) {
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [accessToken, planDate]);

  const summary = useMemo(() => (data ? buildDashboardSummary(data) : null), [data]);

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
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
