import { SectionPage } from "@/components/section-page";

export default function WechatBindingPage() {
  return (
    <SectionPage
      title="微信绑定"
      description="这里会提供绑定码、当前绑定状态和解绑入口，后续对接 openclaw-weixin 只是通道接入，不改变 Agent 主流程。"
      badges={["绑定码", "状态", "解绑"]}
      bullets={["生成微信绑定码", "查看当前绑定状态", "对接后端 channel_identities 接口"]}
    />
  );
}
