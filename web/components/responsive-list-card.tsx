"use client";

import { Card, Space, Tag, Typography } from "antd";

import { ResponsiveActionStack } from "@/components/responsive-action-stack";

const { Text } = Typography;

export function ResponsiveListCard({
  title,
  meta,
  tags,
  description,
  details,
  actions,
  accent,
  compact = false,
}: Readonly<{
  title: React.ReactNode;
  meta?: React.ReactNode;
  tags?: React.ReactNode[];
  description?: React.ReactNode;
  details?: React.ReactNode;
  actions?: React.ReactNode[];
  accent?: string;
  compact?: boolean;
}>) {
  return (
    <Card
      className={compact ? "section-card responsive-list-card responsive-list-card--compact" : "section-card responsive-list-card"}
      variant="borderless"
    >
      <div
        className="responsive-list-card__accent"
        style={accent ? { background: accent } : undefined}
      />
      <Space direction="vertical" size={compact ? 8 : 10} style={{ width: "100%" }}>
        <Space direction="vertical" size={compact ? 2 : 4} style={{ width: "100%" }}>
          <Text strong className="responsive-list-card__title">
            {title}
          </Text>
          {meta ? <Text className="muted-text responsive-list-card__meta">{meta}</Text> : null}
        </Space>

        {tags?.length ? (
          <Space wrap size={6}>
            {tags.map((tag, index) => (
              <Tag key={index} className="responsive-list-card__tag">
                {tag}
              </Tag>
            ))}
          </Space>
        ) : null}

        {description ? <div className="responsive-list-card__description">{description}</div> : null}
        {details ? <div className="responsive-list-card__details">{details}</div> : null}

        {actions?.length ? (
          <ResponsiveActionStack primary={actions[0]} secondary={actions.slice(1)} compact={compact} />
        ) : null}
      </Space>
    </Card>
  );
}
