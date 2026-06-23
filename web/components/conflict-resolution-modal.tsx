"use client";

import { EditOutlined, SwapOutlined, WarningOutlined } from "@ant-design/icons";
import { Button, Card, Modal, Space, Spin, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";

import { formatRange, loadScheduledItem, type ConflictItem, type ScheduledItem } from "@/lib/dashboard";

const { Text } = Typography;

type ConflictResolutionModalProps = Readonly<{
  open: boolean;
  conflicts: ConflictItem[];
  currentItemId: string;
  onEditItem: (item: ScheduledItem) => void;
  onIgnore: () => void;
  onClose: () => void;
  accessToken: string;
  timezone?: string;
}>;

export default function ConflictResolutionModal({
  open,
  conflicts,
  currentItemId,
  onEditItem,
  onIgnore,
  onClose,
  accessToken,
  timezone,
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
      wrapClassName="conflict-resolution-modal"
      footer={
        <div className="conflict-resolution-modal__footer">
          <Button onClick={onClose}>关闭</Button>
          <Button type="primary" onClick={onIgnore}>
            忽略冲突
          </Button>
        </div>
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
              className="conflict-resolution-modal__card"
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
                  <div className="conflict-resolution-modal__item">
                    <div className="conflict-resolution-modal__item-info">
                      <Text strong>{current.title}</Text>
                      <br />
                      <Text className="muted-text" style={{ fontSize: 12 }}>
                        {formatRange(current.start_time, current.end_time, timezone)}
                      </Text>
                    </div>
                    {current.id === currentItemId ? (
                      <Tag color="blue">当前项</Tag>
                    ) : null}
                  </div>
                ) : null}
                {other ? (
                  <div className="conflict-resolution-modal__item">
                    <div className="conflict-resolution-modal__item-info">
                      <Text strong>{other.title}</Text>
                      <br />
                      <Text className="muted-text" style={{ fontSize: 12 }}>
                        {formatRange(other.start_time, other.end_time, timezone)}
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
                <div className="conflict-resolution-modal__actions">
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
