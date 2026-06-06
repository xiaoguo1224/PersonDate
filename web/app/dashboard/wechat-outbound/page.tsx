"use client";

import { EyeOutlined, ReloadOutlined, InboxOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Descriptions, Form, Input, Modal, Select, Space, Spin, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type { WechatOutboundQueueItem, WechatOutboundQueueListResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

type OutboundQueueFilters = {
  account_id?: string;
  conversation_id?: string;
  status?: string;
};

function getStatusColor(status: string) {
  if (status === "sent") return "green";
  if (status === "queued") return "blue";
  if (status === "failed") return "red";
  return "default";
}

export default function WechatOutboundQueuePage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const isOwner = session?.role === "owner";
  const [form] = Form.useForm<OutboundQueueFilters>();
  const [items, setItems] = useState<WechatOutboundQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<WechatOutboundQueueItem | null>(null);
  const [query, setQuery] = useState<OutboundQueueFilters>({});

  const loadQueue = useCallback(
    async (filters: OutboundQueueFilters = {}) => {
      if (!accessToken) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const searchParams = new URLSearchParams();
        if (filters.account_id) {
          searchParams.set("account_id", filters.account_id);
        }
        if (filters.conversation_id) {
          searchParams.set("conversation_id", filters.conversation_id);
        }
        if (filters.status && filters.status !== "all") {
          searchParams.set("status", filters.status);
        }
        const path = searchParams.toString()
          ? `/api/admin/wechat/outbound-queue?${searchParams.toString()}`
          : "/api/admin/wechat/outbound-queue";
        const result = await requestJson<WechatOutboundQueueListResponse>(path, {}, accessToken);
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
      void loadQueue(query);
    } else {
      setLoading(false);
    }
  }, [isOwner, loadQueue, query]);

  const handleSearch = (values: OutboundQueueFilters) => {
    const nextQuery = {
      account_id: values.account_id?.trim() || undefined,
      conversation_id: values.conversation_id?.trim() || undefined,
      status: values.status || undefined,
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
      render: (value: string) => formatDateTime(value),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (value: string) => <Tag color={getStatusColor(value)}>{value}</Tag>,
    },
    {
      title: "通道账号",
      dataIndex: "account_id",
      width: 170,
      ellipsis: true,
    },
    {
      title: "会话",
      dataIndex: "conversation_id",
      width: 170,
      ellipsis: true,
    },
    {
      title: "message_id",
      dataIndex: "message_id",
      width: 180,
      ellipsis: true,
    },
    {
      title: "重试",
      dataIndex: "retry_count",
      width: 90,
    },
    {
      title: "内容",
      dataIndex: "content",
      ellipsis: true,
      render: (value: string | null) => <Text>{value || "-"}</Text>,
    },
    {
      title: "操作",
      width: 110,
      render: (_: unknown, record: WechatOutboundQueueItem) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => setSelectedItem(record)}>
          详情
        </Button>
      ),
    },
  ];

  if (!isOwner) {
    return <Alert type="error" showIcon message="无权限访问" description="微信出站队列仅 owner 可访问。" />;
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <InboxOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>微信出站队列</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里展示微信通道当前的出站排队、已发送与失败消息，便于确认 queued 消息是否被派发，以及排查失败原因。
          </Paragraph>
          <Button icon={<ReloadOutlined />} onClick={() => void loadQueue(query)} loading={loading} style={{ width: "fit-content" }}>
            刷新队列
          </Button>
        </Space>
      </Card>

      <Card className="section-card" bordered={false}>
        <Form form={form} layout="inline" onFinish={handleSearch}>
          <Form.Item name="account_id" label="账号 ID">
            <Input placeholder="输入 account_id" allowClear style={{ width: 240 }} />
          </Form.Item>
          <Form.Item name="conversation_id" label="会话 ID">
            <Input placeholder="输入 conversation_id" allowClear style={{ width: 240 }} />
          </Form.Item>
          <Form.Item name="status" label="状态" initialValue="all">
            <Select
              style={{ width: 150 }}
              options={[
                { value: "all", label: "全部" },
                { value: "queued", label: "排队中" },
                { value: "sent", label: "已发送" },
                { value: "failed", label: "失败" },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                查询
              </Button>
              <Button onClick={() => void handleReset()}>重置</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {error ? <Alert type="error" showIcon message="加载出站队列失败" description={error} /> : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" tip="正在加载出站队列..." />
        </div>
      ) : (
        <Card className="section-card" bordered={false}>
          <Table
            rowKey="id"
            dataSource={items}
            columns={columns}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            scroll={{ x: 1200 }}
            locale={{ emptyText: "暂无出站队列" }}
          />
        </Card>
      )}

      <Modal
        open={selectedItem !== null}
        onCancel={() => setSelectedItem(null)}
        footer={null}
        title="出站队列详情"
        width={900}
      >
        {selectedItem ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="时间">{formatDateTime(selectedItem.created_at)}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={getStatusColor(selectedItem.status)}>{selectedItem.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="通道账号">{selectedItem.account_id}</Descriptions.Item>
              <Descriptions.Item label="会话 ID">{selectedItem.conversation_id}</Descriptions.Item>
              <Descriptions.Item label="message_id">{selectedItem.message_id}</Descriptions.Item>
              <Descriptions.Item label="to_user_id">{selectedItem.to_user_id}</Descriptions.Item>
              <Descriptions.Item label="context_token">{selectedItem.context_token || "-"}</Descriptions.Item>
              <Descriptions.Item label="retry_count">{selectedItem.retry_count}</Descriptions.Item>
              <Descriptions.Item label="error_code">{selectedItem.error_code || "-"}</Descriptions.Item>
              <Descriptions.Item label="error_message">{selectedItem.error_message || "-"}</Descriptions.Item>
              <Descriptions.Item label="sent_at">{selectedItem.sent_at ? formatDateTime(selectedItem.sent_at) : "-"}</Descriptions.Item>
              <Descriptions.Item label="内容">{selectedItem.content || "-"}</Descriptions.Item>
            </Descriptions>
            <Card size="small" title="原始数据" bordered={false}>
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
