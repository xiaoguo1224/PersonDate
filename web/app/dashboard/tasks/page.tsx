import { SectionPage } from "@/components/section-page";

export default function TasksPage() {
  return (
    <SectionPage
      title="任务池"
      description="用于查看未完成任务、优先级、截止时间，以及触发 Agent 自动安排任务的入口。"
      badges={["任务", "优先级", "自动安排"]}
      bullets={["展示未安排任务列表", "支持创建、编辑、删除和完成任务", "预留触发 Agent 安排任务的操作按钮"]}
    />
  );
}
