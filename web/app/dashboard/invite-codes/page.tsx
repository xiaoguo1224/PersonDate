import { SectionPage } from "@/components/section-page";

export default function InviteCodesPage() {
  return (
    <SectionPage
      title="邀请码管理"
      description="owner 可以在这里生成、查看和管理邀请码，服务新成员注册流程。"
      badges={["邀请码", "注册", "owner"]}
      bullets={["生成邀请码", "设置有效期和最大使用次数", "查看邀请码使用记录"]}
    />
  );
}
