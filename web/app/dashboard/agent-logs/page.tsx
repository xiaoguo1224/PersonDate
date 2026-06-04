import { SectionPage } from "@/components/section-page";

export default function AgentLogsPage() {
  return (
    <SectionPage
      title="Agent 日志"
      description="展示自然语言输入、意图识别、工具调用和最终回复，方便排查 Agent 行为。"
      badges={["工具调用", "trace", "pending_state"]}
      bullets={["查看每次 Debug 调试记录", "查看 tool_calls / tool_results", "后续可按会话和时间过滤"]}
    />
  );
}
