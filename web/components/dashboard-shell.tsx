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
  RobotOutlined,
  SettingOutlined,
  TeamOutlined,
  BellOutlined,
  UserOutlined,
  WarningOutlined,
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
  { key: "/dashboard/account", label: "我的账号设置", href: "/dashboard/account", icon: <UserOutlined />, roles: ["owner", "member"] },
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

function getHeaderDateLabel() {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
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
      <div className="app-shell dashboard-shell dashboard-shell--loading">
        <Spin size="large" tip="正在进入驾驶舱..." />
      </div>
    );
  }

  return (
    <Layout className="app-shell dashboard-shell">
      <Sider breakpoint="lg" collapsedWidth={0} width={284} className="dashboard-sidebar">
        <div className="dashboard-sidebar__brand">
          <div className="dashboard-brand-mark">
            <AppstoreOutlined />
          </div>
          <div>
            <Title level={4} className="dashboard-brand-title">
              日程驾驶舱
            </Title>
            <Text className="muted-text">智能规划 · 高效每一天</Text>
          </div>
        </div>

        <div className="dashboard-sidebar__meta">
          <span className="hero-kicker">owner / member</span>
          <Text className="muted-text">全站视觉已切换为浅色编辑风格</Text>
        </div>

        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[pathname]}
          items={menuItems}
          onClick={({ key }) => router.push(key)}
          className="dashboard-nav"
        />

        <div className="dashboard-sidebar__footer">
          <div className="dashboard-profile-card">
            <Avatar className="dashboard-profile-card__avatar">
              {(session.displayName || session.username || "U").slice(0, 1).toUpperCase()}
            </Avatar>
            <div className="dashboard-profile-card__body">
              <Text strong className="dashboard-profile-card__name">
                {session.displayName || session.username || session.userId || "用户"}
              </Text>
              <Space size={8} wrap>
                <Tag color={session.role === "owner" ? "gold" : "blue"} style={{ marginInlineEnd: 0 }}>
                  {session.role}
                </Tag>
                <Text className="muted-text">在线</Text>
              </Space>
            </div>
          </div>
          <Space className="dashboard-sidebar__actions" size={8} wrap>
            <Button icon={<BellOutlined />} href="/dashboard/reminders">
              提醒
            </Button>
            <Button icon={<LogoutOutlined />} onClick={logout}>
              退出
            </Button>
          </Space>
        </div>
      </Sider>

      <Layout className="dashboard-main">
        <Header className="dashboard-topbar">
          <Space direction="vertical" size={2}>
            <Text className="muted-text">欢迎回来</Text>
            <Title level={5} className="dashboard-topbar__title">
              {session.displayName || session.username || session.userId || "用户"}
            </Title>
          </Space>
          <Space size={12} wrap className="dashboard-topbar__actions">
            <Tag color="blue" className="dashboard-topbar__date">
              {getHeaderDateLabel()}
            </Tag>
            <Button href="/dashboard/today">回到今日</Button>
            <Avatar className="dashboard-topbar__avatar">
              {(session.displayName || session.username || "U").slice(0, 1).toUpperCase()}
            </Avatar>
          </Space>
        </Header>

        <Content className="dashboard-content">
          <div className="dashboard-content__inner">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
