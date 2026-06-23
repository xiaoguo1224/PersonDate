"use client";

import { Card, Space } from "antd";

import { ResponsiveActionStack } from "@/components/responsive-action-stack";
import { ResponsiveListHeader } from "@/components/responsive-list-header";

export function ResponsiveListShell({
  kicker,
  title,
  description,
  stats,
  primaryAction,
  secondaryActions,
  children,
  footer,
  className,
}: Readonly<{
  kicker?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  stats?: React.ReactNode[];
  primaryAction?: React.ReactNode;
  secondaryActions?: React.ReactNode[];
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}>) {
  const headerActions =
    primaryAction || (secondaryActions?.length ?? 0) > 0 ? (
      <ResponsiveActionStack primary={primaryAction} secondary={secondaryActions} />
    ) : undefined;

  return (
    <div
      className={["responsive-list-shell", className].filter(Boolean).join(" ")}
      style={{ width: "100%" }}
    >
      <ResponsiveListHeader
        kicker={kicker}
        title={title}
        description={description}
        stats={stats}
        actions={headerActions}
      />
      <Card className="section-card responsive-list-shell__body" variant="borderless">
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          {children}
        </Space>
      </Card>
      {footer ? <div className="responsive-list-shell__footer">{footer}</div> : null}
    </div>
  );
}
