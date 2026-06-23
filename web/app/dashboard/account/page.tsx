"use client";

import { SaveOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Cascader, Col, Form, Grid, Input, InputNumber, Row, Space, Spin, Switch, TimePicker, Typography } from "antd";
import { useEffect, useState } from "react";

import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";

dayjs.extend(customParseFormat);

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import { chinaAreaOptions, cityPathToText, resolveCityPath } from "@/lib/china-area";
import type { UserSettingsResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

type SettingsForm = {
  default_timezone: string;
  workday_start_time?: dayjs.Dayjs | null;
  workday_end_time?: dayjs.Dayjs | null;
  daily_plan_push_time?: dayjs.Dayjs | null;
  default_remind_before_minutes?: number | null;
  daily_plan_push_enabled: boolean;
  cityPath?: string[];
};

export default function AccountPage() {
  const { session } = useAuth();
  const { message } = App.useApp();
  const accessToken = session?.accessToken;
  const screens = Grid.useBreakpoint();
  const isMobile = screens.md === false;
  const [form] = Form.useForm<SettingsForm>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedCity, setSavedCity] = useState<string | null>(null);

  useEffect(() => {
    async function loadSettings() {
      if (!accessToken) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const result = await requestJson<UserSettingsResponse>("/me/settings", {}, accessToken);
        form.setFieldsValue({
          default_timezone: result.default_timezone,
          workday_start_time: result.workday_start_time ? dayjs(result.workday_start_time, ["HH:mm:ss", "HH:mm"]) : null,
          workday_end_time: result.workday_end_time ? dayjs(result.workday_end_time, ["HH:mm:ss", "HH:mm"]) : null,
          daily_plan_push_time: result.daily_plan_push_time ? dayjs(result.daily_plan_push_time, ["HH:mm:ss", "HH:mm"]) : null,
          default_remind_before_minutes: result.default_remind_before_minutes ?? 0,
          daily_plan_push_enabled: result.daily_plan_push_enabled,
          cityPath: resolveCityPath(result.city) ?? undefined,
        });
        setSavedCity(result.city?.trim() ? result.city.trim() : null);
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
      const { cityPath, ...restValues } = values;
      const body = {
        ...restValues,
        workday_start_time: restValues.workday_start_time?.format("HH:mm") ?? null,
        workday_end_time: restValues.workday_end_time?.format("HH:mm") ?? null,
        daily_plan_push_time: restValues.daily_plan_push_time?.format("HH:mm") ?? null,
        city: cityPathToText(cityPath),
      };
      const result = await requestJson<UserSettingsResponse>(
        "/me/settings",
        {
          method: "PATCH",
          body: JSON.stringify(body),
        },
        accessToken,
      );
      form.setFieldsValue({
        default_timezone: result.default_timezone,
        workday_start_time: result.workday_start_time ? dayjs(result.workday_start_time, ["HH:mm:ss", "HH:mm"]) : null,
        workday_end_time: result.workday_end_time ? dayjs(result.workday_end_time, ["HH:mm:ss", "HH:mm"]) : null,
        daily_plan_push_time: result.daily_plan_push_time ? dayjs(result.daily_plan_push_time, ["HH:mm:ss", "HH:mm"]) : null,
        default_remind_before_minutes: result.default_remind_before_minutes ?? 0,
        daily_plan_push_enabled: result.daily_plan_push_enabled,
        cityPath: resolveCityPath(result.city) ?? undefined,
      });
      setSavedCity(result.city?.trim() ? result.city.trim() : null);
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
        <Col xs={24} xl={16}>
          <Card className="section-card" variant="borderless">
          <Form
            form={form}
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => void handleFinish(values)}
            initialValues={{
              default_timezone: "Asia/Shanghai",
              default_remind_before_minutes: 0,
              daily_plan_push_enabled: false,
              daily_plan_push_time: dayjs("09:00", "HH:mm"),
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
              <TimePicker format="HH:mm" style={{ width: "100%" }} />
            </Form.Item>

            <Form.Item label="工作结束时间" name="workday_end_time">
              <TimePicker format="HH:mm" style={{ width: "100%" }} />
            </Form.Item>

            <Form.Item label="每日计划推送时间" name="daily_plan_push_time">
              <TimePicker format="HH:mm" style={{ width: "100%" }} />
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

            <Form.Item label="所在地区（用于天气推送）" name="cityPath">
              <Cascader
                allowClear
                showSearch
                placeholder="请选择省 / 市 / 区"
                options={chinaAreaOptions}
                style={{ width: "100%" }}
              />
            </Form.Item>
            <Text className="muted-text" style={{ display: "block", marginBottom: 16 }}>
              当前保存：{savedCity || "未设置"}
            </Text>

            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving} block={isMobile}>
              保存设置
            </Button>
          </Form>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card className="section-card" variant="borderless" title="设置说明">
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              <Text className="muted-text">默认时区会影响时间展示、提醒计算和 Agent 输出。</Text>
              <Text className="muted-text">工作时间段用于后续排期和可用时间计算。</Text>
              <Text className="muted-text">地区信息会同步到天气推送和今日摘要。</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card className="section-card" variant="borderless">
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text strong>说明</Text>
          <Text className="muted-text">
            当前表单直接调用 `/me/settings`，保存后会同步到后端 `user_settings`。
          </Text>
        </Space>
      </Card>
    </Space>
  );
}
