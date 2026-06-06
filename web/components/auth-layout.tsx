"use client";

import { ArrowRightOutlined, LoginOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Button, Card, Col, Divider, Row, Space, Typography } from "antd";

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
    <main className="app-shell auth-shell">
      <Row gutter={[28, 28]} className="auth-layout">
        <Col xs={24} xl={11}>
          <div className="auth-story">
            <Space direction="vertical" size={24} style={{ width: "100%" }}>
              <span className="hero-kicker">
                <SafetyCertificateOutlined />
                Schedule Agent
              </span>
              <div className="auth-story__headline">
                <Title className="brand-display auth-story__title" style={{ margin: 0 }}>
                  微信智能日程规划 Agent
                </Title>
                <Paragraph className="muted-text auth-story__subtitle">{subtitle}</Paragraph>
              </div>
              <div className="auth-story__panel">
                <div className="auth-story__panel-copy">
                  <Text className="muted-text">把自然语言变成可执行的日程、任务与提醒。</Text>
                  <Title level={2} className="auth-story__panel-title">
                    从登录开始，进入你的专属节奏。
                  </Title>
                  <Text className="muted-text">
                    先让 Agent 接管琐碎安排，再把注意力留给真正重要的工作和生活。
                  </Text>
                </div>
                <div className="auth-story__panel-grid">
                  <Card className="auth-story__metric" bordered={false}>
                    <Text className="muted-text">今日日程</Text>
                    <Title level={3}>8</Title>
                  </Card>
                  <Card className="auth-story__metric" bordered={false}>
                    <Text className="muted-text">待办任务</Text>
                    <Title level={3}>12</Title>
                  </Card>
                  <Card className="auth-story__metric" bordered={false}>
                    <Text className="muted-text">冲突提醒</Text>
                    <Title level={3}>2</Title>
                  </Card>
                  <Card className="auth-story__metric auth-story__metric--wide" bordered={false}>
                    <Text className="muted-text">系统状态</Text>
                    <Title level={3}>稳定在线</Title>
                  </Card>
                </div>
              </div>
              <Space wrap size={10}>
                <Text className="auth-story__tag">日程</Text>
                <Text className="auth-story__tag">任务</Text>
                <Text className="auth-story__tag">计划</Text>
                <Text className="auth-story__tag">冲突</Text>
                <Text className="auth-story__tag">提醒</Text>
              </Space>
            </Space>
          </div>
        </Col>

        <Col xs={24} xl={13}>
          <Card className="auth-panel" bordered={false}>
            <Space direction="vertical" size={24} style={{ width: "100%" }}>
              <div>
                <Title level={2} className="auth-panel__title">
                  {title}
                </Title>
                <Text className="muted-text">{subtitle}</Text>
              </div>
              {children}
              <Divider className="auth-panel__divider" />
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
