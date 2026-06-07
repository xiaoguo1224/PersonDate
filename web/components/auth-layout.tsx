"use client";

import {
  ArrowRightOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button, Divider, Typography } from "antd";

const { Title, Text } = Typography;

export function AuthLayout({
  title,
  subtitle,
  ctaText,
  ctaHref,
  children,
}: Readonly<{
  title: string;
  subtitle: string;
  ctaText: string;
  ctaHref: string;
  children: React.ReactNode;
}>) {
  return (
    <main className="auth-root">
      {/* 背景装饰 — GSAP 负责运动 */}
      <div className="auth-bg-orb auth-bg-orb--blue" />
      <div className="auth-bg-orb auth-bg-orb--purple" />
      <div className="auth-bg-grid" />

      <div className="auth-container">
        <div className="auth-card">
          {/* 顶部品牌标识 */}
          <div className="auth-card__brand">
            <span className="auth-card__icon">
              <SafetyCertificateOutlined />
            </span>
            <span className="auth-card__name">Schedule Agent</span>
          </div>

          {/* 内容区 */}
          <div className="auth-card__body">
            <div className="auth-card__header">
              <Title level={2} className="auth-card__title">
                {title}
              </Title>
              <Text className="auth-card__subtitle">{subtitle}</Text>
            </div>
            {children}
          </div>

          {/* 底部切换 */}
          <Divider className="auth-card__divider" />
          <div className="auth-card__footer">
            <Text className="auth-card__footer-text">
              {ctaText === "前往注册" ? "还没有账号？" : "已有账号？"}
            </Text>
            <Button type="text" icon={<ArrowRightOutlined />} href={ctaHref}>
              {ctaText}
            </Button>
          </div>
        </div>

        {/* 页脚 */}
        <div className="auth-footer">
          <Text type="secondary">
            微信智能安排规划 Agent &mdash; 把自然语言变成可执行的安排与提醒
          </Text>
        </div>
      </div>
    </main>
  );
}
