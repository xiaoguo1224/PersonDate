import { SectionPage } from "@/components/section-page";

export default function ModelConfigPage() {
  return (
    <SectionPage
      title="模型配置"
      description="用于配置 LLM 提示词、模型参数和 provider。敏感信息不会在页面中明文展示。"
      badges={["LLM", "配置", "安全"]}
      bullets={["配置模型名称和 base URL", "保持 API Key 隐藏", "后续接入后台校验和权限控制"]}
    />
  );
}
