import { SectionPage } from "@/components/section-page";

export default function MessageLogsPage() {
  return (
    <SectionPage
      title="全局消息日志"
      description="owner 用于查看微信入站消息和出站回复日志，方便追踪通道行为。"
      badges={["消息", "日志", "owner"]}
      bullets={["查看消息收发明细", "过滤 conversation_id", "排查通道异常"]}
    />
  );
}
