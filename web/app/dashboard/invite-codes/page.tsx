"use client";

import { MinusCircleOutlined, PlusOutlined, QrcodeOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, DatePicker, Empty, Form, Input, InputNumber, Row, Space, Spin, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { formatDateTime } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type InviteCodeItem = {
  id: string;
  code: string;
  max_uses: number;
  used_count: number;
  expires_at?: string | null;
  status: string;
  remark?: string | null;
};

type InviteCodeListResponse = {
  items: InviteCodeItem[];
};

type InviteCodeCreatePayload = {
  max_uses: number;
  expires_at?: { toISOString: () => string } | null;
  remark?: string | null;
};

function InviteCodesLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" tip="正在加载邀请码..." />
    </div>
  );
}

function InviteCodesEmpty() {
  return (
    <div className="dashboard-empty">
      <Empty description="当前没有邀请码" />
    </div>
  );
}

function getStatusColor(status: string) {
  if (status === "active") return "green";
  if (status === "disabled") return "default";
  if (status === "expired") return "red";
  return "blue";
}

export default function InviteCodesPage() {
  const { session } = useAuth();
  const [form] = Form.useForm<InviteCodeCreatePayload>();
  const [codes, setCodes] = useState<InviteCodeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isOwner = session?.role === "owner";

  const accessToken = session?.accessToken;

  const loadInviteCodes = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<InviteCodeListResponse>("/api/admin/invite-codes", {}, accessToken);
      setCodes(result.items);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "未知错误");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    if (isOwner) {
      void loadInviteCodes();
    } else {
      setLoading(false);
    }
  }, [isOwner, loadInviteCodes]);

  const activeCount = useMemo(() => codes.filter((item) => item.status === "active").length, [codes]);

  const handleCreate = async (values: InviteCodeCreatePayload) => {
    if (!accessToken) {
      return;
    }
    setSubmitting(true);
    try {
      await requestJson(
        "/api/admin/invite-codes",
        {
          method: "POST",
          body: JSON.stringify({
            ...values,
            expires_at: values.expires_at ? values.expires_at.toISOString() : null,
          }),
        },
        accessToken,
      );
      message.success("邀请码已创建");
      form.resetFields();
      await loadInviteCodes();
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDisable = async (inviteCodeId: string) => {
    if (!accessToken) {
      return;
    }
    try {
      await requestJson(
        `/api/admin/invite-codes/${inviteCodeId}/disable`,
        {
          method: "PATCH",
        },
        accessToken,
      );
      message.success("邀请码已禁用");
      await loadInviteCodes();
    } catch (caughtError: unknown) {
      message.error(caughtError instanceof Error ? caughtError.message : "禁用失败");
    }
  };

  if (!isOwner) {
    return (
      <Alert
        type="error"
        showIcon
        message="无权限访问"
        description="邀请码管理仅 owner 可访问。"
      />
    );
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <QrcodeOutlined />
            owner 管理
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>邀请码管理</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里可以创建邀请码、查看使用次数并禁用邀请码。成员注册必须依赖这里生成的邀请码。
          </Paragraph>
          <Space wrap>
            <Tag color="green">{activeCount} 个有效</Tag>
            <Tag color="blue">{codes.length} 个总数</Tag>
          </Space>
        </Space>
      </Card>

      {error ? (
        <Alert type="error" showIcon message="加载邀请码失败" description={error} />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card className="section-card" bordered={false} title="创建邀请码">
            <Form
              form={form}
              layout="vertical"
              onFinish={handleCreate}
              initialValues={{ max_uses: 1 }}
              requiredMark={false}
            >
              <Form.Item
                name="max_uses"
                label="最大使用次数"
                rules={[{ required: true, message: "请输入最大使用次数" }]}
              >
                <InputNumber min={1} max={1000} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="expires_at" label="过期时间">
                <DatePicker showTime style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="remark" label="备注">
                <Input.TextArea rows={3} placeholder="可选备注" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={submitting} block icon={<PlusOutlined />}>
                生成邀请码
              </Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={16}>
          <Card className="section-card" bordered={false} title="邀请码列表">
            {loading ? (
              <InviteCodesLoading />
            ) : codes.length ? (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {codes.map((item) => (
                  <Card
                    key={item.id}
                    size="small"
                    bordered={false}
                    style={{ background: "rgba(255,255,255,0.04)" }}
                    extra={
                      item.status === "active" ? (
                        <Button danger size="small" onClick={() => void handleDisable(item.id)} icon={<MinusCircleOutlined />}>
                          禁用
                        </Button>
                      ) : (
                        <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                      )
                    }
                  >
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ letterSpacing: 1 }}>
                          {item.code}
                        </Text>
                        <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                      </Space>
                      <Text className="muted-text">
                        使用次数：{item.used_count}/{item.max_uses}
                      </Text>
                      <Text className="muted-text">
                        过期时间：{item.expires_at ? formatDateTime(item.expires_at) : "未设置"}
                      </Text>
                      {item.remark ? <Text className="muted-text">备注：{item.remark}</Text> : null}
                    </Space>
                  </Card>
                ))}
              </Space>
            ) : (
              <InviteCodesEmpty />
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
