import { SectionPage } from "@/components/section-page";

export default function WechatStatusPage() {
  return (
    <SectionPage
      title="微信通道状态"
      description="owner 可查看 openclaw-weixin 及适配层的消息状态、连接状态和异常。"
      badges={["通道", "消息状态", "owner"]}
      bullets={["通道连接健康检查", "消息入站/出站统计", "后续对接 channel_message_logs"]}
    />
  );
}
