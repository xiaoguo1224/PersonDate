"use client";

import {
  AppstoreOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  DownOutlined,
  FileTextOutlined,
  HomeOutlined,
  InboxOutlined,
  LogoutOutlined,
  MessageOutlined,
  PlusOutlined,
  QrcodeOutlined,
  RobotOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { Avatar, Badge, Button, Layout, Menu, Space, Spin, Tag, Typography } from "antd";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";

import { useAuth } from "@/components/auth-provider";
import { DashboardPreferencesProvider, useDashboardTimezone } from "@/components/dashboard-preferences";
import { useTheme } from "@/components/theme-provider";
import type { UserRole } from "@/lib/types";
import type { ThemeName } from "@/components/theme-provider";

type NavigationItem = {
  key: string;
  label: string;
  href?: string;
  icon: React.ReactNode;
  roles: UserRole[];
  children?: NavigationItem[];
};

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const navigation: NavigationItem[] = [
  { key: "/dashboard/today", label: "今日安排", href: "/dashboard/today", icon: <HomeOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/calendar", label: "日历视图", href: "/dashboard/calendar", icon: <CalendarOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/tasks", label: "任务", href: "/dashboard/tasks", icon: <CheckSquareOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/conflicts", label: "冲突事项", href: "/dashboard/conflicts", icon: <WarningOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/reminders", label: "提醒任务", href: "/dashboard/reminders", icon: <BellOutlined />, roles: ["owner", "member"] },
  { key: "logs", label: "日志", icon: <FileTextOutlined />, roles: ["owner", "member"], children: [
    { key: "/dashboard/agent-logs", label: "Agent 日志", icon: <FileTextOutlined />, roles: ["owner", "member"] },
    { key: "/dashboard/message-logs", label: "消息日志", icon: <MessageOutlined />, roles: ["owner"] },
    { key: "/dashboard/wechat-outbound", label: "出站队列", icon: <InboxOutlined />, roles: ["owner"] },
  ]},
  { key: "/dashboard/wechat-binding", label: "微信绑定", href: "/dashboard/wechat-binding", icon: <QrcodeOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/account", label: "我的账号设置", href: "/dashboard/account", icon: <UserOutlined />, roles: ["owner", "member"] },
  { key: "/dashboard/users", label: "用户管理", href: "/dashboard/users", icon: <TeamOutlined />, roles: ["owner"] },
  { key: "/dashboard/invite-codes", label: "邀请码管理", href: "/dashboard/invite-codes", icon: <DatabaseOutlined />, roles: ["owner"] },
  { key: "settings", label: "设置", icon: <SettingOutlined />, roles: ["owner"], children: [
    { key: "/dashboard/settings", label: "系统设置", icon: <SettingOutlined />, roles: ["owner"] },
    { key: "/dashboard/model-config", label: "模型配置", icon: <RobotOutlined />, roles: ["owner"] },
    { key: "/dashboard/notification-settings", label: "通知设置", icon: <BellOutlined />, roles: ["owner", "member"] },
  ]},
  { key: "/dashboard/wechat-status", label: "微信通道状态", href: "/dashboard/wechat-status", icon: <ClusterOutlined />, roles: ["owner"] },
];

type MenuItem = NonNullable<MenuProps["items"]>[number];

function menuItemToAntD(item: NavigationItem, role: UserRole): MenuItem {
  if (item.children) {
    const visibleChildren = item.children
      .filter((child) => child.roles.includes(role))
      .map((child) => ({
        key: child.key,
        icon: child.icon,
        label: child.label,
      }));
    if (visibleChildren.length === 0) return null;
    return {
      key: item.key,
      icon: item.icon,
      label: item.label,
      children: visibleChildren,
    } as MenuItem;
  }
  if (!item.roles.includes(role)) return null;
  return {
    key: item.key,
    icon: item.icon,
    label: item.label,
  } as MenuItem;
}

function getMenuItems(role: UserRole) {
  return navigation
    .map((item) => menuItemToAntD(item, role))
    .filter((item): item is MenuItem => item !== null);
}

function ThemeSwitcher() {
  const { themeName, setThemeName } = useTheme();
  const themes: { name: ThemeName; color: string; label: string }[] = [
    { name: "blue-white", color: "#1677ff", label: "蓝白" },
    { name: "black-gold", color: "#d4a853", label: "黑金" },
    { name: "pink", color: "#e84393", label: "粉" },
  ];
  return (
    <div className="dashboard-theme-switcher">
      {themes.map((t) => (
        <button
          key={t.name}
          className={`dashboard-theme-dot ${themeName === t.name ? "active" : ""}`}
          style={{ background: t.color }}
          onClick={() => setThemeName(t.name)}
          title={t.label}
          aria-label={t.label}
        />
      ))}
    </div>
  );
}

function getHeaderDateLabel(timeZone: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone,
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

  const displayName = session.displayName || session.username || session.userId || "用户";
  const avatarText = (displayName || "U").slice(0, 1).toUpperCase();

  return (
    <DashboardPreferencesProvider>
      <DashboardShellContent
        avatarText={avatarText}
        displayName={displayName}
        menuItems={menuItems}
        pathname={pathname}
        router={router}
        sessionRole={session.role}
        logout={logout}
      >
        {children}
      </DashboardShellContent>
    </DashboardPreferencesProvider>
  );
}

function DashboardShellContent({
  avatarText,
  children,
  displayName,
  logout,
  menuItems,
  pathname,
  router,
  sessionRole,
}: Readonly<{
  avatarText: string;
  children: React.ReactNode;
  displayName: string;
  logout: () => void;
  menuItems: MenuProps["items"];
  pathname: string;
  router: ReturnType<typeof useRouter>;
  sessionRole: UserRole;
}>) {
  const preferences = useDashboardTimezone();
  const dateLabel = getHeaderDateLabel(preferences.timezone);

  return (
    <Layout className="app-shell dashboard-shell">
      <Sider breakpoint="lg" collapsedWidth={0} width={254} className="dashboard-sidebar">
        <div className="dashboard-sidebar__brand">
          <div className="dashboard-brand-mark">
            <AppstoreOutlined />
          </div>
          <div>
            <Title level={4} className="dashboard-brand-title">
              安排驾驶舱
            </Title>
            <Text className="muted-text">智能规划，高效每一天</Text>
          </div>
        </div>

        <div className="dashboard-sidebar__meta">
          <span className="hero-kicker">Dashboard</span>
          <Text className="muted-text">安排、任务、冲突与提醒统一管理</Text>
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
            <Avatar className="dashboard-profile-card__avatar">{avatarText}</Avatar>
            <div className="dashboard-profile-card__body">
              <Text strong className="dashboard-profile-card__name">
                {displayName}
              </Text>
              <Space size={8} wrap>
                <Tag color={sessionRole === "owner" ? "gold" : "blue"} style={{ marginInlineEnd: 0 }}>
                  {sessionRole}
                </Tag>
                <Text className="muted-text">在线</Text>
              </Space>
            </div>
          </div>
          <ThemeSwitcher />
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
          <Space direction="vertical" size={2} className="dashboard-topbar__headline">
            <Text className="muted-text dashboard-topbar__eyebrow">欢迎回来</Text>
            <Title level={4} className="dashboard-topbar__title">
              {preferences.loading ? "正在同步你的时区..." : dateLabel}
            </Title>
          
          </Space>
          <Space size={12} wrap className="dashboard-topbar__actions">
            <Button className="dashboard-topbar__button" type="default" icon={<PlusOutlined />} href="/dashboard/calendar">
              快速新建
            </Button>
            <Badge count={3} size="small" offset={[-4, 4]}>
              <Button className="dashboard-topbar__icon-button" icon={<BellOutlined />} aria-label="通知" />
            </Badge>
            <Avatar className="dashboard-topbar__avatar">{avatarText}</Avatar>
            <Button type="text" className="dashboard-topbar__user-menu" icon={<DownOutlined />} />
          </Space>
        </Header>

        <Content className="dashboard-content">
          <div className="dashboard-content__inner">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
