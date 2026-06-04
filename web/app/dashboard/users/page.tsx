import { SectionPage } from "@/components/section-page";

export default function UsersPage() {
  return (
    <SectionPage
      title="用户管理"
      description="owner 可在这里查看、启用和禁用用户，并管理成员权限。"
      badges={["owner", "RBAC", "用户管理"]}
      bullets={["查看成员列表", "启用/禁用账号", "查看成员微信绑定"]}
    />
  );
}
