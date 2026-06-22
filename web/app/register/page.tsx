"use client";

import { LockOutlined, MailOutlined, UserOutlined } from "@ant-design/icons";
import { App, Button, Form, Input } from "antd";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthLayout } from "@/components/auth-layout";
import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import type { AuthMeResponse, AuthSession } from "@/lib/types";

type RegisterForm = {
  invite_code: string;
  username: string;
  password: string;
  display_name?: string;
  email?: string;
};

export default function RegisterPage() {
  const router = useRouter();
  const { session, login } = useAuth();
  const { message } = App.useApp();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (session) {
      router.replace("/dashboard/today");
    }
  }, [router, session]);

  const handleFinish = async (values: RegisterForm) => {
    setSubmitting(true);
    try {
      const auth = await requestJson<{ access_token: string; token_type: "bearer"; user_id: string }>(
        "/auth/register-with-invite",
        {
          method: "POST",
          body: JSON.stringify(values),
        },
      );
      const me = await requestJson<AuthMeResponse>("/auth/me", {}, auth.access_token);
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
      message.success("注册成功");
      router.replace("/dashboard/today");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "注册失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="邀请码注册"
      subtitle="输入邀请码后创建账号，注册完成后即可进入你的专属日程空间。"
      ctaText="返回登录"
      ctaHref="/login"
    >
      <Form layout="vertical" size="large" onFinish={handleFinish} requiredMark={false}>
        <Form.Item name="invite_code" label="邀请码" rules={[{ required: true, message: "请输入邀请码" }]}>
          <Input placeholder="请输入邀请码" />
        </Form.Item>
        <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
          <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="new-password" />
        </Form.Item>
        <Form.Item name="display_name" label="显示名称">
          <Input placeholder="可选，注册后显示在驾驶舱中" />
        </Form.Item>
        <Form.Item name="email" label="邮箱">
          <Input prefix={<MailOutlined />} placeholder="可选" autoComplete="email" />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting} style={{ marginTop: 8 }}>
          创建账号
        </Button>
      </Form>
    </AuthLayout>
  );
}
