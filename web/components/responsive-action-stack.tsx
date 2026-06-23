"use client";

import { Button, Space, type ButtonProps } from "antd";
import { cloneElement, isValidElement } from "react";

function enhanceAction(node: React.ReactNode, compact: boolean) {
  if (!compact || !isValidElement(node) || node.type !== Button) {
    return node;
  }

  const button = node as React.ReactElement<{ style?: React.CSSProperties }>;
  const nextStyle = {
    ...(button.props.style ?? {}),
    width: "100%",
  };

  return cloneElement(button as React.ReactElement<ButtonProps>, {
    block: true,
    style: nextStyle,
  });
}

export function ResponsiveActionStack({
  primary,
  secondary,
  compact = false,
}: Readonly<{
  primary?: React.ReactNode;
  secondary?: React.ReactNode[];
  compact?: boolean;
}>) {
  const secondaryActions = secondary?.filter(Boolean) ?? [];

  if (!primary && secondaryActions.length === 0) {
    return null;
  }

  return (
    <Space
      className={compact ? "responsive-action-stack responsive-action-stack--compact" : "responsive-action-stack"}
      direction={compact ? "vertical" : "horizontal"}
      size={compact ? 10 : 12}
      wrap={!compact}
    >
      {primary ? enhanceAction(primary, compact) : null}
      {secondaryActions.map((action, index) => (
        <span key={index} className="responsive-action-stack__secondary">
          {enhanceAction(action, compact)}
        </span>
      ))}
    </Space>
  );
}
