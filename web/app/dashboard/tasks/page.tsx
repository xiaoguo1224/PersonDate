"use client";

import { CheckCircleOutlined, ClockCircleOutlined, DeleteOutlined, EditOutlined, RocketOutlined, CalendarOutlined, PlusOutlined } from "@ant-design/icons";
import { App, Alert, Button, Card, DatePicker, Empty, Form, Input, InputNumber, List, Modal, Pagination, Select, Segmented, Space, Spin, Tag, TimePicker, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime, loadTaskScheduledItems, type ScheduledItem, type TaskItem, type TaskListResponse } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

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

function formatDateLabel(value: string | null | undefined): string {
  if (!value) return "";
  return value;
}

function getScheduleLabel(task: TaskItem): string {
  const parts: string[] = [];
  if (task.schedule_type) {
    const typeMap: Record<string, string> = {
      daily: "每天",
      weekdays: "工作日",
      duration_days: `持续${task.duration_days ?? "?"}天`,
      custom_range: `${formatDateLabel(task.start_date)} 至 ${formatDateLabel(task.end_date)}`,
    };
    parts.push(typeMap[task.schedule_type] || task.schedule_type);
  }
  if (task.time_type === "fixed" && task.scheduled_time) {
    parts.push(`固定 ${task.scheduled_time}${task.scheduled_end_time ? `-${task.scheduled_end_time}` : ""}`);
  } else if (task.time_type === "flexible" && task.estimated_minutes) {
    parts.push(`弹性 ${task.estimated_minutes}分钟`);
  }
  return parts.join(" | ");
}

