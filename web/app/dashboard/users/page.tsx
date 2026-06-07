"use client";

import { ClusterOutlined, CheckCircleOutlined, PauseCircleOutlined, TeamOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Modal, Row, Space, Spin, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type UserAdminItem = {
  id: string;
  username: string;
  display_name?: string | null;
  email?: string | null;
  role: "owner" | "member";
  status: "active" | "disabled" | "deleted";
  default_timezone?: string | null;
  last_login_at?: string | null;
  created_at: string;
};

type UserListResponse = {
  items: UserAdminItem[];
};

type ChannelIdentityItem = {
  id: string;
  channel: string;
  channel_user_id: string;
  conversation_id: string;
  display_name?: string | null;
  avatar_url?: string | null;
  status: string;
  bound_at?: string | null;
  created_at: string;
};

type ChannelIdentityListResponse = {
  items: ChannelIdentityItem[];
};

function getStatusColor(status: string) {
  if (status === "active") return "green";
  if (status === "disabled") return "orange";
  if (status === "deleted") return "default";
  return "blue";
}

function UsersLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" />
    </div>
  );
}

function UsersEmpty() {
  return (
    <div className="dashboard-empty">
      <Text className="muted-text">当前没有成员数据</Text>
    </div>
  );
}

export default function UsersPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const isOwner = session?.role === "owner";
  const [users, setUsers] = useState<UserAdminItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bindingOpen, setBindingOpen] = useState(false);
  const [bindingLoading, setBindingLoading] = useState(false);
  const [bindingError, setBindingError] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<UserAdminItem | null>(null);
  const [bindings, setBindings] = useState<ChannelIdentityItem[]>([]);

  const loadUsers = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<UserListResponse>("/api/admin/users", {}, accessToken);
      setUsers(result.items);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "未知错误");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    if (isOwner) {
      void loadUsers();
    } else {
      setLoading(false);
    }
  }, [isOwner, loadUsers]);

  const summary = useMemo(() => {
    return {
      total: users.length,
      active: users.filter((item) => item.status === "active").length,
      disabled: users.filter((item) => item.status === "disabled").length,
      owners: users.filter((item) => item.role === "owner").length,
    };
  }, [users]);

  const openBindings = useCallback(
    async (user: UserAdminItem) => {
      if (!accessToken) {
        return;
      }
      setSelectedUser(user);
      setBindingOpen(true);
      setBindingLoading(true);
      setBindingError(null);
      try {
        const result = await requestJson<ChannelIdentityListResponse>(
          `/api/admin/users/${user.id}/channel-identities`,
          {},
          accessToken,
        );
        setBindings(result.items);
      } catch (caughtError: unknown) {
        setBindingError(caughtError instanceof Error ? caughtError.message : "未知错误");
        setBindings([]);
      } finally {
        setBindingLoading(false);
      }
    },
    [accessToken],
  );

  const toggleUserStatus = useCallback(
    async (user: UserAdminItem) => {
      if (!accessToken) {
        return;
      }
      try {
        const action = user.status === "active" ? "disable" : "enable";
        await requestJson(
          `/api/admin/users/${user.id}/${action}`,
          {
            method: "PATCH",
          },
          accessToken,
        );
        message.success(user.status === "active" ? "已禁用用户" : "已启用用户");
        await loadUsers();
      } catch (caughtError: unknown) {
        message.error(caughtError instanceof Error ? caughtError.message : "操作失败");
      }
    },
    [accessToken, loadUsers],
  );

  if (!isOwner) {
    return (
      <Alert type="error" showIcon message="无权限访问" description="用户管理仅 owner 可访问。" />
    );
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" variant="borderless">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <TeamOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>用户管理</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里可以查看成员账号、启用或禁用成员，并查看微信绑定情况。后端已经强制 owner 权限校验。
          </Paragraph>
          <Space wrap>
            <Tag color="blue">{summary.total} 个用户</Tag>
            <Tag color="green">{summary.active} 个激活</Tag>
            <Tag color="orange">{summary.disabled} 个禁用</Tag>
            <Tag color="gold">{summary.owners} 个 owner</Tag>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载用户失败" description={error} /> : null}

      {loading ? (
        <UsersLoading />
      ) : users.length ? (
        <Row gutter={[16, 16]}>
          {users.map((user) => (
            <Col xs={24} lg={12} key={user.id}>
              <Card
                className="section-card"
                variant="borderless"
                extra={
                  <Space wrap>
                    <Button size="small" onClick={() => void openBindings(user)} icon={<ClusterOutlined />}>
                      微信绑定
                    </Button>
                    {user.role === "owner" ? (
                      <Tag color="gold">owner</Tag>
                    ) : (
                      <Button
                        size="small"
                        type={user.status === "active" ? "default" : "primary"}
                        danger={user.status === "active"}
                        icon={user.status === "active" ? <PauseCircleOutlined /> : <CheckCircleOutlined />}
                        onClick={() => void toggleUserStatus(user)}
                      >
                        {user.status === "active" ? "禁用" : "启用"}
                      </Button>
                    )}
                  </Space>
                }
              >
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{user.display_name || user.username}</Text>
                    <Tag color={getStatusColor(user.status)}>{user.status}</Tag>
                    <Tag>{user.role}</Tag>
                  </Space>
                  <Text className="muted-text">用户名：{user.username}</Text>
                  {user.email ? <Text className="muted-text">邮箱：{user.email}</Text> : null}
                  {user.default_timezone ? (
                    <Text className="muted-text">时区：{user.default_timezone}</Text>
                  ) : null}
                  <Text className="muted-text">
                    创建时间：{formatDateTime(user.created_at, timezone)}
                  </Text>
                  <Text className="muted-text">
                    最近登录：{user.last_login_at ? formatDateTime(user.last_login_at, timezone) : "未登录"}
                  </Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <UsersEmpty />
      )}

      <Modal
        open={bindingOpen}
        title={`微信绑定 - ${selectedUser?.display_name || selectedUser?.username || "用户"}`}
        onCancel={() => setBindingOpen(false)}
        footer={null}
        width={720}
      >
        {bindingLoading ? (
          <div className="dashboard-empty">
            <Spin />
          </div>
        ) : bindingError ? (
          <Alert type="error" showIcon message="加载绑定信息失败" description={bindingError} />
        ) : bindings.length ? (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {bindings.map((identity) => (
              <Card key={identity.id} size="small" variant="borderless" style={{ background: "rgba(255,255,255,0.04)" }}>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{identity.channel}</Text>
                    <Tag color={getStatusColor(identity.status)}>{identity.status}</Tag>
                  </Space>
                  <Text className="muted-text">channel_user_id：{identity.channel_user_id}</Text>
                  <Text className="muted-text">conversation_id：{identity.conversation_id}</Text>
                  <Text className="muted-text">
                    绑定时间：{identity.bound_at ? formatDateTime(identity.bound_at, timezone) : "未知"}
                  </Text>
                </Space>
              </Card>
            ))}
          </Space>
        ) : (
          <div className="dashboard-empty">
            <Text className="muted-text">当前没有微信绑定记录</Text>
          </div>
        )}
      </Modal>
    </Space>
  );
}
