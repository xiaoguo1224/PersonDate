"use client";

import { RobotOutlined, SaveOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Form, Input, Row, Space, Spin, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import { getSettingValue, type SystemSettingItem, type SystemSettingsResponse } from "@/lib/admin-settings";

const { Title, Paragraph, Text } = Typography;

type ModelConfigForm = {
  LLM_BASE_URL?: string;
  LLM_MODEL?: string;
  LLM_API_KEY?: string;
};

export default function ModelConfigPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const [form] = Form.useForm<ModelConfigForm>();
  const [items, setItems] = useState<SystemSettingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const llmBaseUrl = useMemo(() => getSettingValue(items, "LLM_BASE_URL"), [items]);
  const llmModel = useMemo(() => getSettingValue(items, "LLM_MODEL"), [items]);
  const llmApiKey = useMemo(() => getSettingValue(items, "LLM_API_KEY"), [items]);

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
          LLM_BASE_URL: String(getSettingValue(result.items, "LLM_BASE_URL")?.value ?? ""),
          LLM_MODEL: String(getSettingValue(result.items, "LLM_MODEL")?.value ?? ""),
          LLM_API_KEY: "",
        });
      } catch (caughtError: unknown) {
        setError(caughtError instanceof Error ? caughtError.message : "加载失败");
      } finally {
        setLoading(false);
      }
    }

    void loadSettings();
  }, [accessToken, form]);

  const handleFinish = async (values: ModelConfigForm) => {
    if (!accessToken) {
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, string> = {};
      if (values.LLM_BASE_URL !== undefined) {
        payload.LLM_BASE_URL = values.LLM_BASE_URL;
      }
      if (values.LLM_MODEL !== undefined) {
        payload.LLM_MODEL = values.LLM_MODEL;
      }
      if (values.LLM_API_KEY && values.LLM_API_KEY.trim()) {
        payload.LLM_API_KEY = values.LLM_API_KEY.trim();
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
      form.setFieldsValue({
        LLM_BASE_URL: String(getSettingValue(result.items, "LLM_BASE_URL")?.value ?? ""),
        LLM_MODEL: String(getSettingValue(result.items, "LLM_MODEL")?.value ?? ""),
        LLM_API_KEY: "",
      });
      message.success("模型配置已更新");
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
            <RobotOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>模型配置</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里管理 LLM Base URL、模型名称和 API Key。API Key 不会明文展示，留空表示不修改当前密钥。
          </Paragraph>
          <Space wrap>
            <Tag color="blue">Base URL：{String(llmBaseUrl?.value ?? "未配置")}</Tag>
            <Tag color="green">模型：{String(llmModel?.value ?? "未配置")}</Tag>
            <Tag color={llmApiKey?.is_configured ? "gold" : "default"}>
              API Key：{llmApiKey?.is_configured ? "已配置" : "未配置"}
            </Tag>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message="加载模型配置失败" description={error} /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card className="section-card" variant="borderless">
            <Form<ModelConfigForm>
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleFinish(values)}
            >
              <Form.Item label="LLM Base URL" name="LLM_BASE_URL">
                <Input placeholder="https://api.example.com/v1" />
              </Form.Item>

              <Form.Item label="LLM Model" name="LLM_MODEL">
                <Input placeholder="deepseek-chat" />
              </Form.Item>

              <Form.Item
                label="LLM API Key"
                name="LLM_API_KEY"
                extra="留空表示不修改当前密钥。输入新密钥后会覆盖原配置。"
              >
                <Input.Password placeholder="输入新的 API Key" autoComplete="new-password" />
              </Form.Item>

              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
                保存模型配置
              </Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card className="section-card" variant="borderless">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Title level={4} style={{ color: "var(--text-primary)", margin: 0 }}>
                当前状态
              </Title>
              <Text className="muted-text">当前配置直接来自 `system_settings`，不在页面中展示 API Key 明文。</Text>
              <div className="dashboard-empty">
                <Space direction="vertical" size={8}>
                  <Text className="muted-text">LLM_BASE_URL：{String(llmBaseUrl?.value ?? "未配置")}</Text>
                  <Text className="muted-text">LLM_MODEL：{String(llmModel?.value ?? "未配置")}</Text>
                  <Text className="muted-text">
                    LLM_API_KEY：{llmApiKey?.is_configured ? "已配置" : "未配置"}
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
