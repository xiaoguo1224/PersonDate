import { SectionPage } from "@/components/section-page";

export default function ConflictsPage() {
  return (
    <SectionPage
      title="冲突事项"
      description="这里会显示冲突列表、严重程度、相关事项和处理建议，帮助用户快速判断是否需要重新规划。"
      badges={["冲突", "建议", "重新规划"]}
      bullets={["展示 open / resolved 冲突", "支持忽略、解决和重新规划", "后续会接入冲突检测触发入口"]}
    />
  );
}
