"use client";

import { CopyOutlined, LoadingOutlined, QrcodeOutlined, ReloadOutlined, StopOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Space, Spin, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type {
  ChannelIdentityItem,
  ChannelIdentityListResponse,
  WechatLoginSessionCreateResponse,
  WechatLoginSessionItem,
} from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

function getStatusColor(status: string) {
  if (status === "active") return "green";
  if (status === "disabled") return "default";
  if (status === "expired") return "red";
  return "blue";
}

export default function WechatBindingPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const [identities, setIdentities] = useState<ChannelIdentityItem[]>([]);
  const [loginSession, setLoginSession] = useState<WechatLoginSessionCreateResponse | null>(null);
  const [loginSessionDetail, setLoginSessionDetail] = useState<WechatLoginSessionItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const loadIdentities = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<ChannelIdentityListResponse>("/api/me/channel-identities", {}, accessToken);
      setIdentities(result.items);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const loadLoginSession = useCallback(
    async (loginSessionId: string) => {
      if (!accessToken) {
        return;
      }
      try {
        const result = await requestJson<WechatLoginSessionItem>(
          `/api/me/wechat-login-sessions/${loginSessionId}`,
          {},
          accessToken,
        );
        setLoginSessionDetail(result);
      } catch (caughtError: unknown) {
        message.error(caughtError instanceof Error ? caughtError.message : "刷新登录会话失败");
      }
    },
    [accessToken],
  );

  useEffect(() => {
    if (session) {
      void loadIdentities();
    } else {
      setLoading(false);
    }
  }, [loadIdentities, session]);

  const summary = useMemo(() => {
    return {
      total: identities.length,
      active: identities.filter((item) => item.status === "active").length,
      disabled: identities.filter((item) => item.status === "disabled").length,
    };
  }, [identities]);

  const handleCreateLoginSession = async () => {
    if (!accessToken) {
      return;
    }
    setGenerating(true);
    try {
      const result = await requestJson<WechatLoginSessionCreateResponse>(
        "/api/me/wechat-login-sessions",
        { method: "POST" },
        accessToken,
      );
      setLoginSession(result);
      await loadLoginSession(result.login_session_id);
      message.success("二维码登录会话已创建");
      await loadIdentities();
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const handleCopySessionId = async () => {
    if (!loginSession) {
      return;
    }
    await navigator.clipboard.writeText(loginSession.login_session_id);
    message.success("已复制会话 ID");
  };

  const handleRefreshSession = async () => {
    if (!loginSession) {
      return;
    }
    await loadLoginSession(loginSession.login_session_id);
  };

  const handleUnbind = async (identityId: string) => {
    if (!accessToken) {
      return;
    }
    try {
      await requestJson(
        `/api/me/channel-identities/${identityId}`,
        { method: "DELETE" },
        accessToken,
      );
      message.success("已解绑微信");
      await loadIdentities();
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "解绑失败");
    }
  };

  if (loading) {
    return (
      <div className="dashboard-empty">
        <Spin size="large" tip="正在加载微信绑定信息..." />
      </div>
    );
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <QrcodeOutlined />
            微信绑定
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>微信绑定</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里可以创建二维码登录会话、查看当前绑定状态并解绑。微信只负责通道收发，不改变 Agent 的日程处理主流程。
          </Paragraph>
          <Space wrap>
            <Tag color="blue">{summary.total} 个绑定</Tag>
            <Tag color="green">{summary.active} 个激活</Tag>
            <Tag color="default">{summary.disabled} 个禁用</Tag>
          </Space>
          <Space wrap>
            <Button type="primary" icon={generating ? <LoadingOutlined /> : <QrcodeOutlined />} onClick={() => void handleCreateLoginSession()} loading={generating}>
              创建二维码登录
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadIdentities()} loading={loading}>
              刷新绑定
            </Button>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载微信绑定失败" description={error} /> : null}

      {loginSession ? (
        <Alert
          type="success"
          showIcon
          message={`请使用微信扫码完成登录：${loginSession.login_session_id}`}
          description={`二维码载荷：${loginSession.qr_payload}，会话将在 ${formatDateTime(loginSession.expires_at)} 过期。`}
          action={
            <Space>
              <Button size="small" icon={<CopyOutlined />} onClick={() => void handleCopySessionId()}>
                复制会话 ID
              </Button>
              <Button size="small" icon={<ReloadOutlined />} onClick={() => void handleRefreshSession()}>
                刷新会话
              </Button>
            </Space>
          }
        />
      ) : null}

      {loginSessionDetail ? (
        <Alert
          type={loginSessionDetail.status === "confirmed" ? "success" : "info"}
          showIcon
          message={`登录会话状态：${loginSessionDetail.status}`}
          description={
            loginSessionDetail.confirmed_at
              ? `确认时间：${formatDateTime(loginSessionDetail.confirmed_at)}`
              : `创建时间：${formatDateTime(loginSessionDetail.created_at)}`
          }
        />
      ) : null}

      {identities.length ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {identities.map((identity) => (
            <Card
              key={identity.id}
              className="section-card"
              bordered={false}
              extra={
                identity.status === "active" ? (
                  <Button danger size="small" icon={<StopOutlined />} onClick={() => void handleUnbind(identity.id)}>
                    解绑
                  </Button>
                ) : (
                  <Tag color={getStatusColor(identity.status)}>{identity.status}</Tag>
                )
              }
            >
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Space wrap>
                  <Text strong>{identity.display_name || identity.channel_user_id}</Text>
                  <Tag color={getStatusColor(identity.status)}>{identity.status}</Tag>
                  <Tag>{identity.channel}</Tag>
                </Space>
                <Text className="muted-text">channel_user_id：{identity.channel_user_id}</Text>
                <Text className="muted-text">conversation_id：{identity.conversation_id}</Text>
                <Text className="muted-text">
                  绑定时间：{identity.bound_at ? formatDateTime(identity.bound_at) : "未知"}
                </Text>
                <Text className="muted-text">
                  创建时间：{formatDateTime(identity.created_at)}
                </Text>
              </Space>
            </Card>
          ))}
        </Space>
      ) : (
        <Card className="section-card" bordered={false}>
          <Empty description="当前没有微信绑定记录" />
        </Card>
      )}
    </Space>
  );
}
