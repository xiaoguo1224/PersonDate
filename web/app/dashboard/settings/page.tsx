"use client";

import { SettingOutlined, SaveOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Spin, Switch, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import { getSettingValue, type SystemSettingItem, type SystemSettingsResponse } from "@/lib/admin-settings";

const { Title, Paragraph, Text } = Typography;

type SystemSettingsForm = {
  DEFAULT_TIMEZONE: string;
  REMINDER_SCAN_INTERVAL_SECONDS: number;
  DEFAULT_REMIND_BEFORE_MINUTES: number;
  SYSTEM_DAILY_PUSH_ENABLED: boolean;
  WEATHER_API_PROVIDER: string;
  WEATHER_API_KEY?: string;
};

export default function SystemSettingsPage() {
  const { session } = useAuth();
  const { message } = App.useApp();
  const accessToken = session?.accessToken;
  const [form] = Form.useForm<SystemSettingsForm>();
  const [items, setItems] = useState<SystemSettingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(() => {
    const timezone = getSettingValue(items, "DEFAULT_TIMEZONE");
    const scanInterval = getSettingValue(items, "REMINDER_SCAN_INTERVAL_SECONDS");
    const remindBefore = getSettingValue(items, "DEFAULT_REMIND_BEFORE_MINUTES");
    const dailyPush = getSettingValue(items, "SYSTEM_DAILY_PUSH_ENABLED");
    const weatherApiProvider = getSettingValue(items, "WEATHER_API_PROVIDER");
    const weatherApiKey = getSettingValue(items, "WEATHER_API_KEY");
    return { timezone, scanInterval, remindBefore, dailyPush, weatherApiProvider, weatherApiKey };
  }, [items]);

  useEffect(() => {
    async function loadSettings() {
      if (!accessToken) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const result = await requestJson<SystemSettingsResponse>("/api/admin/system-settings", {}, accessToken);
        setItems(result.items);
        form.setFieldsValue({
          DEFAULT_TIMEZONE: String(getSettingValue(result.items, "DEFAULT_TIMEZONE")?.value ?? "Asia/Shanghai"),
          REMINDER_SCAN_INTERVAL_SECONDS: Number(
            getSettingValue(result.items, "REMINDER_SCAN_INTERVAL_SECONDS")?.value ?? 10,
          ),
          DEFAULT_REMIND_BEFORE_MINUTES: Number(
            getSettingValue(result.items, "DEFAULT_REMIND_BEFORE_MINUTES")?.value ?? 0,
          ),
          SYSTEM_DAILY_PUSH_ENABLED: Boolean(
            getSettingValue(result.items, "SYSTEM_DAILY_PUSH_ENABLED")?.value ?? false,
          ),
          WEATHER_API_PROVIDER: String(
            getSettingValue(result.items, "WEATHER_API_PROVIDER")?.value ?? "openweathermap",
          ),
          WEATHER_API_KEY: "",
        });
      } catch (caughtError: unknown) {
        setError(caughtError instanceof Error ? caughtError.message : "加载失败");
      } finally {
        setLoading(false);
      }
    }

    void loadSettings();
  }, [accessToken, form]);

  const handleFinish = async (values: SystemSettingsForm) => {
    if (!accessToken) {
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...values };
      // 只有当 API Key 为空时才删除，否则保留用户输入的值
      if (!values.WEATHER_API_KEY || !values.WEATHER_API_KEY.trim()) {
        delete payload.WEATHER_API_KEY;
      }
      const result = await requestJson<SystemSettingsResponse>(
        "/api/admin/system-settings",
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
        accessToken,
      );
      setItems(result.items);
      // 保存成功后清空输入框
      form.setFieldsValue({
        WEATHER_API_KEY: "",
      });
      message.success("系统设置已更新");
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "保存失败");
    } finally {
      setSaving(false);
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
            <SettingOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>系统设置</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里管理全局默认时区、提醒扫描间隔和系统级推送开关。敏感配置统一在“模型配置”页单独维护。
          </Paragraph>
          <Space wrap>
            <Tag color="blue">默认时区：{summary.timezone?.value ? String(summary.timezone.value) : "未设置"}</Tag>
            <Tag color="green">
              扫描间隔：{summary.scanInterval?.value ? String(summary.scanInterval.value) : "10"} 秒
            </Tag>
            <Tag color="gold">
              默认提醒：{summary.remindBefore?.value ? String(summary.remindBefore.value) : "0"} 分钟
            </Tag>
            <Tag color={summary.dailyPush?.value ? "green" : "default"}>
              每日推送：{summary.dailyPush?.value ? "开启" : "关闭"}
            </Tag>
            <Tag color="cyan">
              天气源：{summary.weatherApiProvider?.value === "amap" ? "高德地图" : "OpenWeatherMap"}
            </Tag>
            <Tag color={summary.weatherApiKey?.is_configured ? "cyan" : "default"}>
              天气 API Key：{summary.weatherApiKey?.is_configured ? "已配置" : "未配置"}
            </Tag>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载系统设置失败" description={error} /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card className="section-card" variant="borderless">
            <Form<SystemSettingsForm>
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleFinish(values)}
            >
              <Form.Item
                label="默认时区"
                name="DEFAULT_TIMEZONE"
                rules={[{ required: true, message: "请输入默认时区" }]}
              >
                <Input placeholder="Asia/Shanghai" />
              </Form.Item>

              <Form.Item
                label="提醒扫描间隔（秒）"
                name="REMINDER_SCAN_INTERVAL_SECONDS"
                rules={[{ required: true, message: "请输入扫描间隔" }]}
              >
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>

              <Form.Item
                label="系统默认提醒提前分钟数"
                name="DEFAULT_REMIND_BEFORE_MINUTES"
                rules={[{ required: true, message: "请输入默认提醒分钟数" }]}
              >
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>

              <Form.Item label="每日推送开关" name="SYSTEM_DAILY_PUSH_ENABLED" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Form.Item
                label="天气 API 提供商"
                name="WEATHER_API_PROVIDER"
                rules={[{ required: true, message: "请选择天气 API 提供商" }]}
              >
                <Select>
                  <Select.Option value="openweathermap">OpenWeatherMap</Select.Option>
                  <Select.Option value="amap">高德地图</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="天气 API Key"
                name="WEATHER_API_KEY"
                extra={
                  summary.weatherApiKey?.is_configured
                    ? "已配置 API Key。留空表示不修改，输入新值将覆盖原配置。"
                    : "未配置 API Key，请输入有效的 API Key 以启用天气功能。"
                }
              >
                <Input.Password
                  placeholder={summary.weatherApiKey?.is_configured ? "留空不修改，输入新值覆盖" : "请输入天气 API Key"}
                  autoComplete="new-password"
                />
              </Form.Item>

              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
                保存系统设置
              </Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card className="section-card" variant="borderless">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Title level={4} style={{ color: "var(--text-primary)", margin: 0 }}>
                当前配置
              </Title>
              <Text className="muted-text">这些值直接来自后端 `system_settings`，可以用于校验当前系统基线。</Text>
              <div className="dashboard-empty">
                <Space direction="vertical" size={8}>
                  <Text className="muted-text">DEFAULT_TIMEZONE：{String(summary.timezone?.value ?? "Asia/Shanghai")}</Text>
                  <Text className="muted-text">
                    REMINDER_SCAN_INTERVAL_SECONDS：{String(summary.scanInterval?.value ?? 10)}
                  </Text>
                  <Text className="muted-text">
                    DEFAULT_REMIND_BEFORE_MINUTES：{String(summary.remindBefore?.value ?? 0)}
                  </Text>
                  <Text className="muted-text">
                    SYSTEM_DAILY_PUSH_ENABLED：{summary.dailyPush?.value ? "true" : "false"}
                  </Text>
                  <Text className="muted-text">
                    WEATHER_API_PROVIDER：{summary.weatherApiProvider?.value === "amap" ? "amap" : "openweathermap"}
                  </Text>
                  <Text className="muted-text">
                    WEATHER_API_KEY：{summary.weatherApiKey?.is_configured ? "已配置" : "未配置"}
                  </Text>
                </Space>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
