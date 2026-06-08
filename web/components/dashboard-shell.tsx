"use client";

import {
  AppstoreOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  CloudOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  EnvironmentOutlined,
  FileTextOutlined,
  HomeOutlined,
  InboxOutlined,
  LogoutOutlined,
  MessageOutlined,
  PlusOutlined,
  QrcodeOutlined,
  RobotOutlined,
  SettingOutlined,
  SmileOutlined,
  TeamOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { App, Avatar, Button, Dropdown, Layout, Menu, Space, Spin, Tag, Typography } from "antd";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

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
    { name: "black-gold", color: "#191102", label: "黑金" },
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
        <Spin size="large" />
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

  const [weather, setWeather] = useState<{
    city: string;
    temperature: number;
    description: string;
    humidity: number;
    wind_speed: number;
  } | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [warmMessage, setWarmMessage] = useState("");
  const [weatherApiKey, setWeatherApiKey] = useState<string | null>(null);

  const generateWarmMessage = useCallback((weatherData: typeof weather) => {
    const messages = [
      "今天也要加油哦！",
      "愿你的一天充满阳光和快乐！",
      "无论遇到什么，都要保持微笑！",
      "今天会是美好的一天！",
      "记得照顾好自己！",
      "你的努力终将会有回报！",
      "每一天都是新的开始！",
      "相信自己，你可以做到！",
    ];

    if (weatherData) {
      const temp = weatherData.temperature;
      const desc = weatherData.description.toLowerCase();

      if (desc.includes("雨") || desc.includes("rain")) {
        return "今天有雨，记得带伞哦！";
      } else if (desc.includes("雪") || desc.includes("snow")) {
        return "今天有雪，注意保暖和出行安全！";
      } else if (desc.includes("雾") || desc.includes("fog") || desc.includes("霾") || desc.includes("haze")) {
        return "今天空气质量不佳，建议减少外出！";
      } else if (temp > 35) {
        return "今天天气炎热，记得多喝水防暑！";
      } else if (temp > 30) {
        return "今天天气较热，注意防晒！";
      } else if (temp < 0) {
        return "今天天气寒冷，注意保暖！";
      } else if (temp < 10) {
        return "今天天气较冷，多穿点衣服！";
      }
    }

    const randomIndex = Math.floor(Math.random() * messages.length);
    return messages[randomIndex];
  }, []);

  const fetchWeatherApiKey = useCallback(async () => {
    try {
      const response = await requestJson<{ items: Array<{ key: string; is_configured: boolean }> }>(
        "/api/admin/system-settings",
      );
      const weatherSetting = response.items.find((item) => item.key === "WEATHER_API_KEY");
      if (weatherSetting?.is_configured) {
        setWeatherApiKey("configured");
      }
    } catch (err) {
      console.error("获取天气 API Key 失败:", err);
    }
  }, []);

  const fetchWeather = useCallback(async (latitude: number, longitude: number) => {
    if (!weatherApiKey) {
      const fallbackMessage = generateWarmMessage(null);
      setWarmMessage(fallbackMessage);
      return;
    }
    setWeatherLoading(true);
    try {
      const response = await requestJson<{
        city: string;
        temperature: number;
        description: string;
        humidity: number;
        wind_speed: number;
      }>(`/api/weather?lat=${latitude}&lon=${longitude}`);
      setWeather(response);
      setWarmMessage(generateWarmMessage(response));
    } catch (err) {
      console.error("获取天气失败:", err);
      const fallbackMessage = generateWarmMessage(null);
      setWarmMessage(fallbackMessage);
    } finally {
      setWeatherLoading(false);
    }
  }, [weatherApiKey, generateWarmMessage]);

  const getLocation = useCallback(() => {
    if (!navigator.geolocation) {
      const fallbackMessage = generateWarmMessage(null);
      setWarmMessage(fallbackMessage);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        void fetchWeather(latitude, longitude);
      },
      (err) => {
        console.error("获取位置失败:", err);
        const fallbackMessage = generateWarmMessage(null);
        setWarmMessage(fallbackMessage);
      }
    );
  }, [fetchWeather, generateWarmMessage]);

  useEffect(() => {
    void fetchWeatherApiKey();
  }, [fetchWeatherApiKey]);

  useEffect(() => {
    if (weatherApiKey) {
      getLocation();
    }
  }, [weatherApiKey, getLocation]);

  return (
    <App>
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

      </Sider>

      <Layout className="dashboard-main">
        <Header className="dashboard-topbar">
          <div className="dashboard-topbar__headline">
            <div className="dashboard-topbar__greeting">
              <Title level={4} className="dashboard-topbar__title">
                {preferences.loading ? "正在同步你的时区..." : dateLabel}
              </Title>
            </div>
            <div className="dashboard-topbar__weather">
              {weatherLoading ? (
                <Spin size="small" />
              ) : weather ? (
                <>
                  <span className="dashboard-topbar__weather-item">
                    <EnvironmentOutlined className="dashboard-topbar__weather-icon" />
                    <span>{weather.city}</span>
                  </span>
                  <span className="dashboard-topbar__weather-divider">|</span>
                  <span className="dashboard-topbar__weather-item">
                    <CloudOutlined className="dashboard-topbar__weather-icon" />
                    <span>{weather.temperature}°C {weather.description}</span>
                  </span>
                </>
              ) : (
                <span className="dashboard-topbar__weather-item">
                  <EnvironmentOutlined className="dashboard-topbar__weather-icon" />
                  <span>定位中...</span>
                </span>
              )}
              {warmMessage && (
                <>
                  <span className="dashboard-topbar__weather-divider">|</span>
                  <span className="dashboard-topbar__weather-message">
                    <SmileOutlined className="dashboard-topbar__weather-icon" />
                    <span>{warmMessage}</span>
                  </span>
                </>
              )}
            </div>
          </div>
          <Space size={12} wrap className="dashboard-topbar__actions">
            <Button className="dashboard-topbar__button" type="default" icon={<PlusOutlined />} href="/dashboard/calendar">
              快速新建
            </Button>
            <Button className="dashboard-topbar__icon-button" icon={<BellOutlined />} href="/dashboard/reminders" aria-label="提醒" />
            <ThemeSwitcher />
            <Dropdown
              menu={{
                items: [
                  {
                    key: "profile",
                    label: (
                      <Space>
                        <Tag color={sessionRole === "owner" ? "gold" : "blue"} style={{ marginInlineEnd: 0 }}>
                          {sessionRole}
                        </Tag>
                        <span>{displayName}</span>
                      </Space>
                    ),
                    disabled: true,
                  },
                  { type: "divider" },
                  { key: "account", label: "账号设置", icon: <UserOutlined />, onClick: () => router.push("/dashboard/account") },
                  { key: "reminders", label: "提醒任务", icon: <BellOutlined />, onClick: () => router.push("/dashboard/reminders") },
                  { type: "divider" },
                  { key: "logout", label: "退出登录", icon: <LogoutOutlined />, danger: true, onClick: logout },
                ],
              }}
              trigger={["click"]}
            >
              <Space className="dashboard-topbar__user-trigger" size={8}>
                <Avatar className="dashboard-topbar__avatar">{avatarText}</Avatar>
              </Space>
            </Dropdown>
          </Space>
        </Header>

        <Content className="dashboard-content">
          <div className="dashboard-content__inner">{children}</div>
        </Content>
      </Layout>
    </Layout>
    </App>
  );
}
