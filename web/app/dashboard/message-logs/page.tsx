"use client";

import { EyeOutlined, ReloadOutlined, SwapOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Descriptions, Empty, Form, Grid, Input, Modal, Select, Space, Spin, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { ResponsiveFilterRail } from "@/components/responsive-filter-rail";
import { ResponsiveListCard } from "@/components/responsive-list-card";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type { ChannelMessageLogItem, ChannelMessageLogListResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

type MessageLogFilters = {
  conversation_id?: string;
  direction?: string;
};

function getDirectionColor(direction: string) {
  return direction === "inbound" ? "blue" : "gold";
}

function getStatusColor(status: string) {
  if (status === "sent" || status === "received") return "green";
  if (status === "failed") return "red";
  return "default";
}

export default function MessageLogsPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const screens = Grid.useBreakpoint();
  const isMobile = screens.md === false;
  const isOwner = session?.role === "owner";
  const [form] = Form.useForm<MessageLogFilters>();
  const [items, setItems] = useState<ChannelMessageLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<ChannelMessageLogItem | null>(null);
  const [query, setQuery] = useState<MessageLogFilters>({});

  const loadLogs = useCallback(
    async (filters: MessageLogFilters = {}) => {
      if (!accessToken) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const searchParams = new URLSearchParams();
        if (filters.conversation_id) {
          searchParams.set("conversation_id", filters.conversation_id);
        }
        if (filters.direction && filters.direction !== "all") {
          searchParams.set("direction", filters.direction);
        }
        const path = searchParams.toString()
          ? `/admin/message-logs?${searchParams.toString()}`
          : "/admin/message-logs";
        const result = await requestJson<ChannelMessageLogListResponse>(path, {}, accessToken);
        setItems(result.items);
      } catch (caughtError: unknown) {
        setError(caughtError instanceof Error ? caughtError.message : "加载失败");
      } finally {
        setLoading(false);
      }
    },
    [accessToken],
  );

  useEffect(() => {
    if (isOwner) {
      void loadLogs(query);
    } else {
      setLoading(false);
    }
  }, [isOwner, loadLogs, query]);

  const handleSearch = (values: MessageLogFilters) => {
    const nextQuery = {
      conversation_id: values.conversation_id?.trim() || undefined,
      direction: values.direction || undefined,
    };
    setQuery(nextQuery);
  };

  const handleReset = () => {
    form.resetFields();
    setQuery({});
  };

  const columns = [
    {
      title: "时间",
      dataIndex: "created_at",
      width: 180,
      render: (value: string) => formatDateTime(value, timezone),
    },
    {
      title: "方向",
      dataIndex: "direction",
      width: 100,
      render: (value: string) => <Tag color={getDirectionColor(value)}>{value}</Tag>,
    },
    {
      title: "会话",
      dataIndex: "conversation_id",
      width: 170,
      ellipsis: true,
    },
    {
      title: "内容",
      dataIndex: "content",
      ellipsis: true,
      render: (value: string | null) => <Text>{value || "-"}</Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 120,
      render: (value: string) => <Tag color={getStatusColor(value)}>{value}</Tag>,
    },
    {
      title: "操作",
      width: 110,
      render: (_: unknown, record: ChannelMessageLogItem) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => setSelectedItem(record)}>
          详情
        </Button>
      ),
    },
  ];

  const mobileCards = (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {items.map((item) => (
        <ResponsiveListCard
          key={item.id}
          compact
          accent={item.direction === "inbound" ? "#3b82f6" : "#f59e0b"}
          title={`${item.direction === "inbound" ? "入站" : "出站"} · ${item.status}`}
          meta={`${formatDateTime(item.created_at, timezone)} · ${item.conversation_id}`}
          tags={[
            item.content_type,
            item.status,
          ]}
          description={
            <Typography.Paragraph className="muted-text responsive-list-card__description-text" ellipsis={{ rows: 2, expandable: false }}>
              {item.content || "暂无内容"}
            </Typography.Paragraph>
          }
          details={
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              {item.error_message ? (
                <Text type="danger" className="muted-text responsive-list-card__description-text">
                  错误：{item.error_message}
                </Text>
              ) : null}
              <Text className="muted-text responsive-list-card__description-text">
                重试：{item.retry_count}
              </Text>
            </Space>
          }
          actions={[
            <Button key="detail" size="middle" icon={<EyeOutlined />} onClick={() => setSelectedItem(item)}>
              详情
            </Button>,
          ]}
        />
      ))}
    </Space>
  );

  if (!isOwner) {
    return <Alert type="error" showIcon message="无权限访问" description="全局消息日志仅 owner 可访问。" />;
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" variant="borderless">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <SwapOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>全局消息日志</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里展示微信入站与出站消息的完整日志，方便按会话排查消息链路与通道异常。
          </Paragraph>
          <Button icon={<ReloadOutlined />} onClick={() => void loadLogs()} loading={loading} style={{ width: "fit-content" }}>
            刷新日志
          </Button>
        </Space>
      </Card>

      <Card className="section-card" variant="borderless">
        <Form form={form} layout={isMobile ? "vertical" : "inline"} onFinish={handleSearch}>
          <ResponsiveFilterRail compact={isMobile}>
            <Form.Item name="conversation_id" label="会话 ID" style={{ flex: isMobile ? "1 1 100%" : undefined }}>
              <Input placeholder="输入 conversation_id" allowClear style={{ width: isMobile ? "100%" : 240 }} />
            </Form.Item>
            <Form.Item name="direction" label="方向" initialValue="all" style={{ flex: isMobile ? "1 1 100%" : undefined }}>
              <Select
                style={{ width: isMobile ? "100%" : 150 }}
                options={[
                  { value: "all", label: "全部" },
                  { value: "inbound", label: "入站" },
                  { value: "outbound", label: "出站" },
                ]}
              />
            </Form.Item>
            <Form.Item style={{ flex: isMobile ? "1 1 100%" : undefined }}>
              <Space direction={isMobile ? "vertical" : "horizontal"} style={{ width: isMobile ? "100%" : "auto" }}>
                <Button type="primary" htmlType="submit" block={isMobile}>
                  查询
                </Button>
                <Button onClick={() => void handleReset()} block={isMobile}>
                  重置
                </Button>
              </Space>
            </Form.Item>
          </ResponsiveFilterRail>
        </Form>
      </Card>

      {error ? <Alert type="error" showIcon message="加载消息日志失败" description={error} /> : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" />
        </div>
      ) : (
        <Card className="section-card" variant="borderless">
          {isMobile ? (
            items.length ? mobileCards : <div className="dashboard-empty"><Empty description="暂无消息日志" /></div>
          ) : (
            <Table
              rowKey="id"
              dataSource={items}
              columns={columns}
              pagination={{ pageSize: 10, showSizeChanger: false }}
              scroll={{ x: 1000 }}
              locale={{ emptyText: "暂无消息日志" }}
            />
          )}
        </Card>
      )}

      <Modal
        open={selectedItem !== null}
        onCancel={() => setSelectedItem(null)}
        footer={null}
        title="消息日志详情"
        width={900}
      >
        {selectedItem ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="时间">{formatDateTime(selectedItem.created_at, timezone)}</Descriptions.Item>
              <Descriptions.Item label="方向">
                <Tag color={getDirectionColor(selectedItem.direction)}>{selectedItem.direction}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="会话 ID">{selectedItem.conversation_id}</Descriptions.Item>
              <Descriptions.Item label="用户 ID">{selectedItem.user_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="通道账号">{selectedItem.account_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="message_id">{selectedItem.message_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="context_token">{selectedItem.context_token || "-"}</Descriptions.Item>
              <Descriptions.Item label="retry_count">{selectedItem.retry_count}</Descriptions.Item>
              <Descriptions.Item label="error_code">{selectedItem.error_code || "-"}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={getStatusColor(selectedItem.status)}>{selectedItem.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="错误信息">{selectedItem.error_message || "-"}</Descriptions.Item>
              <Descriptions.Item label="内容">{selectedItem.content || "-"}</Descriptions.Item>
            </Descriptions>
            <Card size="small" title="原始数据" variant="borderless">
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selectedItem.raw_payload ?? {}, null, 2)}
              </pre>
            </Card>
          </Space>
        ) : null}
      </Modal>
    </Space>
  );
}
