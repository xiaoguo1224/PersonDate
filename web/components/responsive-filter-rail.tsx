"use client";

import { Space } from "antd";

export function ResponsiveFilterRail({
  children,
  compact = false,
}: Readonly<{
  children: React.ReactNode;
  compact?: boolean;
}>) {
  return (
    <Space
      className={compact ? "responsive-filter-rail responsive-filter-rail--compact" : "responsive-filter-rail"}
      wrap
      size={compact ? 10 : 12}
      style={{ width: "100%" }}
    >
      {children}
    </Space>
  );
}
