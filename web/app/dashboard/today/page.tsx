"use client";

import { BarChartOutlined, ClockCircleOutlined, FireOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Card, Col, Row, Space, Statistic, Tag, Timeline, Typography } from "antd";

const { Title, Paragraph, Text } = Typography;

export default function TodayPage() {
  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <ThunderboltOutlined />
            今日计划
          </span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>今天的节奏</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里会展示固定日程、弹性任务、空闲时间和冲突提示。当前为前端骨架，后续接入后端接口后会变成实时数据。
          </Paragraph>
        </Space>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="section-card" bordered={false}>
            <Statistic title="今日日程" value={4} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="section-card" bordered={false}>
            <Statistic title="待安排任务" value={6} prefix={<BarChartOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="section-card" bordered={false}>
            <Statistic title="冲突提醒" value={1} prefix={<FireOutlined />} valueStyle={{ color: "var(--danger)" }} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card className="section-card" bordered={false} title="时间轴预览">
            <Timeline
              items={[
                {
                  color: "cyan",
                  children: (
                    <Space direction="vertical" size={2}>
                      <Text strong>09:00 - 10:00 团队同步</Text>
                      <Text className="muted-text">固定日程 / 已发送提醒</Text>
                    </Space>
                  ),
                },
                {
                  color: "gold",
                  children: (
                    <Space direction="vertical" size={2}>
                      <Text strong>10:30 - 12:00 写论文</Text>
                      <Text className="muted-text">弹性任务 / 可继续拆分</Text>
                    </Space>
                  ),
                },
                {
                  color: "green",
                  children: (
                    <Space direction="vertical" size={2}>
                      <Text strong>14:00 - 17:00 空闲窗口</Text>
                      <Text className="muted-text">可用于重新规划</Text>
                    </Space>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card className="section-card" bordered={false} title="Agent 建议">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Tag color="cyan">建议优先处理任务池中的高优先级事项</Tag>
              <Tag color="gold">若确认草案，系统会写入正式计划</Tag>
              <Tag color="blue">冲突处理后会同步更新提醒</Tag>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
