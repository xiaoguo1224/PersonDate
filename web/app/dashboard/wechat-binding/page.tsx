"use client";

import { LoadingOutlined, QrcodeOutlined, ReloadOutlined, StopOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Empty, Modal, QRCode, Space, Spin, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type {
  ChannelIdentityItem,
  ChannelIdentityListResponse,
  WechatAccountItem,
  WechatAccountListResponse,
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
  const { message } = App.useApp();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const [identities, setIdentities] = useState<ChannelIdentityItem[]>([]);
  const [accounts, setAccounts] = useState<WechatAccountItem[]>([]);
  const [loginSession, setLoginSession] = useState<WechatLoginSessionCreateResponse | null>(null);
  const [loginSessionDetail, setLoginSessionDetail] = useState<WechatLoginSessionItem | null>(null);
  const [qrModalOpen, setQrModalOpen] = useState(false);
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

  const loadAccounts = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const result = await requestJson<WechatAccountListResponse>("/api/me/wechat-accounts", {}, accessToken);
      setAccounts(result.items);
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "加载账号失败");
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
      void loadAccounts();
    } else {
      setLoading(false);
    }
  }, [loadAccounts, loadIdentities, session]);

  useEffect(() => {
    if (!accessToken || !loginSession?.login_session_id) {
      return;
    }
    if (loginSessionDetail?.status === "confirmed" || loginSessionDetail?.status === "expired") {
      return;
    }

    const refreshSession = async () => {
      await loadLoginSession(loginSession.login_session_id);
    };

    void refreshSession();
    const timer = window.setInterval(() => {
      void refreshSession();
    }, 3000);

    return () => {
      window.clearInterval(timer);
    };
  }, [accessToken, loadLoginSession, loginSession?.login_session_id, loginSessionDetail?.status]);

  useEffect(() => {
    if (loginSessionDetail?.status !== "confirmed") {
      return;
    }
    setQrModalOpen(false);
    void loadIdentities();
    void loadAccounts();
  }, [loadAccounts, loadIdentities, loginSessionDetail?.status]);

  const accountBindings = useMemo(() => {
    const grouped = new Map<string, ChannelIdentityItem[]>();
    for (const identity of identities) {
      const key = identity.channel_user_id;
      const list = grouped.get(key) ?? [];
      list.push(identity);
      grouped.set(key, list);
    }

    const result: { channel_user_id: string; active: ChannelIdentityItem | null; latest: ChannelIdentityItem; total: number }[] = [];
    for (const [channel_user_id, list] of grouped) {
      const sorted = [...list].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
      const active = sorted.find((item) => item.status === "active") ?? null;
      result.push({ channel_user_id, active, latest: sorted[0], total: list.length });
    }
    return result;
  }, [identities]);

  const summary = useMemo(() => {
    return {
      accountCount: accountBindings.length,
      activeCount: accountBindings.filter((item) => item.active).length,
      accountTotal: accounts.length,
      accountActive: accounts.filter((item) => item.status === "active").length,
    };
  }, [accountBindings, accounts]);

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
      setQrModalOpen(true);
      await loadLoginSession(result.login_session_id);
      message.success("二维码登录会话已创建");
      await loadIdentities();
      await loadAccounts();
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const handleCopySessionId = async () => { // eslint-disable-line @typescript-eslint/no-unused-vars
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

  const handleCloseQrModal = () => {
    setQrModalOpen(false);
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
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" variant="borderless">
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
            <Tag color="blue">{summary.accountCount} 个绑定账号</Tag>
            <Tag color="green">{summary.activeCount} 个已激活</Tag>
            <Tag color="cyan">{summary.accountTotal} 个通道账号</Tag>
            <Tag color="geekblue">{summary.accountActive} 个活跃通道</Tag>
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
          message="请使用微信扫码完成登录"
          description={`会话将在 ${formatDateTime(loginSession.expires_at, timezone)} 过期。扫码后页面会自动轮询确认状态。`}
          action={
            <Space>
              <Button size="small" icon={<QrcodeOutlined />} onClick={() => setQrModalOpen(true)}>
                查看二维码
              </Button>
              <Button size="small" icon={<ReloadOutlined />} onClick={() => void handleRefreshSession()}>
                刷新会话
              </Button>
            </Space>
          }
        />
      ) : null}

      <Modal
        open={qrModalOpen && Boolean(loginSession)}
        title="微信二维码登录"
        onCancel={handleCloseQrModal}
        footer={null}
        centered
        destroyOnHidden
      >
        <Space direction="vertical" size={16} style={{ width: "100%", alignItems: "center", textAlign: "center" }}>
          {loginSession?.qr_img_content ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={`data:image/png;base64,${loginSession.qr_img_content}`}
              alt="微信扫码"
              style={{ width: 240, height: 240 }}
            />
          ) : (
            <QRCode value={loginSession?.qr_payload ?? ""} size={240} bordered />
          )}
          <Space direction="vertical" size={4}>
            <Text strong>请使用微信扫码完成登录</Text>
            <Text className="muted-text">会话 ID：{loginSession?.login_session_id}</Text>
            <Text className="muted-text">
              过期时间：{loginSession ? formatDateTime(loginSession.expires_at, timezone) : "未知"}
            </Text>
            <Text className="muted-text">扫码后页面会自动刷新会话状态。</Text>
          </Space>
        </Space>
      </Modal>

      {loginSessionDetail ? (
        <Alert
          type={loginSessionDetail.status === "confirmed" ? "success" : "info"}
          showIcon
          message={`登录会话状态：${loginSessionDetail.status}`}
          description={
            loginSessionDetail.confirmed_at
              ? `确认时间：${formatDateTime(loginSessionDetail.confirmed_at, timezone)}`
              : `创建时间：${formatDateTime(loginSessionDetail.created_at, timezone)}`
          }
        />
      ) : null}

      {accountBindings.length ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {accountBindings.map((binding) => {
            const display = binding.active ?? binding.latest;
            const isActive = binding.active !== null;
            return (
              <Card
                key={binding.channel_user_id}
                className="section-card"
                variant="borderless"
                extra={
                  isActive ? (
                    <Button danger size="small" icon={<StopOutlined />} onClick={() => void handleUnbind(display.id)}>
                      解绑
                    </Button>
                  ) : (
                    <Tag color={getStatusColor(display.status)}>{display.status}</Tag>
                  )
                }
              >
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{display.display_name || binding.channel_user_id}</Text>
                    <Tag color={isActive ? "green" : "default"}>{isActive ? "已绑定" : "未绑定"}</Tag>
                    <Tag>{display.channel}</Tag>
                    {binding.total > 1 && <Tag color="orange">共 {binding.total} 条记录</Tag>}
                  </Space>
                  <Text className="muted-text">账号标识：{binding.channel_user_id}</Text>
                  {isActive && (
                    <Text className="muted-text">会话标识：{display.conversation_id}</Text>
                  )}
                  <Text className="muted-text">
                    {isActive ? "绑定时间" : "最后绑定时间"}：{display.bound_at ? formatDateTime(display.bound_at, timezone) : "未知"}
                  </Text>
                </Space>
              </Card>
            );
          })}
        </Space>
      ) : (
        <Card className="section-card" variant="borderless">
          <Empty description="当前没有微信绑定记录" />
        </Card>
      )}

      <Card className="section-card" variant="borderless" title="通道账号">
        {accounts.length ? (
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {accounts.map((account) => (
              <Card key={account.id} size="small" variant="borderless" style={{ background: "var(--surface-secondary)" }}>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{account.account_id}</Text>
                    <Tag color={getStatusColor(account.status)}>{account.status}</Tag>
                  </Space>
                  <Text className="muted-text">wechat_user_id：{account.wechat_user_id || "未知"}</Text>
                  <Text className="muted-text">base_url：{account.base_url}</Text>
                  <Text className="muted-text">
                    最近活跃：{account.last_active_time ? formatDateTime(account.last_active_time, timezone) : "未知"}
                  </Text>
                </Space>
              </Card>
            ))}
          </Space>
        ) : (
          <Empty description="当前没有通道账号" />
        )}
      </Card>
    </Space>
  );
}
