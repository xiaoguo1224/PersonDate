"use client";

import { BellOutlined, SaveOutlined } from "@ant-design/icons";
import { App, Button, Card, Cascader, Col, Form, Grid, Input, Row, Space, Spin, Switch, Typography } from "antd";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import { chinaAreaOptions, cityPathToText, resolveCityPath } from "@/lib/china-area";

const { Title, Paragraph, Text } = Typography;

type NotificationForm = {
  daily_plan_push_enabled: boolean;
  daily_plan_push_time: string;
  cityPath?: string[];
};

type NotificationSettingsResponse = NotificationForm & {
  city?: string | null;
};

export default function NotificationSettingsPage() {
  const { session } = useAuth();
  const { message } = App.useApp();
  const accessToken = session?.accessToken;
  const screens = Grid.useBreakpoint();
  const isMobile = screens.md === false;
  const [form] = Form.useForm<NotificationForm>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedCity, setSavedCity] = useState<string | null>(null);

  useEffect(() => {
    async function loadSettings() {
      if (!accessToken) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const result = await requestJson<NotificationSettingsResponse>("/me/notification-settings", {}, accessToken);
        form.setFieldsValue({
          daily_plan_push_enabled: result.daily_plan_push_enabled ?? false,
          daily_plan_push_time: result.daily_plan_push_time ?? "08:00",
          cityPath: resolveCityPath(result.city) ?? undefined,
        });
        setSavedCity(result.city?.trim() ? result.city.trim() : null);
      } catch {
        message.error("加载通知设置失败");
      } finally {
        setLoading(false);
      }
    }
    void loadSettings();
  }, [accessToken, form, message]);

  const handleFinish = async (values: NotificationForm) => {
    if (!accessToken) return;
    setSaving(true);
    try {
      const { cityPath, ...restValues } = values;
      await requestJson(
        "/me/notification-settings",
        {
          method: "PUT",
          body: JSON.stringify({
            ...restValues,
            city: cityPathToText(cityPath),
          }),
        },
        accessToken,
      );
      setSavedCity(cityPathToText(cityPath));
      message.success("通知设置已保存");
    } catch {
      message.error("保存失败");
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
            <BellOutlined />
            通知设置
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>每日安排推送</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            开启后，系统会在每天指定时间将当日安排和天气推送到你的微信。
          </Paragraph>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card className="section-card" variant="borderless">
            <Form<NotificationForm>
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleFinish(values)}
            >
              <Form.Item label="每日推送" name="daily_plan_push_enabled" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Form.Item
                label="推送时间"
                name="daily_plan_push_time"
                rules={[{ required: true, message: "请选择推送时间" }]}
              >
                <Input placeholder="08:00" />
              </Form.Item>

              <Form.Item label="所在地区（用于天气）" name="cityPath">
                <Cascader
                  allowClear
                  showSearch
                  placeholder="请选择省 / 市 / 区"
                  options={chinaAreaOptions}
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
        <Col xs={24} xl={10}>
          <Card className="section-card" variant="borderless">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Title level={4} style={{ color: "var(--text-primary)", margin: 0 }}>
                推送预览
              </Title>
              <div className="dashboard-empty" style={{ padding: 16, whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 13 }}>
{`🌤 早安！今天是 2026-06-07 星期日

📍 北京 今日天气：☀️ 晴  22~31°C

📅 今日安排：
  • 10:00 - 产品评审会议

✅ 待办任务：
  • 完成周报（高优先级）

📌 回复我可调整今日安排～`}
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
