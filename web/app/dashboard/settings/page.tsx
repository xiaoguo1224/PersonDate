import { SectionPage } from "@/components/section-page";

export default function SettingsPage() {
  return (
    <SectionPage
      title="系统设置"
      description="用于管理默认时区、提醒策略、计划推送时间和系统级配置。"
      badges={["时区", "提醒", "系统配置"]}
      bullets={["默认时区和工作时间段", "每日计划推送配置", "系统设置的权限控制"]}
    />
  );
}