export default function TasksPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const { modal, message } = App.useApp();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TaskStatus>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [scheduledSlots, setScheduledSlots] = useState<ScheduledItem[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsModalOpen, setSlotsModalOpen] = useState(false);
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formLoading, setFormLoading] = useState(false);
  const [form] = Form.useForm();

  const fetchTasks = (status?: string, p?: number, ps?: number) => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看待办");
      return;
    }
    setLoading(true);
    setError(null);
    const currentPage = p ?? page;
    const currentPageSize = ps ?? pageSize;
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("page", String(currentPage));
    params.set("page_size", String(currentPageSize));
    requestJson<TaskListResponse>(`/api/tasks?${params}`, {}, accessToken)
      .then((result) => {
        setTasks(result.items);
        setTotal(result.total);
      })
      .catch((caughtError: unknown) => {
        setError(caughtError instanceof Error ? caughtError.message : "未知错误");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    setPage(1);
    fetchTasks(filter === "all" ? undefined : filter, 1);
  }, [accessToken, filter]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleComplete = async (taskId: string) => {
    if (!accessToken) return;
    try {
      await requestJson(`/api/tasks/${taskId}/complete`, { method: "PATCH" }, accessToken);
      message.success("任务已完成");
      fetchTasks(filter === "all" ? undefined : filter, page);
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "操作失败");
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!accessToken) return;
    modal.confirm({
      title: "确认删除",
      content: "确定要删除该任务吗？",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          await requestJson(`/api/tasks/${taskId}`, { method: "DELETE" }, accessToken);
          message.success("任务已删除");
          fetchTasks(filter === "all" ? undefined : filter, page);
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
      const items = await loadTaskScheduledItems(task.id, accessToken);
      setScheduledSlots(items);
    } catch {
      setScheduledSlots([]);
    } finally {
      setSlotsLoading(false);
    }
  };

  const openCreateForm = () => {
    setFormMode("create");
    form.resetFields();
    setFormModalOpen(true);
  };

  const openEditForm = (task: TaskItem) => {
    setFormMode("edit");
    setSelectedTask(task);
    form.setFieldsValue({
      title: task.title,
      description: task.description,
      estimated_minutes: task.estimated_minutes,
      deadline: task.deadline ? new Date(task.deadline) : undefined,
      priority: task.priority,
      schedule_type: task.schedule_type,
      start_date: task.start_date ? new Date(task.start_date) : undefined,
      end_date: task.end_date ? new Date(task.end_date) : undefined,
      duration_days: task.duration_days,
      time_type: task.time_type,
      scheduled_time: task.scheduled_time ? new Date(`2000-01-01T${task.scheduled_time}`) : undefined,
      scheduled_end_time: task.scheduled_end_time ? new Date(`2000-01-01T${task.scheduled_end_time}`) : undefined,
    });
    setFormModalOpen(true);
  };

  const handleFormSubmit = async () => {
    try {
      const values = await form.validateFields();
      setFormLoading(true);

      const payload = {
        title: values.title,
        description: values.description,
        estimated_minutes: values.estimated_minutes,
        deadline: values.deadline?.toISOString(),
        priority: values.priority || "medium",
        schedule_type: values.schedule_type,
        start_date: values.start_date?.format("YYYY-MM-DD"),
        end_date: values.end_date?.format("YYYY-MM-DD"),
        duration_days: values.duration_days,
        time_type: values.time_type,
        scheduled_time: values.scheduled_time?.format("HH:mm"),
        scheduled_end_time: values.scheduled_end_time?.format("HH:mm"),
      };

      if (formMode === "create") {
        await requestJson("/api/tasks", {
          method: "POST",
          body: JSON.stringify(payload),
        }, accessToken);
        message.success("任务已创建");
      } else if (selectedTask) {
        await requestJson(`/api/tasks/${selectedTask.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        }, accessToken);
        message.success("任务已更新");
      }

      setFormModalOpen(false);
      fetchTasks(filter === "all" ? undefined : filter, page);
    } catch (caughtError: unknown) {
      if (caughtError instanceof Error && !("errorFields" in (caughtError as { errorFields?: unknown }))) {
        message.error(caughtError instanceof Error ? caughtError.message : "操作失败");
      }
    } finally {
      setFormLoading(false);
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="hero-kicker">
              <RocketOutlined />
              待办
            </span>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateForm}>
              新建任务
            </Button>
          </div>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>待办总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            管理你的任务：创建、编辑、完成、删除，以及查看任务在日历中的排期。
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
            pagination={false}
            renderItem={(task: TaskItem) => (
              <List.Item key={task.id}>
                <Card size="small" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap>
                      <Text strong>{task.title}</Text>
                      <Tag color={getPriorityColor(task.priority)}>{task.priority}</Tag>
                      <Tag color={getStatusColor(task.status)}>{task.status}</Tag>
                      {task.completed_days && task.completed_days > 0 ? (
                        <Tag color="purple">{task.completed_days}天已完成</Tag>
                      ) : null}
                    </Space>
                    {task.description ? <Text className="muted-text">{task.description}</Text> : null}
                    {getScheduleLabel(task) ? (
                      <Tag icon={<CalendarOutlined />}>{getScheduleLabel(task)}</Tag>
                    ) : null}
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
                        <>
                          <Button
                            type="primary"
                            size="small"
                            icon={<CheckCircleOutlined />}
                            onClick={() => void handleComplete(task.id)}
                          >
                            完成
                          </Button>
                          <Button
                            size="small"
                            icon={<EditOutlined />}
                            onClick={() => openEditForm(task)}
                          >
                            编辑
                          </Button>
                        </>
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
          {total > pageSize && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                showSizeChanger
                showTotal={(t) => `共 ${t} 条`}
                onChange={(p, ps) => {
                  setPage(p);
                  setPageSize(ps);
                  fetchTasks(filter === "all" ? undefined : filter, p, ps);
                }}
              />
            </div>
          )}
        </Card>
      ) : (
        <div className="dashboard-empty">
          <Empty description="当前没有任务数据" />
        </div>
      )}

      {/* 排期查看弹窗 */}
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
            renderItem={(slot: ScheduledItem) => (
              <List.Item>
                <Space>
                  <CalendarOutlined />
                  <Text>
                    {formatDateTime(slot.start_time, timezone)}
                    {slot.end_time ? ` - ${formatDateTime(slot.end_time, timezone)}` : ""}
                  </Text>
                  <Tag>{slot.status}</Tag>
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无该任务的排期" />
        )}
      </Modal>

      {/* 创建/编辑表单弹窗 */}
      <Modal
        title={formMode === "create" ? "新建任务" : "编辑任务"}
        open={formModalOpen}
        onOk={handleFormSubmit}
        onCancel={() => setFormModalOpen(false)}
        confirmLoading={formLoading}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: "请输入任务标题" }]}>
            <Input placeholder="任务标题" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue="medium">
            <Select options={[
              { label: "低", value: "low" },
              { label: "中", value: "medium" },
              { label: "高", value: "high" },
            ]} />
          </Form.Item>
          <Form.Item name="estimated_minutes" label="预估时长（分钟）">
            <InputNumber min={1} max={1440} style={{ width: "100%" }} addonAfter="分钟" />
          </Form.Item>
          <Form.Item name="deadline" label="截止日期">
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>

          <Card size="small" title="日期范围" style={{ marginBottom: 12, background: "transparent" }}>
            <Form.Item name="schedule_type" label="重复类型">
              <Select options={[
                { label: "无重复", value: null },
                { label: "每天", value: "daily" },
                { label: "工作日", value: "weekdays" },
                { label: "持续N天", value: "duration_days" },
                { label: "自定义区间", value: "custom_range" },
              ]} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.schedule_type !== curr.schedule_type}>
              {() => {
                const st = form.getFieldValue("schedule_type");
                return (
                  <>
                    {(st === "daily" || st === "weekdays") && (
                      <>
                        <Form.Item name="start_date" label="开始日期">
                          <DatePicker style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="end_date" label="截止日期">
                          <DatePicker style={{ width: "100%" }} />
                        </Form.Item>
                      </>
                    )}
                    {st === "duration_days" && (
                      <>
                        <Form.Item name="start_date" label="开始日期">
                          <DatePicker style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="duration_days" label="持续天数">
                          <InputNumber min={1} style={{ width: "100%" }} />
                        </Form.Item>
                      </>
                    )}
                    {st === "custom_range" && (
                      <>
                        <Form.Item name="start_date" label="开始日期">
                          <DatePicker style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="end_date" label="结束日期">
                          <DatePicker style={{ width: "100%" }} />
                        </Form.Item>
                      </>
                    )}
                  </>
                );
              }}
            </Form.Item>
          </Card>

          <Card size="small" title="时间设置" style={{ background: "transparent" }}>
            <Form.Item name="time_type" label="时间模式">
              <Select options={[
                { label: "无", value: null },
                { label: "固定时间", value: "fixed" },
                { label: "弹性时间", value: "flexible" },
              ]} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.time_type !== curr.time_type}>
              {() => {
                const tt = form.getFieldValue("time_type");
                return (
                  <>
                    {tt === "fixed" && (
                      <>
                        <Form.Item name="scheduled_time" label="开始时间">
                          <TimePicker format="HH:mm" style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="scheduled_end_time" label="结束时间">
                          <TimePicker format="HH:mm" style={{ width: "100%" }} />
                        </Form.Item>
                      </>
                    )}
                    {tt === "flexible" && (
                      <Text className="muted-text" style={{ fontSize: 12 }}>
                        弹性时间将根据上方的「预估时长」自动排到空闲时段
                      </Text>
                    )}
                  </>
                );
              }}
            </Form.Item>
          </Card>
        </Form>
      </Modal>
    </Space>
  );
}
