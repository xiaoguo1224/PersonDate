"use client";

import { LockOutlined, LoginOutlined, UserOutlined } from "@ant-design/icons";
import { App, Button, Form, Input, Typography } from "antd";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthLayout } from "@/components/auth-layout";
import { useAuth } from "@/components/auth-provider";
import { useLoginAnimation } from "@/hooks/use-login-animation";
import { requestJson } from "@/lib/api";
import type { AuthMeResponse, AuthSession } from "@/lib/types";

type LoginForm = {
  username: string;
  password: string;
};

export default function LoginPage() {
  const router = useRouter();
  const { session, login } = useAuth();
  const { message } = App.useApp();
  const [submitting, setSubmitting] = useState(false);

  useLoginAnimation();

  useEffect(() => {
    if (session) {
      router.replace("/dashboard/today");
    }
  }, [router, session]);

  const handleFinish = async (values: LoginForm) => {
    setSubmitting(true);
    try {
      const auth = await requestJson<{ access_token: string; token_type: "bearer"; user_id: string }>(
        "/api/auth/login",
        {
          method: "POST",
          body: JSON.stringify(values),
        },
      );
      const me = await requestJson<AuthMeResponse>("/api/auth/me", {}, auth.access_token);
      const nextSession: AuthSession = {
        accessToken: auth.access_token,
        tokenType: auth.token_type,
        userId: auth.user_id,
        role: me.role,
        username: me.username,
        displayName: me.display_name,
        email: me.email,
      };
      login(nextSession);
      message.success("登录成功");
      router.replace("/dashboard/today");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "登录失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="欢迎登录"
      subtitle="使用你的账号进入安排驾驶舱，查看安排、待办、提醒和 Agent 日志。"
      ctaText="前往注册"
      ctaHref="/register"
    >
      <Form layout="vertical" size="large" onFinish={handleFinish} requiredMark={false}>
        <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
          <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="current-password" />
        </Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          icon={<LoginOutlined />}
          loading={submitting}
          block
          style={{ marginTop: 8 }}
        >
          登录
        </Button>
      </Form>
      <Typography.Text className="muted-text">
        后端默认地址由 <code>NEXT_PUBLIC_API_BASE_URL</code> 控制，开发环境可指向 FastAPI 服务。
      </Typography.Text>
    </AuthLayout>
  );
}
