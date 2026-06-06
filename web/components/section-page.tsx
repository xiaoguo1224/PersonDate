"use client";

import { ArrowRightOutlined, RocketOutlined } from "@ant-design/icons";
import { Button, Card, Col, Row, Space, Tag, Typography } from "antd";

const { Title, Paragraph, Text } = Typography;

export function SectionPage({
  title,
  description,
  badges = [],
  bullets = [],
}: Readonly<{
  title: string;
  description: string;
  badges?: string[];
  bullets?: string[];
}>) {
  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Row gutter={[24, 24]} align="stretch">
          <Col xs={24} lg={15}>
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <span className="hero-kicker">
                <RocketOutlined />
                Web Dashboard
              </span>
              <Title className="page-title" style={{ margin: 0 }}>
                {title}
              </Title>
              <Paragraph className="muted-text page-summary">{description}</Paragraph>
              <Space wrap>
                {badges.map((badge) => (
                  <Tag key={badge} color="blue" className="dashboard-chip">
                    {badge}
                  </Tag>
                ))}
              </Space>
              <Button type="primary" icon={<ArrowRightOutlined />} style={{ width: "fit-content" }}>
                继续接入数据
              </Button>
            </Space>
          </Col>
          <Col xs={24} lg={9}>
            <div className="section-page-preview">
              <Text className="muted-text">当前状态</Text>
              <Title level={3} className="section-page-preview__title">
                基础骨架已就绪
              </Title>
              <Text className="muted-text">
                这些页面会在统一视觉系统下继续接入真实数据和交互。
              </Text>
            </div>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card className="section-card" bordered={false} title="功能占位">
            {bullets.length > 0 ? (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {bullets.map((bullet) => (
                  <div key={bullet} className="section-page-bullet">
                    <span className="section-page-bullet__dot" />
                    <Text>{bullet}</Text>
                  </div>
                ))}
              </Space>
            ) : (
              <Text className="muted-text">这里会接入后端接口、列表和筛选条件。</Text>
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card className="section-card" bordered={false}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Text className="muted-text">下一步</Text>
              <Title level={4} style={{ margin: 0 }}>
                统一成更成熟的产品面貌
              </Title>
              <Text className="muted-text">
                继续把列表、表单、详情和空状态收口到同一套节奏上。
              </Text>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
