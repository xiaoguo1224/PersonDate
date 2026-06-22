"use client";

import { LoadingOutlined, QrcodeOutlined, ReloadOutlined, StopOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Modal, QRCode, Space, Spin, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
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

const STATUS_OPTIONS = [
  { text: "已绑定", value: "active" },
  { text: "已禁用", value: "disabled" },
  { text: "已过期", value: "expired" },
] as const;

function getStatusColor(status: string) {
  if (status === "active") return "green";
  if (status === "disabled") return "default";
  if (status === "expired") return "red";
  return "blue";
}

function getStatusLabel(status: string) {
  const found = STATUS_OPTIONS.find((opt) => opt.value === status);
  return found?.text ?? status;
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
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<ChannelIdentityListResponse>("/me/channel-identities", {}, accessToken);
      setIdentities(result.items);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const loadAccounts = useCallback(async () => {
    if (!accessToken) return;
    try {
      const result = await requestJson<WechatAccountListResponse>("/me/wechat-accounts", {}, accessToken);
      setAccounts(result.items);
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "加载账号失败");
    }
  }, [accessToken]);

  const loadLoginSession = useCallback(
    async (loginSessionId: string) => {
      if (!accessToken) return;
      try {
        const result = await requestJson<WechatLoginSessionItem>(
          `/me/wechat-login-sessions/${loginSessionId}`,
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
    if (!accessToken || !loginSession?.login_session_id) return;
    if (loginSessionDetail?.status === "confirmed" || loginSessionDetail?.status === "expired") return;

    const refreshSession = async () => {
      await loadLoginSession(loginSession.login_session_id);
    };

    void refreshSession();
    const timer = window.setInterval(() => void refreshSession(), 3000);
    return () => window.clearInterval(timer);
  }, [accessToken, loadLoginSession, loginSession?.login_session_id, loginSessionDetail?.status]);

  useEffect(() => {
    if (loginSessionDetail?.status !== "confirmed") return;
    setQrModalOpen(false);
    void loadIdentities();
    void loadAccounts();
  }, [loadAccounts, loadIdentities, loginSessionDetail?.status]);

  const summary = useMemo(() => {
    const active = identities.filter((item) => item.status === "active").length;
    const disabled = identities.filter((item) => item.status === "disabled").length;
    return { total: identities.length, active, disabled };
  }, [identities]);

  const handleCreateLoginSession = async () => {
    if (!accessToken) return;
    setGenerating(true);
    try {
      const result = await requestJson<WechatLoginSessionCreateResponse>(
        "/me/wechat-login-sessions",
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

  const handleRefreshSession = async () => {
    if (!loginSession) return;
    await loadLoginSession(loginSession.login_session_id);
  };

  const handleUnbind = async (identityId: string) => {
    if (!accessToken) return;
    try {
      await requestJson(`/me/channel-identities/${identityId}`, { method: "DELETE" }, accessToken);
      message.success("已解绑微信");
      await loadIdentities();
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "解绑失败");
    }
  };

  const identityColumns: ColumnsType<ChannelIdentityItem> = useMemo(
    () => [
      {
        title: "账号标识",
        dataIndex: "channel_user_id",
        key: "channel_user_id",
        ellipsis: true,
      },
      {
        title: "会话标识",
        dataIndex: "conversation_id",
        key: "conversation_id",
        ellipsis: true,
      },
      {
        title: "昵称",
        dataIndex: "display_name",
        key: "display_name",
        render: (val: string | null | undefined) => val || "-",
      },
      {
        title: "通道",
        dataIndex: "channel",
        key: "channel",
        width: 90,
        filters: [{ text: "wechat", value: "wechat" }],
        onFilter: (value, record) => record.channel === value,
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 100,
        filters: STATUS_OPTIONS.map((opt) => ({ text: opt.text, value: opt.value })),
        defaultFilteredValue: ["active"],
        onFilter: (value, record) => record.status === value,
        render: (status: string) => <Tag color={getStatusColor(status)}>{getStatusLabel(status)}</Tag>,
      },
      {
        title: "绑定时间",
        dataIndex: "bound_at",
        key: "bound_at",
        width: 180,
        sorter: (a, b) => new Date(a.bound_at ?? 0).getTime() - new Date(b.bound_at ?? 0).getTime(),
        defaultSortOrder: "descend",
        render: (val: string | null) => (val ? formatDateTime(val, timezone) : "-"),
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
        render: (val: string) => formatDateTime(val, timezone),
      },
      {
        title: "操作",
        key: "action",
        width: 80,
        render: (_, record) =>
          record.status === "active" ? (
            <Button danger size="small" icon={<StopOutlined />} onClick={() => void handleUnbind(record.id)}>
              解绑
            </Button>
          ) : null,
      },
    ],
    [timezone],
  );

  const accountColumns: ColumnsType<WechatAccountItem> = useMemo(
    () => [
      {
        title: "账号 ID",
        dataIndex: "account_id",
        key: "account_id",
        ellipsis: true,
      },
      {
        title: "微信用户 ID",
        dataIndex: "wechat_user_id",
        key: "wechat_user_id",
        ellipsis: true,
        render: (val: string | null | undefined) => val || "-",
      },
      {
        title: "Base URL",
        dataIndex: "base_url",
        key: "base_url",
        ellipsis: true,
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 100,
        filters: [
          { text: "活跃", value: "active" },
          { text: "禁用", value: "disabled" },
        ],
        onFilter: (value, record) => record.status === value,
        render: (status: string) => <Tag color={getStatusColor(status)}>{status}</Tag>,
      },
      {
        title: "最近活跃",
        dataIndex: "last_active_time",
        key: "last_active_time",
        width: 180,
        sorter: (a, b) =>
          new Date(a.last_active_time ?? 0).getTime() - new Date(b.last_active_time ?? 0).getTime(),
        defaultSortOrder: "descend",
        render: (val: string | null) => (val ? formatDateTime(val, timezone) : "-"),
      },
      {
        title: "绑定时间",
        dataIndex: "bind_time",
        key: "bind_time",
        width: 180,
        render: (val: string | null) => (val ? formatDateTime(val, timezone) : "-"),
      },
    ],
    [timezone],
  );

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
            <Tag color="blue">{summary.total} 条绑定记录</Tag>
            <Tag color="green">{summary.active} 条已激活</Tag>
            <Tag color="default">{summary.disabled} 条已禁用</Tag>
            <Tag color="cyan">{accounts.length} 个通道账号</Tag>
          </Space>
          <Space wrap>
            <Button
              type="primary"
              icon={generating ? <LoadingOutlined /> : <QrcodeOutlined />}
              onClick={() => void handleCreateLoginSession()}
              loading={generating}
            >
              创建二维码登录
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void loadIdentities();
                void loadAccounts();
              }}
              loading={loading}
            >
              刷新
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
        onCancel={() => setQrModalOpen(false)}
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

      <Card className="section-card" variant="borderless" title="绑定记录">
        <Table
          rowKey="id"
          dataSource={identities}
          columns={identityColumns}
          loading={loading}
          pagination={false}
          size="middle"
        />
      </Card>

      <Card className="section-card" variant="borderless" title="通道账号">
        <Table
          rowKey="id"
          dataSource={accounts}
          columns={accountColumns}
          loading={loading}
          pagination={false}
          size="middle"
        />
      </Card>
    </Space>
  );
}
