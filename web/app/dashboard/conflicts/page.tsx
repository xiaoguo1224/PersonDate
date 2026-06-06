"use client";

import { Alert, Card, Empty, List, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime, type ConflictItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type ConflictListResponse = {
  items: ConflictItem[];
};

function getSeverityColor(severity: string) {
  if (severity === "high") return "red";
  if (severity === "medium") return "gold";
  return "blue";
}

function getStatusColor(status: string) {
  if (status === "resolved") return "green";
  if (status === "ignored") return "default";
  return "orange";
}

function ConflictsLoading() {
  return (
    <div className="dashboard-empty">
      <Spin size="large" tip="正在加载冲突事项..." />
    </div>
  );
}

function ConflictsError({ message }: Readonly<{ message: string }>) {
  return <Alert type="error" showIcon message="加载冲突事项失败" description={message} />;
}

function ConflictEmpty() {
  return (
    <div className="dashboard-empty">
      <Empty description="当前没有冲突事项" />
    </div>
  );
}

export default function ConflictsPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      setError("请先登录后查看冲突事项");
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    requestJson<ConflictListResponse>("/api/conflicts?status=open", {}, accessToken)
      .then((result) => {
        if (alive) {
          setConflicts(result.items);
        }
      })
      .catch((caughtError: unknown) => {
        if (alive) {
          setError(caughtError instanceof Error ? caughtError.message : "未知错误");
        }
      })
      .finally(() => {
        if (alive) {
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [accessToken]);

  const summary = useMemo(() => {
    const high = conflicts.filter((item) => item.severity === "high").length;
    const medium = conflicts.filter((item) => item.severity === "medium").length;
    const open = conflicts.filter((item) => item.status === "open").length;
    return {
      total: conflicts.length,
      high,
      medium,
      open,
    };
  }, [conflicts]);

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">冲突事项</span>
          <Title style={{ color: "var(--text-primary)", margin: 0 }}>冲突总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            这里已经接入后端冲突列表。后续可在此基础上补充忽略、解决和重新规划入口。
          </Paragraph>
          <Space wrap>
            <Tag color="red">{summary.high} 个高优先级</Tag>
            <Tag color="gold">{summary.medium} 个中优先级</Tag>
            <Tag color="orange">{summary.open} 个待处理</Tag>
            <Tag color="cyan">{summary.total} 条记录</Tag>
          </Space>
        </Space>
      </Card>

      {error ? <ConflictsError message={error} /> : null}

      {loading ? (
        <ConflictsLoading />
      ) : conflicts.length ? (
        <Card className="section-card" bordered={false} title="冲突列表">
          <List
            itemLayout="vertical"
            dataSource={conflicts}
            renderItem={(conflict) => (
              <List.Item key={conflict.id}>
                <Card size="small" bordered={false} style={{ background: "rgba(255,255,255,0.04)" }}>
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap>
                      <Text strong>{conflict.title}</Text>
                      <Tag color={getSeverityColor(conflict.severity)}>{conflict.severity}</Tag>
                      <Tag color={getStatusColor(conflict.status)}>{conflict.status}</Tag>
                      <Tag color="cyan">{conflict.conflict_type}</Tag>
                    </Space>
                    {conflict.description ? <Text className="muted-text">{conflict.description}</Text> : null}
                    {conflict.suggestion ? <Text className="muted-text">建议：{conflict.suggestion}</Text> : null}
                    <Space wrap>
                      <Tag>检测时间 {formatDateTime(conflict.detected_at, timezone)}</Tag>
                      {conflict.related_item_ids?.length ? (
                        <Tag>{conflict.related_item_ids.length} 个相关事项</Tag>
                      ) : null}
                    </Space>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        </Card>
      ) : (
        <ConflictEmpty />
      )}
    </Space>
  );
}
