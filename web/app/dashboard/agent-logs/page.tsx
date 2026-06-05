"use client";

import { EyeOutlined, FileTextOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Descriptions, Modal, Space, Spin, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import type { AgentLogItem, AgentLogListResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

function formatTimestamp(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AgentLogsPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const [items, setItems] = useState<AgentLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<AgentLogItem | null>(null);

  const endpoint = useMemo(() => {
    return session?.role === "owner" ? "/api/admin/agent-logs" : "/api/my-agent-logs";
  }, [session?.role]);

  const loadLogs = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<AgentLogListResponse>(endpoint, {}, accessToken);
      setItems(result.items);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accessToken, endpoint]);

  useEffect(() => {
    if (!session) {
      return;
    }
    void loadLogs();
  }, [loadLogs, session]);

  const columns = [
    {
      title: "时间",
      dataIndex: "created_at",
      render: (value: string) => formatTimestamp(value),
      width: 180,
    },
    {
      title: "输入",
      dataIndex: "input_text",
      ellipsis: true,
      render: (value: string) => <Text>{value}</Text>,
    },
    {
      title: "intent",
      dataIndex: "intent",
      width: 140,
      render: (value: string | null) => (value ? <Tag color="blue">{value}</Tag> : <Tag>unknown</Tag>),
    },
    {
      title: "状态",
      dataIndex: "success",
      width: 110,
      render: (value: boolean) => <Tag color={value ? "green" : "red"}>{value ? "成功" : "失败"}</Tag>,
    },
    {
      title: "操作",
      width: 120,
      render: (_: unknown, record: AgentLogItem) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => setSelectedItem(record)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <FileTextOutlined />
            Agent 日志
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>Agent 日志</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里展示自然语言输入、意图识别、工具调用、工具结果和最终回复，方便你排查 Debug API 的真实行为。
          </Paragraph>
          <Button icon={<ReloadOutlined />} onClick={() => void loadLogs()} loading={loading} style={{ width: "fit-content" }}>
            刷新日志
          </Button>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载 Agent 日志失败" description={error} /> : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" tip="正在加载 Agent 日志..." />
        </div>
      ) : (
        <Card className="section-card" bordered={false}>
          <Table
            rowKey="id"
            columns={columns}
            dataSource={items}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            scroll={{ x: 900 }}
            locale={{ emptyText: "暂无 Agent 日志" }}
          />
        </Card>
      )}

      <Modal
        open={selectedItem !== null}
        onCancel={() => setSelectedItem(null)}
        footer={null}
        title="Agent 日志详情"
        width={960}
      >
        {selectedItem ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="时间">{formatTimestamp(selectedItem.created_at)}</Descriptions.Item>
              <Descriptions.Item label="用户输入">{selectedItem.input_text}</Descriptions.Item>
              <Descriptions.Item label="intent">{selectedItem.intent || "unknown"}</Descriptions.Item>
              <Descriptions.Item label="channel">{selectedItem.channel}</Descriptions.Item>
              <Descriptions.Item label="conversation_id">{selectedItem.conversation_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="成功">{selectedItem.success ? "是" : "否"}</Descriptions.Item>
              <Descriptions.Item label="错误信息">{selectedItem.error_message || "-"}</Descriptions.Item>
              <Descriptions.Item label="最终回复">{selectedItem.final_response || "-"}</Descriptions.Item>
            </Descriptions>

            <Card size="small" title="Graph Trace" bordered={false}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selectedItem.graph_trace ?? [], null, 2)}
              </pre>
            </Card>
            <Card size="small" title="Tool Calls" bordered={false}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selectedItem.tools_called ?? [], null, 2)}
              </pre>
            </Card>
            <Card size="small" title="Tool Results" bordered={false}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selectedItem.tool_results ?? [], null, 2)}
              </pre>
            </Card>
          </Space>
        ) : null}
      </Modal>
    </Space>
  );
}
