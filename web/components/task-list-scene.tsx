"use client";

import { CalendarOutlined, CheckCircleOutlined, ClockCircleOutlined, DeleteOutlined, EditOutlined, SearchOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Input, List, Segmented, Space, Spin, Tag, Typography } from "antd";

import { ResponsiveFilterRail } from "@/components/responsive-filter-rail";
import { ResponsiveListCard } from "@/components/responsive-list-card";
import { ResponsiveListViewport } from "@/components/responsive-list-viewport";
import { formatDateTime, type TaskItem } from "@/lib/dashboard";

const { Text } = Typography;

export type TaskStatus = "all" | "pending" | "completed";

function getPriorityColor(priority: string) {
  if (priority === "high") return "red";
  if (priority === "medium") return "gold";
  return "blue";
}

function getPriorityLabel(priority: string) {
  if (priority === "high") return "高优先级";
  if (priority === "medium") return "中优先级";
  return "低优先级";
}

function getStatusLabel(status: string) {
  if (status === "completed") return "已完成";
  if (status === "deleted") return "已删除";
  if (status === "in_progress") return "进行中";
  return "待处理";
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

function TaskListCard({
  task,
  compact,
  timezone,
  onComplete,
  onViewSchedule,
  onEdit,
  onDelete,
}: Readonly<{
  task: TaskItem;
  compact: boolean;
  timezone: string;
  onComplete: (taskId: string) => void;
  onViewSchedule: (task: TaskItem) => void;
  onEdit: (task: TaskItem) => void;
  onDelete: (taskId: string) => void;
}>) {
  const isActive = task.status !== "completed" && task.status !== "deleted";
  const scheduleLabel = getScheduleLabel(task);
  const actions: React.ReactNode[] = [];

  if (isActive) {
    actions.push(
      <Button key="complete" type="primary" icon={<CheckCircleOutlined />} onClick={() => void onComplete(task.id)}>
        完成
      </Button>,
    );
  }

  actions.push(
    <Button key="schedule" type={isActive ? "default" : "primary"} icon={<CalendarOutlined />} onClick={() => void onViewSchedule(task)}>
      查看排期
    </Button>,
  );

  if (isActive) {
    actions.push(
      <Button key="edit" icon={<EditOutlined />} onClick={() => onEdit(task)}>
        编辑
      </Button>,
    );
  }

  if (task.status !== "deleted") {
    actions.push(
      <Button key="delete" danger icon={<DeleteOutlined />} onClick={() => void onDelete(task.id)}>
        删除
      </Button>,
    );
  }

  return (
    <ResponsiveListCard
      accent={getPriorityColor(task.priority)}
      title={task.title}
      meta={scheduleLabel || "暂无排期"}
      tags={[
        getPriorityLabel(task.priority),
        getStatusLabel(task.status),
        task.completed_days && task.completed_days > 0 ? `${task.completed_days}天已完成` : null,
      ].filter(Boolean) as React.ReactNode[]}
      description={task.description ? <Text className="muted-text responsive-list-card__description-text">{task.description}</Text> : null}
      details={
        <Space direction="vertical" size={compact ? 6 : 8} style={{ width: "100%" }}>
          <Space wrap size={6}>
            {task.estimated_minutes ? <Tag icon={<ClockCircleOutlined />}>{task.estimated_minutes} 分钟</Tag> : null}
            {task.deadline ? <Tag color="cyan">截止 {formatDateTime(task.deadline, timezone)}</Tag> : null}
          </Space>
        </Space>
      }
      actions={actions}
      compact={compact}
    />
  );
}

export function TaskListScene({
  tasks,
  loading,
  error,
  filter,
  filterOptions,
  onFilterChange,
  onSearch,
  timezone,
  onComplete,
  onViewSchedule,
  onEdit,
  onDelete,
}: Readonly<{
  tasks: TaskItem[];
  loading: boolean;
  error: string | null;
  filter: TaskStatus;
  filterOptions: { label: string; value: TaskStatus }[];
  onFilterChange: (value: TaskStatus) => void;
  onSearch: (value: string) => void;
  timezone: string;
  onComplete: (taskId: string) => void;
  onViewSchedule: (task: TaskItem) => void;
  onEdit: (task: TaskItem) => void;
  onDelete: (taskId: string) => void;
}>) {
  const renderDesktop = () => (
    <>
      <ResponsiveFilterRail>
        <Segmented<TaskStatus> options={filterOptions} value={filter} onChange={(value) => onFilterChange(value)} />
        <Input.Search
          placeholder="搜索任务标题或描述"
          allowClear
          enterButton={<SearchOutlined />}
          style={{ width: 300 }}
          onSearch={(value) => onSearch(value)}
        />
      </ResponsiveFilterRail>

      {error ? <Alert type="error" showIcon message="加载待办失败" description={error} /> : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" />
        </div>
      ) : tasks.length ? (
        <List
          itemLayout="vertical"
          dataSource={tasks}
          pagination={false}
          renderItem={(task: TaskItem) => (
            <List.Item key={task.id}>
              <TaskListCard
                task={task}
                compact={false}
                timezone={timezone}
                onComplete={onComplete}
                onViewSchedule={onViewSchedule}
                onEdit={onEdit}
                onDelete={onDelete}
              />
            </List.Item>
          )}
        />
      ) : (
        <div className="dashboard-empty">
          <Empty description="当前没有任务数据" />
        </div>
      )}
    </>
  );

  const renderMobile = () => (
    <>
      <ResponsiveFilterRail compact>
        <Segmented<TaskStatus> options={filterOptions} value={filter} onChange={(value) => onFilterChange(value)} />
        <Input.Search
          placeholder="搜索任务标题或描述"
          allowClear
          enterButton={<SearchOutlined />}
          style={{ width: 300 }}
          onSearch={(value) => onSearch(value)}
        />
      </ResponsiveFilterRail>

      {error ? <Alert type="error" showIcon message="加载待办失败" description={error} /> : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" />
        </div>
      ) : tasks.length ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {tasks.map((task) => (
            <TaskListCard
              key={task.id}
              task={task}
              compact
              timezone={timezone}
              onComplete={onComplete}
              onViewSchedule={onViewSchedule}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          ))}
        </Space>
      ) : (
        <div className="dashboard-empty">
          <Empty description="当前没有任务数据" />
        </div>
      )}
    </>
  );

  return <ResponsiveListViewport desktop={renderDesktop()} mobile={renderMobile()} tablet={renderDesktop()} />;
}
