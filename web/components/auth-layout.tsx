"use client";

import { ArrowRightOutlined, LoginOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Divider, Row, Space, Typography } from "antd";

const { Title, Paragraph, Text } = Typography;

export function AuthLayout({
  title,
  subtitle,
  ctaText,
  ctaHref,
  children,
}: Readonly<{
  title: string;
  subtitle: string;
  ctaText: string;
  ctaHref: string;
  children: React.ReactNode;
}>) {
  return (
    <main className="app-shell">
      <Row gutter={[24, 24]} style={{ minHeight: "100vh", padding: 24, alignItems: "stretch" }}>
        <Col xs={24} lg={12}>
          <div className="glass-panel" style={{ height: "100%", padding: 32, borderRadius: 28 }}>
            <Space direction="vertical" size={24} style={{ width: "100%" }}>
              <span className="hero-kicker">
                <SafetyCertificateOutlined />
                Schedule Agent
              </span>
              <div>
                <Title
                  className="brand-display"
                  style={{ color: "var(--text-primary)", margin: 0, fontSize: 42, lineHeight: 1.1 }}
                >
                  微信智能日程规划 Agent
                </Title>
                <Paragraph className="muted-text" style={{ marginTop: 16, fontSize: 16, maxWidth: 560 }}>
                  把自然语言转成日程、任务、计划和提醒。先让 Agent 会做事，再让微信成为输入输出通道。
                </Paragraph>
              </div>
              <Row gutter={16}>
                <Col span={8}>
                  <Card className="section-card" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                    <Text style={{ color: "var(--accent)" }}>日程</Text>
                    <Title level={3} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                      24/7
                    </Title>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card className="section-card" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                    <Text style={{ color: "var(--accent-strong)" }}>任务</Text>
                    <Title level={3} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                      计划草案
                    </Title>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card className="section-card" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                    <Text style={{ color: "var(--success)" }}>提醒</Text>
                    <Title level={3} style={{ color: "var(--text-primary)", margin: "8px 0 0" }}>
                      APS
                    </Title>
                  </Card>
                </Col>
              </Row>
              <Alert
                type="info"
                showIcon
                message="当前处于 Dashboard 基础阶段"
                description="登录后即可查看今日计划、日历、任务池和 Agent 日志占位页。"
              />
            </Space>
          </div>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            className="glass-panel"
            bordered={false}
            style={{
              minHeight: "100%",
              borderRadius: 28,
              padding: 8,
              background: "rgba(6, 12, 22, 0.86)",
            }}
          >
            <Space direction="vertical" size={24} style={{ width: "100%", padding: 24 }}>
              <div>
                <Title level={2} style={{ color: "var(--text-primary)", marginBottom: 8 }}>
                  {title}
                </Title>
                <Text className="muted-text">{subtitle}</Text>
              </div>
              {children}
              <Divider style={{ borderColor: "rgba(148, 163, 184, 0.18)", margin: "8px 0" }} />
              <Space size={12} wrap>
                <Button type="default" icon={<LoginOutlined />} href="/login">
                  登录
                </Button>
                <Button type="text" icon={<ArrowRightOutlined />} href={ctaHref}>
                  {ctaText}
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </main>
  );
}
