"use client";

import { CheckCircleOutlined, ClockCircleOutlined, DeleteOutlined, EditOutlined, RocketOutlined, CalendarOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, List, Modal, Segmented, Space, Spin, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime, loadScheduledItems, type ScheduledItem, type TaskItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type TaskListResponse = {
  items: TaskItem[];
};

type TaskStatus = "all" | "pending" | "completed";

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

export default function TasksPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TaskStatus>("all");
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [scheduledSlots, setScheduledSlots] = useState<ScheduledItem[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsModalOpen, setSlotsModalOpen] = useState(false);

  const fetchTasks = (status?: string) => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看待办");
      return;
    }
    setLoading(true);
    setError(null);
    const query = status ? `?status=${status}` : "";
    requestJson<TaskListResponse>(`/api/tasks${query}`, {}, accessToken)
      .then((result) => {
        setTasks(result.items);
      })
      .catch((caughtError: unknown) => {
        setError(caughtError instanceof Error ? caughtError.message : "未知错误");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTasks(filter === "all" ? undefined : filter);
  }, [accessToken, filter]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleComplete = async (taskId: string) => {
    if (!accessToken) return;
    try {
      await requestJson(`/api/tasks/${taskId}/complete`, { method: "PATCH" }, accessToken);
      message.success("任务已完成");
      fetchTasks(filter === "all" ? undefined : filter);
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "操作失败");
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!accessToken) return;
    Modal.confirm({
      title: "确认删除",
      content: "确定要删除该任务吗？",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          await requestJson(`/api/tasks/${taskId}`, { method: "DELETE" }, accessToken);
          message.success("任务已删除");
          fetchTasks(filter === "all" ? undefined : filter);
        } catch (caughtError: unknown) {
          message.error(caughtError instanceof Error ? caughtError.message : "操作失败");
        }
      },
    });
  };

  const handleViewSchedule = async (task: TaskItem) => {
    setSelectedTask(task);
    setSlotsModalOpen(true);
    setSlotsLoading(true);
    try {
      const items = await loadScheduledItems({ keyword: task.title }, accessToken);
      const slots = items.filter((item) => item.source_task_id === task.id || item.title === task.title);
      setScheduledSlots(slots);
    } catch {
      setScheduledSlots([]);
    } finally {
      setSlotsLoading(false);
    }
  };

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

  const filterOptions = [
    { label: "全部", value: "all" as TaskStatus },
    { label: "待处理", value: "pending" as TaskStatus },
    { label: "已完成", value: "completed" as TaskStatus },
  ];

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <RocketOutlined />
            待办
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>待办总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            管理你的任务：查看、完成、删除，以及查看任务在日历中的排期。
          </Paragraph>
          <Space wrap>
            <Tag color="cyan">{summary.total} 个任务</Tag>
            <Tag color="orange">{summary.active} 个待处理</Tag>
            <Tag color="red">{summary.urgent} 个高优先级</Tag>
            <Tag color="blue">{summary.dated} 个已设截止时间</Tag>
          </Space>
        </Space>
      </Card>

      <Segmented<TaskStatus>
        options={filterOptions}
        value={filter}
        onChange={(value) => setFilter(value)}
      />

      {error ? (
        <Alert type="error" showIcon message="加载待办失败" description={error} />
      ) : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" tip="正在加载..." />
        </div>
      ) : tasks.length ? (
        <Card className="section-card" bordered={false} title={filter === "completed" ? "已完成任务" : "任务列表"}>
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
                      {task.deadline ? <Tag color="cyan">截止 {formatDateTime(task.deadline, timezone)}</Tag> : null}
                      <Button
                        type="link"
                        size="small"
                        icon={<CalendarOutlined />}
                        onClick={() => void handleViewSchedule(task)}
                      >
                        查看排期
                      </Button>
                    </Space>
                    <Space>
                      {task.status !== "completed" && task.status !== "deleted" ? (
                        <Button
                          type="primary"
                          size="small"
                          icon={<CheckCircleOutlined />}
                          onClick={() => void handleComplete(task.id)}
                        >
                          完成
                        </Button>
                      ) : null}
                      {task.status !== "deleted" ? (
                        <Button
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => void handleDelete(task.id)}
                        >
                          删除
                        </Button>
                      ) : null}
                    </Space>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        </Card>
      ) : (
        <div className="dashboard-empty">
          <Empty description="当前没有任务数据" />
        </div>
      )}

      <Modal
        title={selectedTask ? `排期 - ${selectedTask.title}` : "排期"}
        open={slotsModalOpen}
        onCancel={() => setSlotsModalOpen(false)}
        footer={null}
        width={600}
      >
        {slotsLoading ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin />
          </div>
        ) : scheduledSlots.length ? (
          <List
            dataSource={scheduledSlots}
            renderItem={(slot) => (
              <List.Item>
                <Space>
                  <CalendarOutlined />
                  <Text>
                    {formatDateTime(slot.start_time, timezone)}
                    {slot.end_time ? ` - ${formatDateTime(slot.end_time, timezone)}` : ""}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无该任务的排期" />
        )}
      </Modal>
    </Space>
  );
}
