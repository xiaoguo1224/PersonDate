"use client";

import { Tag, Typography } from "antd";

const { Text } = Typography;

export function ResponsiveListFooter({
  pagination,
  helperText,
  loading = false,
}: Readonly<{
  pagination?: React.ReactNode;
  helperText?: React.ReactNode;
  loading?: boolean;
}>) {
  if (!pagination && !helperText && !loading) {
    return null;
  }

  return (
    <div className="responsive-list-footer">
      <div className="responsive-list-footer__helper">
        {helperText ? <Text className="muted-text">{helperText}</Text> : null}
        {loading ? <Tag color="processing">加载中</Tag> : null}
      </div>
      {pagination ? <div className="responsive-list-footer__pagination">{pagination}</div> : null}
    </div>
  );
}
