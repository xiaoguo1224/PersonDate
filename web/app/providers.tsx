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
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#7dd3fc",
          colorInfo: "#7dd3fc",
          colorSuccess: "#34d399",
          colorWarning: "#fbbf24",
          colorError: "#fb7185",
          borderRadius: 14,
          fontFamily:
            'var(--font-noto-sans-sc), "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <AuthProvider>{children}</AuthProvider>
    </ConfigProvider>
  );
}
