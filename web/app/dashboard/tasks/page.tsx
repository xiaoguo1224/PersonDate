"use client";

import { CheckCircleOutlined, ClockCircleOutlined, RocketOutlined } from "@ant-design/icons";
import { Alert, Card, Empty, List, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { formatDateTime, type TaskItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type TaskListResponse = {
  items: TaskItem[];
};

function getPriorityColor(priority: string) {
  if (priority === "high") return "red";
  if (priority === "medium") return "gold";
  return "blue";
}

function getStatusColor(status: string) {
  if (status === "completed") return "green";
  if (status === "deleted") return "default";
  if (status === "in_progress") return "cyan";
  return "orange";
}

function TasksLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" tip="正在加载任务池..." />
    </div>
  );
}

function TasksError({ message }: Readonly<{ message: string }>) {
  return <Alert type="error" showIcon message="加载任务池失败" description={message} />;
}

function TaskEmpty() {
  return (
    <div className="dashboard-empty">
      <Empty description="当前没有任务数据" />
    </div>
  );
}

export default function TasksPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看任务池");
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    requestJson<TaskListResponse>("/api/tasks", {}, accessToken)
      .then((result) => {
        if (alive) {
          setTasks(result.items);
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
    const activeTasks = tasks.filter((task) => task.status !== "completed" && task.status !== "deleted");
    const urgentTasks = tasks.filter((task) => task.priority === "high" && task.status !== "completed");
    const datedTasks = tasks.filter((task) => Boolean(task.deadline));
    return {
      total: tasks.length,
      active: activeTasks.length,
      urgent: urgentTasks.length,
      dated: datedTasks.length,
    };
  }, [tasks]);

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <RocketOutlined />
            任务池
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>任务池总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里已经接入后端任务列表。后续可以在此基础上加入创建、编辑、完成和自动排程入口。
          </Paragraph>
          <Space wrap>
            <Tag color="cyan">{summary.total} 个任务</Tag>
            <Tag color="orange">{summary.active} 个待处理</Tag>
            <Tag color="red">{summary.urgent} 个高优先级</Tag>
            <Tag color="blue">{summary.dated} 个已设截止时间</Tag>
          </Space>
        </Space>
      </Card>

      {error ? <TasksError message={error} /> : null}

      {loading ? (
        <TasksLoading />
      ) : tasks.length ? (
        <Card className="section-card" bordered={false} title="任务列表">
          <List
            itemLayout="vertical"
            dataSource={tasks}
            renderItem={(task) => (
              <List.Item key={task.id}>
                <Card size="small" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap>
                      <Text strong>{task.title}</Text>
                      <Tag color={getPriorityColor(task.priority)}>{task.priority}</Tag>
                      <Tag color={getStatusColor(task.status)}>{task.status}</Tag>
                    </Space>
                    {task.description ? <Text className="muted-text">{task.description}</Text> : null}
                    <Space wrap>
                      {task.estimated_minutes ? (
                        <Tag icon={<ClockCircleOutlined />}>{task.estimated_minutes} 分钟</Tag>
                      ) : null}
                      {task.deadline ? <Tag color="cyan">截止 {formatDateTime(task.deadline)}</Tag> : null}
                      {task.status !== "completed" ? <Tag icon={<CheckCircleOutlined />}>待完成</Tag> : null}
                    </Space>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        </Card>
      ) : (
        <TaskEmpty />
      )}
    </Space>
  );
}
