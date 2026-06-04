"use client";

import { CalendarOutlined } from "@ant-design/icons";
import { Alert, Card, Empty, List, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { formatRange, type CalendarEventItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type CalendarEventsResponse = {
  items: CalendarEventItem[];
};

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

export default function CalendarPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const [events, setEvents] = useState<CalendarEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看日历");
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    requestJson<CalendarEventsResponse>("/api/calendar-events", {}, accessToken)
      .then((result) => {
        if (alive) {
          setEvents(result.items);
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
  }, [accessToken]);

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <CalendarOutlined />
            日历视图
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>日程总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里已经接入后端的 calendar_events 列表。后续会在此基础上补月/周/日视图和编辑操作。
          </Paragraph>
          <Tag color="cyan" style={{ width: "fit-content" }}>
            {events.length} 条日程
          </Tag>
        </Space>
      </Card>

      {error ? <CalendarError message={error} /> : null}

      {loading ? (
        <CalendarLoading />
      ) : events.length ? (
        <Card className="section-card" bordered={false} title="全部日程">
          <List
            itemLayout="vertical"
            dataSource={events}
            renderItem={(event) => (
              <List.Item key={event.id}>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{event.title}</Text>
                    <Tag color={event.status === "deleted" ? "default" : "cyan"}>{event.status}</Tag>
                    {event.location ? <Tag>{event.location}</Tag> : null}
                  </Space>
                  <Text className="muted-text">{formatRange(event.start_time, event.end_time)}</Text>
                  {event.description ? <Text className="muted-text">{event.description}</Text> : null}
                </Space>
              </List.Item>
            )}
          />
        </Card>
      ) : (
        <div className="dashboard-empty">
          <Empty description="当前没有日程数据" />
        </div>
      )}
    </Space>
  );
}
