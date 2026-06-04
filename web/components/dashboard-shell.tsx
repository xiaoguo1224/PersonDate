"use client";

import {
  AppstoreOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  HomeOutlined,
  LogoutOutlined,
  MessageOutlined,
  QrcodeOutlined,
  SettingOutlined,
  TeamOutlined,
  BellOutlined,
  WarningOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Layout, Menu, Space, Spin, Tag, Typography } from "antd";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";

import { useAuth } from "@/components/auth-provider";
import type { UserRole } from "@/lib/types";

type NavigationItem = {
  key: string;
  label: string;
  href: string;
  icon: React.ReactNode;
  roles: UserRole[];
};

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const navigation: NavigationItem[] = [
  { key: "/dashboard/today", label: "今日计划", href: "/dashboard/today", icon: <HomeOutlined />, roles: ["owner", "member"] },
  {
    key: "/dashboard/calendar",
    label: "日历视图",
    href: "/dashboard/calendar",
    icon: <CalendarOutlined />,
    roles: ["owner", "member"],
  },
  { key: "/dashboard/tasks", label: "任务池", href: "/dashboard/tasks", icon: <CheckSquareOutlined />, roles: ["owner", "member"] },
  {
    key: "/dashboard/conflicts",
    label: "冲突事项",
    href: "/dashboard/conflicts",
    icon: <WarningOutlined />,
    roles: ["owner", "member"],
  },
  { key: "/dashboard/reminders", label: "提醒任务", href: "/dashboard/reminders", icon: <BellOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/agent-logs", label: "Agent 日志", href: "/dashboard/agent-logs", icon: <FileTextOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/wechat-binding", label: "微信绑定", href: "/dashboard/wechat-binding", icon: <QrcodeOutlined />, roles: ["owner", "member"] },
  {
    key: "/dashboard/users",
    label: "用户管理",
    href: "/dashboard/users",
    icon: <TeamOutlined />,
    roles: ["owner"],
  },
  {
    key: "/dashboard/invite-codes",
    label: "邀请码管理",
    href: "/dashboard/invite-codes",
    icon: <DatabaseOutlined />,
    roles: ["owner"],
  },
  {
    key: "/dashboard/settings",
    label: "系统设置",
    href: "/dashboard/settings",
    icon: <SettingOutlined />,
    roles: ["owner"],
  },
  {
    key: "/dashboard/wechat-status",
    label: "微信通道状态",
    href: "/dashboard/wechat-status",
    icon: <ClusterOutlined />,
    roles: ["owner"],
  },
  {
    key: "/dashboard/message-logs",
    label: "全局消息日志",
    href: "/dashboard/message-logs",
    icon: <MessageOutlined />,
    roles: ["owner"],
  },
  {
    key: "/dashboard/model-config",
    label: "模型配置",
    href: "/dashboard/model-config",
    icon: <RobotOutlined />,
    roles: ["owner"],
  },
];

function getMenuItems(role: UserRole) {
  return navigation
    .filter((item) => item.roles.includes(role))
    .map((item) => ({
      key: item.key,
      icon: item.icon,
      label: item.label,
    }));
}

export function DashboardShell({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, router, session]);

  const menuItems = useMemo(() => getMenuItems(session?.role ?? "member"), [session?.role]);

  if (loading || !session) {
    return (
      <div className="app-shell" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <Spin size="large" tip="正在进入驾驶舱..." />
      </div>
    );
  }

  return (
    <Layout className="app-shell" style={{ minHeight: "100vh" }}>
      <Sider
        breakpoint="lg"
        collapsedWidth={0}
        width={264}
        style={{
          background: "rgba(4, 9, 18, 0.92)",
          borderRight: "1px solid rgba(148, 163, 184, 0.12)",
        }}
      >
        <div style={{ padding: 24 }}>
          <div className="hero-kicker" style={{ marginBottom: 16 }}>
            <AppstoreOutlined />
            Dashboard
          </div>
          <Title level={4} style={{ color: "var(--text-primary)", margin: 0 }}>
            日程驾驶舱
          </Title>
          <Text className="muted-text">Role: {session.role}</Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[pathname]}
          items={menuItems}
          onClick={({ key }) => router.push(key)}
          style={{
            background: "transparent",
            borderRight: 0,
            fontWeight: 500,
          }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: "0 24px",
            background: "rgba(5, 11, 19, 0.82)",
            backdropFilter: "blur(18px)",
            borderBottom: "1px solid rgba(148, 163, 184, 0.12)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <Space direction="vertical" size={0}>
            <Text className="muted-text">欢迎回来</Text>
            <Title level={5} style={{ color: "var(--text-primary)", margin: 0 }}>
              {session.displayName || session.username || session.userId || "用户"}
            </Title>
          </Space>
          <Space size={12}>
            <Tag color={session.role === "owner" ? "gold" : "blue"} style={{ marginInlineEnd: 0 }}>
              {session.role}
            </Tag>
            <Avatar style={{ background: "linear-gradient(135deg, #7dd3fc 0%, #fbbf24 100%)", color: "#06111f" }}>
              {(session.displayName || session.username || "U").slice(0, 1).toUpperCase()}
            </Avatar>
            <Button icon={<LogoutOutlined />} onClick={logout}>
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ padding: 24 }}>
          <div style={{ maxWidth: 1440, margin: "0 auto" }}>{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
