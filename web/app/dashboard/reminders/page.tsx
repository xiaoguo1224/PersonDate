"use client";

import { BellOutlined } from "@ant-design/icons";
import { Alert, Card, Col, Empty, Row, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime, type ReminderItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type ReminderListResponse = {
  items: ReminderItem[];
};

function getStatusColor(status: string) {
  if (status === "fired") return "green";
  if (status === "failed") return "red";
  if (status === "cancelled") return "default";
  return "orange";
}

function RemindersLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" tip="正在加载提醒任务..." />
    </div>
  );
}

function RemindersError({ message }: Readonly<{ message: string }>) {
  return <Alert type="error" showIcon message="加载提醒任务失败" description={message} />;
}

function RemindersEmpty() {
  return (
    <div className="dashboard-empty">
      <Empty description="当前没有提醒任务" />
    </div>
  );
}

export default function RemindersPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看提醒任务");
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    requestJson<ReminderListResponse>("/api/reminders", {}, accessToken)
      .then((result) => {
        if (alive) {
          setReminders(result.items);
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

  const summary = useMemo(() => {
    const pending = reminders.filter((item) => item.status === "pending").length;
    const fired = reminders.filter((item) => item.status === "fired").length;
    const failed = reminders.filter((item) => item.status === "failed").length;
    return {
      total: reminders.length,
      pending,
      fired,
      failed,
    };
  }, [reminders]);

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <BellOutlined />
            提醒任务
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>提醒任务总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里已经接入后端提醒任务列表。后续可在此基础上补充取消提醒、失败重试和触发测试入口。
          </Paragraph>
          <Space wrap>
            <Tag color="orange">{summary.pending} 个待触发</Tag>
            <Tag color="green">{summary.fired} 个已触发</Tag>
            <Tag color="red">{summary.failed} 个失败</Tag>
            <Tag color="cyan">{summary.total} 条记录</Tag>
          </Space>
        </Space>
      </Card>

      {error ? <RemindersError message={error} /> : null}

      {loading ? (
        <RemindersLoading />
      ) : reminders.length ? (
        <Row gutter={[16, 16]}>
          {reminders.map((reminder) => (
            <Col xs={24} lg={12} key={reminder.id}>
              <Card className="section-card" bordered={false}>
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{reminder.title}</Text>
                    <Tag color={getStatusColor(reminder.status)}>{reminder.status}</Tag>
                    <Tag color="cyan">{reminder.target_type}</Tag>
                  </Space>
                  <Text className="muted-text">
                    触发时间：{formatDateTime(reminder.trigger_time, timezone)}
                  </Text>
                  <Text className="muted-text">会话：{reminder.conversation_id}</Text>
                  <Space wrap>
                    <Tag>重试 {reminder.retry_count}/{reminder.max_retries}</Tag>
                    <Tag>目标 {reminder.target_id}</Tag>
                  </Space>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <RemindersEmpty />
      )}
    </Space>
  );
}
