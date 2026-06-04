import { SectionPage } from "@/components/section-page";

export default function CalendarPage() {
  return (
    <SectionPage
      title="日历视图"
      description="月 / 周 / 日视图会在这里展示 calendar_events 与 plan_items。后续接入 FullCalendar 或自定义时间轴。"
      badges={["日程", "计划项", "编辑/删除"]}
      bullets={["展示月视图、周视图和日视图", "支持手动创建、修改和删除日程", "点击事件查看详情和冲突信息"]}
    />
  );
}
