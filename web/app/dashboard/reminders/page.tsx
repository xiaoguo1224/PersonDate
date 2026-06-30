"use client";

import { BellOutlined, SearchOutlined } from "@ant-design/icons";
import { App, Alert, Button, Card, Col, Collapse, DatePicker, Empty, Grid, Input, InputNumber, Modal, Pagination, Row, Select, Space, Spin, Tabs, Tag, Typography } from "antd";
import { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { ResponsiveFilterRail } from "@/components/responsive-filter-rail";
import { ResponsiveListCard } from "@/components/responsive-list-card";
import { formatClock, formatDateTime, getDateKey, type ReminderItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type { UserSettingsResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

type ReminderListResponse = {
  items: ReminderItem[];
  total: number;
  page: number;
  page_size: number;
};

type ReminderDisplayEntry =
  | {
      kind: "single";
      key: string;
      reminder: ReminderItem;
    }
  | {
      kind: "group";
      key: string;
      title: string;
      triggerClock: string;
      dateSummary: string;
      status: string;
      items: ReminderItem[];
    };

function getStatusColor(status: string) {
  if (status === "fired") return "green";
  if (status === "failed") return "red";
  if (status === "canceled") return "default";
  return "orange";
}

function formatMonthDay(value: string, timezone: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: timezone,
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

function buildReminderGroupKey(reminder: ReminderItem, timezone: string) {
  if (reminder.target_type !== "scheduled_item" || !reminder.source_task_id) {
    return null;
  }
  return [
    reminder.source_task_id,
    reminder.status,
    formatClock(reminder.trigger_time, timezone),
  ].join("::");
}

export default function RemindersPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const { modal, message } = App.useApp();
  const screens = Grid.useBreakpoint();
  const isMobile = screens.md === false;
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDate, setFilterDate] = useState<Dayjs | null>(null);
  const [keyword, setKeyword] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [sortOrder, setSortOrder] = useState<"trigger_time_asc" | "trigger_time_desc">("trigger_time_asc");
  const [defaultRemindBefore, setDefaultRemindBefore] = useState(0);
  const [savingDefault, setSavingDefault] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [adjustTarget, setAdjustTarget] = useState<ReminderItem | null>(null);
  const [adjustValue, setAdjustValue] = useState(0);
  const [adjusting, setAdjusting] = useState(false);

  const fetchReminders = useCallback((p?: number, ps?: number) => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const currentPage = p ?? page;
    const currentPageSize = ps ?? pageSize;
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (searchKeyword) params.set("keyword", searchKeyword);
    params.set("sort_order", sortOrder);
    params.set("page", String(currentPage));
    params.set("page_size", String(currentPageSize));
    requestJson<ReminderListResponse>(`/reminders?${params}`, {}, accessToken)
      .then((result) => {
        setReminders(result.items);
        setTotal(result.total);
      })
      .catch((caughtError: unknown) => {
        setError(caughtError instanceof Error ? caughtError.message : "未知错误");
      })
      .finally(() => setLoading(false));
  }, [accessToken, statusFilter, searchKeyword, sortOrder, page, pageSize]);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    fetchReminders();
  }, [accessToken, fetchReminders]);

  useEffect(() => {
    if (!accessToken) return;
    requestJson<UserSettingsResponse>(
      "/me/settings",
      {},
      accessToken,
    ).then((result) => {
      const mins = result.default_remind_before_minutes;
      if (mins !== undefined && mins !== null) setDefaultRemindBefore(mins);
    }).catch(() => {});
  }, [accessToken]);

  const handleSaveDefault = async () => {
    if (!accessToken) return;
    setSavingDefault(true);
    try {
      await requestJson("/me/settings", {
        method: "PATCH",
        body: JSON.stringify({ default_remind_before_minutes: defaultRemindBefore }),
      }, accessToken);
      message.success("默认提醒时间已更新");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSavingDefault(false);
    }
  };

  const handleCancel = async (reminder: ReminderItem) => {
    if (!accessToken) return;
    modal.confirm({
      title: "取消提醒",
      content: `确定要取消"${reminder.title}"的提醒吗？`,
      okText: "取消提醒",
      okType: "danger",
      cancelText: "保持开启",
      onOk: async () => {
        try {
          await requestJson(`/reminders/${reminder.id}/cancel`, { method: "PATCH" }, accessToken);
          message.success("提醒已取消");
          fetchReminders(page);
        } catch (err) {
          message.error(err instanceof Error ? err.message : "操作失败");
        }
      },
    });
  };

  const handleReactivate = async (reminder: ReminderItem) => {
    if (!accessToken) return;

    // 检查是否已过期
    const triggerTime = new Date(reminder.trigger_time);
    const now = new Date();
    const isExpired = triggerTime <= now;

    if (isExpired) {
      // 过期的提醒需要选择新的触发时间
      modal.confirm({
        title: "重新激活提醒",
        content: "该提醒已过期，请设置新的触发时间",
        okText: "激活",
        cancelText: "取消",
        onOk: async () => {
          // 默认设置为1小时后
          const newTime = new Date(Date.now() + 60 * 60 * 1000).toISOString();
          try {
            await requestJson(`/reminders/${reminder.id}/reactivate`, {
              method: "PATCH",
              body: JSON.stringify({ trigger_time: newTime }),
            }, accessToken);
            message.success("提醒已重新激活，将在1小时后触发");
            fetchReminders(page);
          } catch (err) {
            message.error(err instanceof Error ? err.message : "操作失败");
          }
        },
      });
    } else {
      // 未过期的提醒直接激活
      try {
        await requestJson(`/reminders/${reminder.id}/reactivate`, { method: "PATCH" }, accessToken);
        message.success("提醒已重新激活");
        fetchReminders(page);
      } catch (err) {
        message.error(err instanceof Error ? err.message : "操作失败");
      }
    }
  };

  const handleAdjustOpen = (reminder: ReminderItem) => {
    setAdjustTarget(reminder);
    setAdjustValue(reminder.remind_before_minutes ?? 0);
  };

  const handleAdjustConfirm = async () => {
    if (!accessToken || !adjustTarget) return;
    setAdjusting(true);
    try {
      await requestJson(`/reminders/${adjustTarget.id}/adjust`, {
        method: "PATCH",
        body: JSON.stringify({ remind_before_minutes: adjustValue }),
      }, accessToken);
      message.success("提醒时间已调整");
      setAdjustTarget(null);
      fetchReminders(page);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "调整失败");
    } finally {
      setAdjusting(false);
    }
  };

  const filteredReminders = useMemo(() => {
    if (!filterDate) return reminders;
    const dateKey = filterDate.format("YYYY-MM-DD");
    return reminders.filter((r) => {
      const triggerKey = getDateKey(r.trigger_time, timezone);
      return triggerKey === dateKey;
    });
  }, [reminders, filterDate, timezone]);

  const summary = useMemo(() => {
    const pending = reminders.filter((item) => item.status === "pending").length;
    const fired = reminders.filter((item) => item.status === "fired").length;
    const failed = reminders.filter((item) => item.status === "failed").length;
    return { total: reminders.length, pending, fired, failed };
  }, [reminders]);

  const displayEntries = useMemo<ReminderDisplayEntry[]>(() => {
    const buckets: Array<{ key: string; items: ReminderItem[]; groupable: boolean }> = [];
    const groupIndex = new Map<string, number>();

    for (const reminder of filteredReminders) {
      const groupKey = buildReminderGroupKey(reminder, timezone);
      if (!groupKey) {
        buckets.push({
          key: reminder.id,
          items: [reminder],
          groupable: false,
        });
        continue;
      }

      const existingIndex = groupIndex.get(groupKey);
      if (existingIndex === undefined) {
        groupIndex.set(groupKey, buckets.length);
        buckets.push({
          key: groupKey,
          items: [reminder],
          groupable: true,
        });
        continue;
      }
      buckets[existingIndex].items.push(reminder);
    }

    return buckets.map((bucket) => {
      if (!bucket.groupable || bucket.items.length === 1) {
        return {
          kind: "single",
          key: bucket.items[0].id,
          reminder: bucket.items[0],
        };
      }

      const [firstItem] = bucket.items;
      return {
        kind: "group",
        key: bucket.key,
        title: firstItem.title,
        triggerClock: formatClock(firstItem.trigger_time, timezone),
        dateSummary: bucket.items
          .map((item) => formatMonthDay(item.trigger_time, timezone))
          .join("、"),
        status: firstItem.status,
        items: bucket.items,
      };
    });
  }, [filteredReminders, timezone]);

  const renderReminderActions = (reminder: ReminderItem, size: "small" | "middle" = "small") => {
    return [
      reminder.status === "pending" ? (
        <Button key="adjust" size={size} onClick={() => handleAdjustOpen(reminder)}>
          调整提醒时间
        </Button>
      ) : null,
      reminder.status === "pending" ? (
        <Button key="cancel" danger size={size} onClick={() => void handleCancel(reminder)}>
          取消提醒
        </Button>
      ) : null,
      reminder.status === "canceled" && new Date(reminder.trigger_time) > new Date() ? (
        <Button key="reactivate" type="primary" size={size} onClick={() => void handleReactivate(reminder)}>
          重新激活
        </Button>
      ) : null,
    ].filter(Boolean) as React.ReactNode[];
  };

  const renderGroupReminderDetail = (reminder: ReminderItem) => {
    return (
      <Card key={reminder.id} size="small" bordered={false} style={{ background: "rgba(15, 23, 42, 0.03)" }}>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Space wrap>
            <Text strong>{formatDateTime(reminder.trigger_time, timezone)}</Text>
            <Tag color={getStatusColor(reminder.status)}>{reminder.status}</Tag>
            <Tag color="cyan">{reminder.target_type}</Tag>
          </Space>
          {reminder.original_time ? (
            <Text className="muted-text">
              原定时间：{formatDateTime(reminder.original_time, timezone)}
              {" "}({formatClock(reminder.original_time, timezone)})
            </Text>
          ) : null}
          <Text className="muted-text">
            提前提醒：{reminder.remind_before_minutes ?? 0} 分钟
          </Text>
          {reminder.fired_at ? (
            <Text className="muted-text">
              触发于：{formatDateTime(reminder.fired_at, timezone)}
            </Text>
          ) : null}
          {reminder.error_message ? (
            <Text type="danger" className="muted-text">
              错误：{reminder.error_message}
            </Text>
          ) : null}
          <Text className="muted-text">会话：{reminder.conversation_id ?? "无"}</Text>
          <Space wrap>
            <Tag>重试 {reminder.retry_count}/{reminder.max_retries}</Tag>
            <Tag>目标 {reminder.target_id}</Tag>
            {renderReminderActions(reminder)}
          </Space>
        </Space>
      </Card>
    );
  };

  const renderGroupedReminder = (entry: Extract<ReminderDisplayEntry, { kind: "group" }>, mobile: boolean) => {
    const summaryLabel = (
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space wrap>
          <Text strong>{entry.title}</Text>
          <Tag color={getStatusColor(entry.status)}>{entry.status}</Tag>
          <Tag color="blue">{entry.items.length} 条同时间提醒</Tag>
        </Space>
        <Text className="muted-text">
          触发时间：{entry.triggerClock} · 日期：{entry.dateSummary}
        </Text>
      </Space>
    );

    const collapse = (
      <Collapse
        ghost
        items={[
          {
            key: entry.key,
            label: summaryLabel,
            children: (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {entry.items.map((item) => renderGroupReminderDetail(item))}
              </Space>
            ),
          },
        ]}
      />
    );

    if (mobile) {
      return (
        <Card key={entry.key} className="section-card" variant="borderless">
          {collapse}
        </Card>
      );
    }

    return (
      <Col xs={24} lg={12} key={entry.key}>
        <Card className="section-card" variant="borderless">
          {collapse}
        </Card>
      </Col>
    );
  };

  const mobileCards = (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {displayEntries.map((entry) => {
        if (entry.kind === "group") {
          return renderGroupedReminder(entry, true);
        }
        const reminder = entry.reminder;
        return (
          <ResponsiveListCard
            key={reminder.id}
            compact
            accent={getStatusColor(reminder.status) === "green" ? "#22c55e" : getStatusColor(reminder.status) === "red" ? "#ef4444" : "#f59e0b"}
            title={reminder.title}
            meta={`${formatDateTime(reminder.trigger_time, timezone)} · ${reminder.status}`}
            tags={[
              reminder.target_type,
              `重试 ${reminder.retry_count}/${reminder.max_retries}`,
            ]}
            description={
              <Typography.Paragraph className="muted-text responsive-list-card__description-text" ellipsis={{ rows: 2, expandable: false }}>
                {reminder.original_time ? `原定时间：${formatDateTime(reminder.original_time, timezone)} · ` : ""}
                提前提醒 {reminder.remind_before_minutes ?? 0} 分钟
              </Typography.Paragraph>
            }
            details={
              <Space direction="vertical" size={6} style={{ width: "100%" }}>
                {reminder.fired_at ? (
                  <Text className="muted-text responsive-list-card__description-text">
                    触发于：{formatDateTime(reminder.fired_at, timezone)}
                  </Text>
                ) : null}
                {reminder.conversation_id ? (
                  <Text className="muted-text responsive-list-card__description-text">
                    会话：{reminder.conversation_id}
                  </Text>
                ) : (
                  <Text className="muted-text responsive-list-card__description-text">会话：无</Text>
                )}
                {reminder.error_message ? (
                  <Text type="danger" className="muted-text responsive-list-card__description-text">
                    错误：{reminder.error_message}
                  </Text>
                ) : null}
              </Space>
            }
            actions={renderReminderActions(reminder, "middle")}
          />
        );
      })}
    </Space>
  );

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" variant="borderless">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">
            <BellOutlined />
            提醒任务
          </span>
          <Title style={{ margin: 0 }}>提醒任务总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            管理提醒任务：按天筛选、取消提醒、设置默认提前时间。
          </Paragraph>
          <Space wrap>
            <Tag color="orange">{summary.pending} 个待触发</Tag>
            <Tag color="green">{summary.fired} 个已触发</Tag>
            <Tag color="red">{summary.failed} 个失败</Tag>
            <Tag color="cyan">{summary.total} 条记录</Tag>
          </Space>
        </Space>
      </Card>

      <Card className="section-card" variant="borderless" title="我的默认提醒设置">
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text className="muted-text">
            新建安排时的默认提前提醒时间（可在账号设置中同步修改）
          </Text>
          <Space>
            <Space.Compact>
              <InputNumber
                min={0}
                max={120}
                value={defaultRemindBefore}
                onChange={(v) => setDefaultRemindBefore(v ?? 0)}
                style={{ width: 120 }}
              />
              <span style={{ padding: "0 8px", lineHeight: "32px" }}>分钟</span>
            </Space.Compact>
            <Button
              type="primary"
              size="small"
              onClick={() => void handleSaveDefault()}
              loading={savingDefault}
            >
              保存
            </Button>
          </Space>
        </Space>
      </Card>

      <Card className="section-card" variant="borderless">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Tabs
            activeKey={statusFilter}
            onChange={(key) => {
              setStatusFilter(key);
              setPage(1);
              setFilterDate(null);
              setSearchKeyword("");
              setKeyword("");
            }}
            items={[
              { key: "all", label: "全部" },
              { key: "pending", label: "未提醒" },
              { key: "fired", label: "已提醒" },
              { key: "failed", label: "提醒错误" },
            ]}
          />
          <ResponsiveFilterRail compact={isMobile}>
            <DatePicker
              placeholder="按日期筛选"
              allowClear
              value={filterDate}
              onChange={(value) => setFilterDate(value)}
              style={{ width: isMobile ? "100%" : 180 }}
            />
            <Input.Search
              placeholder="搜索提醒标题"
              allowClear
              enterButton={<SearchOutlined />}
              style={{ width: isMobile ? "100%" : 300 }}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onSearch={(value) => {
                setSearchKeyword(value);
                setPage(1);
              }}
            />
            <Select
              value={sortOrder}
              style={{ width: isMobile ? "100%" : 180 }}
              options={[
                { value: "trigger_time_asc", label: "触发时间升序" },
                { value: "trigger_time_desc", label: "触发时间降序" },
              ]}
              onChange={(value) => {
                setSortOrder(value as typeof sortOrder);
                setPage(1);
              }}
            />
            {filterDate ? (
              <Tag closable onClose={() => setFilterDate(null)} style={{ cursor: "pointer" }}>
                日期：{filterDate.format("YYYY-MM-DD")}
              </Tag>
            ) : null}
          </ResponsiveFilterRail>
        </Space>
      </Card>

      {error ? (
        <Alert type="error" showIcon message="加载提醒任务失败" description={error} />
      ) : null}

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" />
        </div>
      ) : filteredReminders.length ? (
        isMobile ? (
          mobileCards
        ) : (
          <Row gutter={[16, 16]}>
            {displayEntries.map((entry) => {
              if (entry.kind === "group") {
                return renderGroupedReminder(entry, false);
              }
              const reminder = entry.reminder;
              return (
                <Col xs={24} lg={12} key={reminder.id}>
                  <Card className="section-card" variant="borderless">
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong>{reminder.title}</Text>
                        <Tag color={getStatusColor(reminder.status)}>{reminder.status}</Tag>
                        <Tag color="cyan">{reminder.target_type}</Tag>
                      </Space>
                      {reminder.original_time ? (
                        <Text className="muted-text">
                          原定时间：{formatDateTime(reminder.original_time, timezone)}
                          {" "}({formatClock(reminder.original_time, timezone)})
                        </Text>
                      ) : null}
                      <Text className="muted-text">
                        触发时间：{formatDateTime(reminder.trigger_time, timezone)}
                        {" "}({formatClock(reminder.trigger_time, timezone)})
                      </Text>
                      <Text className="muted-text">
                        提前提醒：{reminder.remind_before_minutes ?? 0} 分钟
                      </Text>
                      {reminder.fired_at ? (
                        <Text className="muted-text">
                          触发于：{formatDateTime(reminder.fired_at, timezone)}
                        </Text>
                      ) : null}
                      {reminder.error_message ? (
                        <Text type="danger" className="muted-text">
                          错误：{reminder.error_message}
                        </Text>
                      ) : null}
                      <Text className="muted-text">会话：{reminder.conversation_id ?? "无"}</Text>
                      <Space wrap>
                        <Tag>重试 {reminder.retry_count}/{reminder.max_retries}</Tag>
                        <Tag>目标 {reminder.target_id}</Tag>
                        {renderReminderActions(reminder)}
                      </Space>
                    </Space>
                  </Card>
                </Col>
              );
            })}
          </Row>
        )
      ) : (
        <div className="dashboard-empty">
          <Empty description={filterDate ? `${filterDate.format("YYYY-MM-DD")} 无提醒` : "当前没有提醒任务"} />
        </div>
      )}

      <Card className="section-card" variant="borderless">
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showTotal={(t) => `共 ${t} 条`}
            onChange={(p, ps) => {
              setPage(p);
              setPageSize(ps);
            }}
          />
        </div>
      </Card>

      <Modal
        title="调整提醒提前时间"
        open={!!adjustTarget}
        onCancel={() => setAdjustTarget(null)}
        onOk={() => void handleAdjustConfirm()}
        confirmLoading={adjusting}
        okText="确认调整"
        cancelText="取消"
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Text>安排：{adjustTarget?.title}</Text>
          {adjustTarget?.original_time ? (
            <Text className="muted-text">
              原定时间：{formatDateTime(adjustTarget.original_time, timezone)}
            </Text>
          ) : null}
          <Text className="muted-text">
            当前提前 {adjustTarget?.remind_before_minutes ?? 0} 分钟提醒
          </Text>
          <Space>
            <Text>提前</Text>
            <InputNumber
              min={0}
              max={1440}
              value={adjustValue}
              onChange={(v) => setAdjustValue(v ?? 0)}
              style={{ width: 100 }}
            />
            <Text>分钟提醒</Text>
          </Space>
          {adjustTarget?.original_time ? (
            <Text className="muted-text">
              调整后触发时间：
              {formatDateTime(
                new Date(new Date(adjustTarget.original_time).getTime() - adjustValue * 60 * 1000).toISOString(),
                timezone,
              )}
            </Text>
          ) : null}
        </Space>
      </Modal>
    </Space>
  );
}
