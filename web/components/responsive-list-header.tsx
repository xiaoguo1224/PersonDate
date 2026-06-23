"use client";

import { Card, Space, Tag, Typography } from "antd";

const { Title, Paragraph } = Typography;

export function ResponsiveListHeader({
  kicker,
  title,
  description,
  stats,
  actions,
}: Readonly<{
  kicker?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  stats?: React.ReactNode[];
  actions?: React.ReactNode;
}>) {
  return (
    <Card className="section-card dashboard-hero responsive-list-header" variant="borderless">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div className="responsive-list-header__top">
          <Space direction="vertical" size={12} className="responsive-list-header__copy">
            {kicker ? <span className="hero-kicker">{kicker}</span> : null}
            <Title level={2} className="responsive-list-header__title" style={{ margin: 0 }}>
              {title}
            </Title>
            {description ? (
              <Paragraph className="muted-text responsive-list-header__description">
                {description}
              </Paragraph>
            ) : null}
          </Space>

          {actions ? <div className="responsive-list-header__actions">{actions}</div> : null}
        </div>

        {stats?.length ? (
          <Space wrap size={8} className="responsive-list-header__stats">
            {stats.map((stat, index) => (
              <Tag key={index} className="responsive-list-header__stat" color="blue">
                {stat}
              </Tag>
            ))}
          </Space>
        ) : null}
      </Space>
    </Card>
  );
}
