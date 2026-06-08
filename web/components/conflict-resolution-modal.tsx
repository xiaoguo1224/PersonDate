"use client";

import { EditOutlined, SwapOutlined, WarningOutlined } from "@ant-design/icons";
import { Button, Card, Modal, Space, Spin, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";

import { loadScheduledItem, type ConflictItem, type ScheduledItem } from "@/lib/dashboard";

const { Text } = Typography;

type ConflictResolutionModalProps = Readonly<{
  open: boolean;
  conflicts: ConflictItem[];
  currentItemId: string;
  onEditItem: (item: ScheduledItem) => void;
  onIgnore: () => void;
  onClose: () => void;
  accessToken: string;
}>;

export default function ConflictResolutionModal({
  open,
  conflicts,
  currentItemId,
  onEditItem,
  onIgnore,
  onClose,
  accessToken,
}: ConflictResolutionModalProps) {
  const [loading, setLoading] = useState(false);
  const [conflictPairs, setConflictPairs] = useState<Array<{
    conflict: ConflictItem;
    current: ScheduledItem | null;
    other: ScheduledItem | null;
  }>>([]);

  const loadConflictItems = useCallback(async () => {
    if (!open || conflicts.length === 0) {
      setConflictPairs([]);
      return;
    }
    setLoading(true);
    try {
      const pairs = await Promise.all(
        conflicts.map(async (conflict) => {
          const ids = conflict.related_item_ids;
          if (!ids) return { conflict, current: null, other: null };
          const currentId = ids.current;
          const otherId = ids.other;
          const [currentItem, otherItem] = await Promise.all([
            currentId ? loadScheduledItem(currentId, accessToken).catch(() => null) : Promise.resolve(null),
            otherId ? loadScheduledItem(otherId, accessToken).catch(() => null) : Promise.resolve(null),
          ]);
          return { conflict, current: currentItem, other: otherItem };
        }),
      );
      setConflictPairs(pairs);
    } finally {
      setLoading(false);
    }
  }, [open, conflicts, accessToken]);

  useEffect(() => {
    void loadConflictItems();
  }, [loadConflictItems]);

  return (
    <Modal
      title={
        <Space>
          <WarningOutlined style={{ color: "#faad14" }} />
          <span>检测到时间冲突</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={
        <Button onClick={onIgnore}>忽略冲突</Button>
      }
      width={560}
      destroyOnHidden
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin />
        </div>
      ) : (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Text className="muted-text">
            以下安排存在时间重叠，请选择修改其中一项的时间来解决冲突。
          </Text>
          {conflictPairs.map(({ conflict, current, other }) => (
            <Card
              key={conflict.id}
              size="small"
              style={{ background: "rgba(255,255,255,0.04)" }}
            >
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Space wrap>
                  <Tag color="red">时间重叠</Tag>
                  <Tag color={conflict.severity === "high" ? "red" : "gold"}>
                    {conflict.severity}
                  </Tag>
                </Space>
                {current ? (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <Text strong>{current.title}</Text>
                      <br />
                      <Text className="muted-text" style={{ fontSize: 12 }}>
                        {formatTimeRange(current.start_time, current.end_time)}
                      </Text>
                    </div>
                    {current.id === currentItemId ? (
                      <Tag color="blue">当前项</Tag>
                    ) : null}
                  </div>
                ) : null}
                {other ? (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <Text strong>{other.title}</Text>
                      <br />
                      <Text className="muted-text" style={{ fontSize: 12 }}>
                        {formatTimeRange(other.start_time, other.end_time)}
                      </Text>
                    </div>
                    <Button
                      type="link"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => onEditItem(other)}
                    >
                      修改时间
                    </Button>
                  </div>
                ) : null}
                <div style={{ display: "flex", gap: 8 }}>
                  {current ? (
                    <Button
                      size="small"
                      icon={<SwapOutlined />}
                      onClick={() => onEditItem(current)}
                    >
                      修改「{current.title}」
                    </Button>
                  ) : null}
                  {other ? (
                    <Button
                      size="small"
                      icon={<SwapOutlined />}
                      onClick={() => onEditItem(other)}
                    >
                      修改「{other.title}」
                    </Button>
                  ) : null}
                </div>
              </Space>
            </Card>
          ))}
        </Space>
      )}
    </Modal>
  );
}

function formatTimeRange(start: string, end: string): string {
  const fmt: Intl.DateTimeFormatOptions = {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  };
  const s = new Date(start).toLocaleString("zh-CN", fmt);
  const e = new Date(end).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${s} - ${e}`;
}
