import { SectionPage } from "@/components/section-page";

export default function RemindersPage() {
  return (
    <SectionPage
      title="提醒任务"
      description="查看 pending / fired / failed 的提醒任务，后续可查看失败原因、取消提醒和手动测试触发。"
      badges={["PENDING", "FIRED", "FAILED"]}
      bullets={["展示提醒任务状态", "查看失败原因和重试信息", "支持取消提醒和手动测试触发"]}
    />
  );
}
