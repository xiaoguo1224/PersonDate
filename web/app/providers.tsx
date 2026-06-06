"use client";

import { ConfigProvider, theme } from "antd";

import { AuthProvider } from "@/components/auth-provider";

export default function Providers({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#3b82f6",
          colorInfo: "#3b82f6",
          colorSuccess: "#10b981",
          colorWarning: "#f59e0b",
          colorError: "#ef4444",
          colorBgBase: "#f8fafc",
          colorBgContainer: "#ffffff",
          colorBgElevated: "#ffffff",
          colorTextBase: "#0f172a",
          borderRadius: 16,
          fontFamily:
            'var(--font-noto-sans-sc), "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <AuthProvider>{children}</AuthProvider>
    </ConfigProvider>
  );
}
