"use client";

import { ReloadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Empty, Row, Space, Spin, Tag, Timeline, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type { WechatStatusResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

function getStatusColor(value: boolean) {
  return value ? "green" : "red";
}

export default function WechatStatusPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const isOwner = session?.role === "owner";
  const [data, setData] = useState<WechatStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<WechatStatusResponse>("/api/admin/wechat/status", {}, accessToken);
      setData(result);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    if (isOwner) {
      void loadStatus();
    } else {
      setLoading(false);
    }
  }, [isOwner, loadStatus]);

  const summaryCards = useMemo(() => {
    if (!data) {
      return [];
    }
    return [
      { label: "通道配置", value: data.channel_token_configured ? "已配置" : "未配置", color: getStatusColor(data.channel_token_configured) },
      { label: "通道就绪", value: data.connected ? "是" : "否", color: getStatusColor(data.connected) },
      { label: "通道账号", value: data.total_accounts, color: "cyan" },
      { label: "活跃账号", value: data.active_accounts, color: "geekblue" },
      { label: "绑定用户", value: data.bound_users, color: "blue" },
      { label: "活跃绑定", value: data.active_identities, color: "green" },
      { label: "总绑定", value: data.total_identities, color: "gold" },
    ];
  }, [data]);

  if (!isOwner) {
    return <Alert type="error" showIcon message="无权限访问" description="微信通道状态仅 owner 可访问。" />;
  }

  if (loading) {
    return (
      <div className="dashboard-empty">
        <Spin size="large" tip="正在加载微信通道状态..." />
      </div>
    );
  }

  const lastMessageAt = data?.last_message_at;

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <ThunderboltOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>微信通道状态</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里展示微信通道是否已配置、当前绑定数量以及最近的入站和出站消息，便于排查通道运行情况。
          </Paragraph>
          <Button icon={<ReloadOutlined />} onClick={() => void loadStatus()} style={{ width: "fit-content" }}>
            刷新状态
          </Button>
          {lastMessageAt ? (
            <Text className="muted-text">最近消息时间：{formatDateTime(lastMessageAt)}</Text>
          ) : null}
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载微信通道状态失败" description={error} /> : null}

      {data ? (
        <Space direction="vertical" size={20} style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            {summaryCards.map((card) => (
              <Col key={card.label} xs={24} sm={12} xl={8}>
                <Card className="section-card" bordered={false}>
                  <Space direction="vertical" size={4}>
                    <Text className="muted-text">{card.label}</Text>
                    <Tag color={card.color}>{String(card.value)}</Tag>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>

          <Card className="section-card" bordered={false} title="最近入站消息">
            {data.recent_inbound_messages.length ? (
              <Timeline
                items={data.recent_inbound_messages.map((item) => ({
                  children: (
                    <Space direction="vertical" size={2}>
                      <Text strong>{item.content || "-"}</Text>
                      <Text className="muted-text">
                        {formatDateTime(item.created_at)} · {item.conversation_id}
                      </Text>
                      <Text className="muted-text">
                        状态：{item.status} · {item.message_id || "无 message_id"}
                      </Text>
                    </Space>
                  ),
                }))}
              />
            ) : (
              <Empty description="暂无入站消息" />
            )}
          </Card>

          <Card className="section-card" bordered={false} title="最近出站消息">
            {data.recent_outbound_messages.length ? (
              <Timeline
                items={data.recent_outbound_messages.map((item) => ({
                  children: (
                    <Space direction="vertical" size={2}>
                      <Text strong>{item.content || "-"}</Text>
                      <Text className="muted-text">
                        {formatDateTime(item.created_at)} · {item.conversation_id}
                      </Text>
                      <Text className="muted-text">
                        状态：{item.status} · {item.error_message || "无错误"}
                      </Text>
                    </Space>
                  ),
                }))}
              />
            ) : (
              <Empty description="暂无出站消息" />
            )}
          </Card>
        </Space>
      ) : null}
    </Space>
  );
}
