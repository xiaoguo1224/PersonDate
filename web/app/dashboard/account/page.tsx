"use client";

import { SaveOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Form, Input, InputNumber, Row, Space, Spin, Switch, Typography } from "antd";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import type { UserSettingsResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

type SettingsForm = {
  default_timezone: string;
  workday_start_time?: string | null;
  workday_end_time?: string | null;
  daily_plan_push_time?: string | null;
  default_remind_before_minutes?: number | null;
  daily_plan_push_enabled: boolean;
  city?: string | null;
};

function normalizeText(value?: string | null) {
  return value ?? "";
}

export default function AccountPage() {
  const { session } = useAuth();
  const { message } = App.useApp();
  const accessToken = session?.accessToken;
  const [form] = Form.useForm<SettingsForm>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSettings() {
      if (!accessToken) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const result = await requestJson<UserSettingsResponse>("/api/me/settings", {}, accessToken);
        form.setFieldsValue({
          default_timezone: result.default_timezone,
          workday_start_time: normalizeText(result.workday_start_time),
          workday_end_time: normalizeText(result.workday_end_time),
          daily_plan_push_time: normalizeText(result.daily_plan_push_time),
          default_remind_before_minutes: result.default_remind_before_minutes ?? 0,
          daily_plan_push_enabled: result.daily_plan_push_enabled,
          city: normalizeText(result.city),
        });
      } catch (caughtError: unknown) {
        setError(caughtError instanceof Error ? caughtError.message : "加载失败");
      } finally {
        setLoading(false);
      }
    }

    void loadSettings();
  }, [accessToken, form]);

  const handleFinish = async (values: SettingsForm) => {
    if (!accessToken) {
      return;
    }
    setSaving(true);
    try {
      const result = await requestJson<UserSettingsResponse>(
        "/api/me/settings",
        {
          method: "PATCH",
          body: JSON.stringify(values),
        },
        accessToken,
      );
      form.setFieldsValue({
        default_timezone: result.default_timezone,
        workday_start_time: normalizeText(result.workday_start_time),
        workday_end_time: normalizeText(result.workday_end_time),
        daily_plan_push_time: normalizeText(result.daily_plan_push_time),
        default_remind_before_minutes: result.default_remind_before_minutes ?? 0,
        daily_plan_push_enabled: result.daily_plan_push_enabled,
        city: normalizeText(result.city),
      });
      message.success("设置已保存");
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
            我的账号设置
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>我的设置</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里会保存你的默认时区、工作时间段和每日计划推送设置，这些配置会被 Agent 和页面展示共同使用。
          </Paragraph>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载设置失败" description={error} /> : null}

      <Row gutter={[16, 16]}>
        <Card className="section-card" variant="borderless" style={{ width: "100%" }}>
          <Form
            form={form}
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => void handleFinish(values)}
            initialValues={{
              default_timezone: "Asia/Shanghai",
              default_remind_before_minutes: 0,
              daily_plan_push_enabled: false,
            }}
          >
            <Form.Item
              label="默认时区"
              name="default_timezone"
              rules={[{ required: true, message: "请输入默认时区" }]}
            >
              <Input placeholder="Asia/Shanghai" />
            </Form.Item>

            <Form.Item label="工作开始时间" name="workday_start_time">
              <Input placeholder="09:00:00" />
            </Form.Item>

            <Form.Item label="工作结束时间" name="workday_end_time">
              <Input placeholder="18:00:00" />
            </Form.Item>

            <Form.Item label="每日计划推送时间" name="daily_plan_push_time">
              <Input placeholder="08:00:00" />
            </Form.Item>

            <Form.Item label="默认提醒提前分钟数" name="default_remind_before_minutes">
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>

            <Form.Item
              label="启用每日计划推送"
              name="daily_plan_push_enabled"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>

            <Form.Item label="所在城市（用于天气推送）" name="city">
              <Input placeholder="如：北京、上海、广州" />
            </Form.Item>

            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
              保存设置
            </Button>
          </Form>
        </Card>
      </Row>

      <Card className="section-card" variant="borderless">
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text strong>说明</Text>
          <Text className="muted-text">
            当前表单直接调用 `/api/me/settings`，保存后会同步到后端 `user_settings`。
          </Text>
        </Space>
      </Card>
    </Space>
  );
}
