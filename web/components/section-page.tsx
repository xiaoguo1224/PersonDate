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
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <RocketOutlined />
            Web Dashboard
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>{title}</Title>
          <Paragraph className="muted-text" style={{ maxWidth: 900, marginBottom: 0 }}>
            {description}
          </Paragraph>
          <Space wrap>
            {badges.map((badge) => (
              <Tag key={badge} color="cyan">
                {badge}
              </Tag>
            ))}
          </Space>
          <Button type="primary" icon={<ArrowRightOutlined />} style={{ width: "fit-content" }}>
            后续接入数据
          </Button>
        </Space>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card className="section-card" bordered={false}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Title level={4} style={{ color: "var(--text-primary)", margin: 0 }}>
                功能占位
              </Title>
              {bullets.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text-secondary)" }}>
                  {bullets.map((bullet) => (
                    <li key={bullet} style={{ marginBottom: 8 }}>
                      {bullet}
                    </li>
                  ))}
                </ul>
              ) : (
                <Text className="muted-text">这里会接入后端接口、列表和筛选条件。</Text>
              )}
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="section-card" bordered={false}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Title level={4} style={{ color: "var(--text-primary)", margin: 0 }}>
                当前状态
              </Title>
              <div className="dashboard-empty">
                <Text className="muted-text">基础骨架已就绪</Text>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
