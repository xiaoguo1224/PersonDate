"use client";

import { BellOutlined, SearchOutlined } from "@ant-design/icons";
import { App, Alert, Button, Card, Col, DatePicker, Empty, Input, InputNumber, Pagination, Row, Space, Spin, Tag, Typography } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatClock, formatDateTime, type ReminderItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";
import type { UserSettingsResponse } from "@/lib/types";

const { Title, Paragraph, Text } = Typography;

type ReminderListResponse = {
  items: ReminderItem[];
  total: number;
  page: number;
  page_size: number;
};

function getStatusColor(status: string) {
  if (status === "fired") return "green";
  if (status === "failed") return "red";
  if (status === "canceled") return "default";
  return "orange";
}

export default function RemindersPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const { modal, message } = App.useApp();
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDate, setFilterDate] = useState<Dayjs | null>(null);
  const [keyword, setKeyword] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [defaultRemindBefore, setDefaultRemindBefore] = useState(0);
  const [savingDefault, setSavingDefault] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const fetchReminders = useCallback((p?: number, ps?: number) => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const currentPage = p ?? page;
    const currentPageSize = ps ?? pageSize;
    const params = new URLSearchParams();
    if (searchKeyword) params.set("keyword", searchKeyword);
    params.set("page", String(currentPage));
    params.set("page_size", String(currentPageSize));
    requestJson<ReminderListResponse>(`/api/reminders?${params}`, {}, accessToken)
      .then((result) => {
        setReminders(result.items);
        setTotal(result.total);
      })
      .catch((caughtError: unknown) => {
        setError(caughtError instanceof Error ? caughtError.message : "未知错误");
      })
      .finally(() => setLoading(false));
  }, [accessToken, searchKeyword, page, pageSize]);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    setPage(1);
    fetchReminders(1);
  }, [accessToken, fetchReminders]);

  useEffect(() => {
    if (!accessToken) return;
    requestJson<UserSettingsResponse>(
      "/api/me/settings",
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
      await requestJson("/api/me/settings", {
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
          await requestJson(`/api/reminders/${reminder.id}/cancel`, { method: "PATCH" }, accessToken);
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
            await requestJson(`/api/reminders/${reminder.id}/reactivate`, {
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
        await requestJson(`/api/reminders/${reminder.id}/reactivate`, { method: "PATCH" }, accessToken);
        message.success("提醒已重新激活");
        fetchReminders(page);
      } catch (err) {
        message.error(err instanceof Error ? err.message : "操作失败");
      }
    }
  };

  const filteredReminders = useMemo(() => {
    if (!filterDate) return reminders;
    const dateKey = filterDate.format("YYYY-MM-DD");
    return reminders.filter((r) => {
      const triggerKey = dayjs(r.trigger_time).format("YYYY-MM-DD");
      return triggerKey === dateKey;
    });
  }, [reminders, filterDate]);

  const summary = useMemo(() => {
    const pending = reminders.filter((item) => item.status === "pending").length;
    const fired = reminders.filter((item) => item.status === "fired").length;
    const failed = reminders.filter((item) => item.status === "failed").length;
    return { total: reminders.length, pending, fired, failed };
  }, [reminders]);

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

      <Card className="section-card" variant="borderless" title="系统默认设置">
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text className="muted-text">
            所有新建安排的默认提前提醒时间
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
          <Space wrap>
            <DatePicker
              placeholder="按日期筛选"
              allowClear
              value={filterDate}
              onChange={(value) => setFilterDate(value)}
              style={{ minWidth: 180 }}
            />
            <Input.Search
              placeholder="搜索提醒标题"
              allowClear
              enterButton={<SearchOutlined />}
              style={{ width: 300 }}
              onSearch={(value) => setSearchKeyword(value)}
            />
            {filterDate && (
              <Tag closable onClose={() => setFilterDate(null)} style={{ cursor: "pointer" }}>
                日期：{filterDate.format("YYYY-MM-DD")}
              </Tag>
            )}
          </Space>
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
        <Row gutter={[16, 16]}>
          {filteredReminders.map((reminder) => (
            <Col xs={24} lg={12} key={reminder.id}>
              <Card className="section-card" variant="borderless">
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{reminder.title}</Text>
                    <Tag color={getStatusColor(reminder.status)}>{reminder.status}</Tag>
                    <Tag color="cyan">{reminder.target_type}</Tag>
                  </Space>
                  <Text className="muted-text">
                    触发时间：{formatDateTime(reminder.trigger_time, timezone)}
                    {" "}({formatClock(reminder.trigger_time, timezone)})
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
                    {reminder.status === "pending" ? (
                      <Button
                        danger
                        size="small"
                        onClick={() => void handleCancel(reminder)}
                      >
                        取消提醒
                      </Button>
                    ) : null}
                    {reminder.status === "canceled" ? (
                      <Button
                        type="primary"
                        size="small"
                        onClick={() => void handleReactivate(reminder)}
                      >
                        重新激活
                      </Button>
                    ) : null}
                  </Space>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <div className="dashboard-empty">
          <Empty description={filterDate ? `${filterDate.format("YYYY-MM-DD")} 无提醒` : "当前没有提醒任务"} />
        </div>
      )}

      {total > pageSize && (
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
                fetchReminders(p, ps);
              }}
            />
          </div>
        </Card>
      )}
    </Space>
  );
}
