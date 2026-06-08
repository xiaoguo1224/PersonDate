"use client";

import { App, Button, Card, DatePicker, Empty, Form, Input, InputNumber, List, Modal, Pagination, Segmented, Space, Spin, Tag, Typography } from "antd";
import { CheckOutlined, CloseOutlined, EditOutlined, SearchOutlined, SwapOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime, loadScheduledItem, updateScheduledItem, type ConflictItem, type ScheduledItem } from "@/lib/dashboard";
import { requestJson } from "@/lib/api";

const { Title, Paragraph, Text } = Typography;

type StatusFilter = "open" | "resolved" | "ignored" | "all";

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

type EditFormValues = {
  title: string;
  start_time: Dayjs;
  end_time: Dayjs;
};

export default function ConflictsPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const { modal, message } = App.useApp();
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [keyword, setKeyword] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const [selectModalOpen, setSelectModalOpen] = useState(false);
  const [selectConflict, setSelectConflict] = useState<ConflictItem | null>(null);
  const [conflictItemA, setConflictItemA] = useState<ScheduledItem | null>(null);
  const [conflictItemB, setConflictItemB] = useState<ScheduledItem | null>(null);
  const [selectLoading, setSelectLoading] = useState(false);

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ScheduledItem | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editForm] = Form.useForm<EditFormValues>();

  const fetchConflicts = useCallback((p?: number, ps?: number) => {
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
    params.set("page", String(currentPage));
    params.set("page_size", String(currentPageSize));
    requestJson<{ items: ConflictItem[]; total: number }>(`/api/conflicts?${params}`, {}, accessToken)
      .then((result) => {
        setConflicts(result.items);
        setTotal(result.total);
      })
      .catch(() => setConflicts([]))
      .finally(() => setLoading(false));
  }, [accessToken, statusFilter, searchKeyword, page, pageSize]);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    setPage(1);
    fetchConflicts(1);
  }, [accessToken, fetchConflicts]);

  const handleResolve = async (id: string) => {
    if (!accessToken) return;
    try {
      await requestJson(`/api/conflicts/${id}/resolve`, { method: "PATCH" }, accessToken);
      message.success("冲突已解决");
      fetchConflicts(page);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleIgnore = async (id: string) => {
    if (!accessToken) return;
    try {
      await requestJson(`/api/conflicts/${id}/ignore`, { method: "POST" }, accessToken);
      message.success("冲突已忽略");
      fetchConflicts(page);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleConfirmResolve = (conflict: ConflictItem) => {
    modal.confirm({
      title: "确认解决",
      content: `确定要解决"${conflict.title}"冲突吗？`,
      okText: "解决",
      cancelText: "取消",
      onOk: () => void handleResolve(conflict.id),
    });
  };

  const handleOpenEditModal = useCallback(async (conflict: ConflictItem) => {
    if (!accessToken) return;
    const ids = conflict.related_item_ids;
    if (!ids?.current || !ids?.other) return;
    setSelectConflict(conflict);
    setSelectLoading(true);
    setSelectModalOpen(true);
    try {
      const [itemA, itemB] = await Promise.all([
        loadScheduledItem(ids.current, accessToken).catch(() => null),
        loadScheduledItem(ids.other, accessToken).catch(() => null),
      ]);
      setConflictItemA(itemA);
      setConflictItemB(itemB);
    } finally {
      setSelectLoading(false);
    }
  }, [accessToken]);

  const handleSelectEditTarget = useCallback((item: ScheduledItem) => {
    setEditTarget(item);
    editForm.setFieldsValue({
      title: item.title,
      start_time: dayjs(item.start_time),
      end_time: dayjs(item.end_time),
    });
    setSelectModalOpen(false);
    setEditModalOpen(true);
  }, [editForm]);

  const handleEditSubmit = useCallback(async () => {
    if (!accessToken || !editTarget) return;
    try {
      const values = await editForm.validateFields();
      setEditSubmitting(true);
      await updateScheduledItem(editTarget.id, {
        title: values.title.trim(),
        start_time: values.start_time.toISOString(),
        end_time: values.end_time.toISOString(),
      }, accessToken);
      message.success("时间已修改");
      setEditModalOpen(false);
      setEditTarget(null);
      editForm.resetFields();
      fetchConflicts(page);
    } catch (caughtError: unknown) {
      if (caughtError && typeof caughtError === "object" && "errorFields" in caughtError) return;
      message.error(caughtError instanceof Error ? caughtError.message : "修改失败");
    } finally {
      setEditSubmitting(false);
    }
  }, [accessToken, editTarget, editForm, message, fetchConflicts, page]);

  const filteredConflicts = useMemo(() => {
    // 冲突按状态和关键词过滤，不按日期过滤
    // 因为冲突的日期由关联的安排项决定，而不是检测时间
    return conflicts;
  }, [conflicts]);

  const summary = useMemo(() => {
    const high = conflicts.filter((item) => item.severity === "high").length;
    const medium = conflicts.filter((item) => item.severity === "medium").length;
    const open = conflicts.filter((item) => item.status === "open").length;
    const resolved = conflicts.filter((item) => item.status === "resolved").length;
    return { total: conflicts.length, high, medium, open, resolved };
  }, [conflicts]);

  const statusOptions = [
    { label: "未解决", value: "open" as StatusFilter },
    { label: "已解决", value: "resolved" as StatusFilter },
    { label: "已忽略", value: "ignored" as StatusFilter },
    { label: "全部", value: "all" as StatusFilter },
  ];

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="section-card dashboard-hero" variant="borderless">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <span className="hero-kicker">冲突事项</span>
          <Title style={{ margin: 0 }}>冲突总览</Title>
          <Paragraph className="muted-text" style={{ marginBottom: 0, maxWidth: 880 }}>
            管理日程冲突：按天筛选、查看历史、解决或忽略冲突。
          </Paragraph>
          <Space wrap>
            <Tag color="red">{summary.high} 个高优先级</Tag>
            <Tag color="gold">{summary.medium} 个中优先级</Tag>
            <Tag color="orange">{summary.open} 个未解决</Tag>
            <Tag color="green">{summary.resolved} 个已解决</Tag>
          </Space>
        </Space>
      </Card>

      <Card className="section-card" variant="borderless">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Space wrap>
            <Segmented<StatusFilter>
              options={statusOptions}
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
            />
            <Input.Search
              placeholder="搜索冲突标题或描述"
              allowClear
              enterButton={<SearchOutlined />}
              style={{ width: 300 }}
              onSearch={(value) => setSearchKeyword(value)}
            />
          </Space>
        </Space>
      </Card>

      {loading ? (
        <div className="dashboard-empty">
          <Spin size="large" />
        </div>
      ) : filteredConflicts.length ? (
        <Card className="section-card" variant="borderless" title="冲突列表">
          <List
            itemLayout="vertical"
            dataSource={filteredConflicts}
            pagination={false}
            renderItem={(conflict) => (
              <List.Item key={conflict.id}>
                <Card size="small" variant="borderless" style={{ background: "rgba(255,255,255,0.04)" }}>
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap>
                      <Text strong>{conflict.title}</Text>
                      <Tag color={getSeverityColor(conflict.severity)}>{conflict.severity}</Tag>
                      <Tag color={getStatusColor(conflict.status)}>{conflict.status}</Tag>
                    </Space>
                    {conflict.description ? <Text className="muted-text">{conflict.description}</Text> : null}
                    {conflict.suggestion ? <Text className="muted-text">建议：{conflict.suggestion}</Text> : null}
                    <Space wrap>
                      <Tag>检测时间 {formatDateTime(conflict.detected_at, timezone)}</Tag>
                      {conflict.status === "open" ? (
                        <>
                          <Tag
                            color="blue"
                            style={{ cursor: "pointer" }}
                            onClick={() => void handleOpenEditModal(conflict)}
                          >
                            <EditOutlined /> 修改时间
                          </Tag>
                          <Tag
                            color="green"
                            style={{ cursor: "pointer" }}
                            onClick={() => handleConfirmResolve(conflict)}
                          >
                            <CheckOutlined /> 解决
                          </Tag>
                          <Tag
                            color="default"
                            style={{ cursor: "pointer" }}
                            onClick={() => void handleIgnore(conflict.id)}
                          >
                            <CloseOutlined /> 忽略
                          </Tag>
                        </>
                      ) : null}
                    </Space>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              showSizeChanger
              showTotal={(t) => `共 ${t} 条`}
              onChange={(p, ps) => {
                setPage(p);
                setPageSize(ps);
                fetchConflicts(p, ps);
              }}
            />
          </div>
        </Card>
      ) : (
        <div className="dashboard-empty">
          <Empty description="当前没有冲突事项" />
        </div>
      )}

      <Modal
        title="选择要修改的安排"
        open={selectModalOpen}
        onCancel={() => {
          setSelectModalOpen(false);
          setSelectConflict(null);
          setConflictItemA(null);
          setConflictItemB(null);
        }}
        footer={null}
        width={480}
        destroyOnHidden
      >
        {selectLoading ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin />
          </div>
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Text className="muted-text">
              以下两个安排存在时间重叠，请选择一个修改其时间：
            </Text>
            {conflictItemA ? (
              <Card
                size="small"
                hoverable
                style={{ cursor: "pointer", background: "rgba(255,255,255,0.04)" }}
                onClick={() => handleSelectEditTarget(conflictItemA)}
              >
                <Space>
                  <SwapOutlined />
                  <div>
                    <Text strong>{conflictItemA.title}</Text>
                    <br />
                    <Text className="muted-text" style={{ fontSize: 12 }}>
                      {formatDateTime(conflictItemA.start_time, timezone)} - {formatDateTime(conflictItemA.end_time, timezone)}
                    </Text>
                  </div>
                </Space>
              </Card>
            ) : null}
            {conflictItemB ? (
              <Card
                size="small"
                hoverable
                style={{ cursor: "pointer", background: "rgba(255,255,255,0.04)" }}
                onClick={() => handleSelectEditTarget(conflictItemB)}
              >
                <Space>
                  <SwapOutlined />
                  <div>
                    <Text strong>{conflictItemB.title}</Text>
                    <br />
                    <Text className="muted-text" style={{ fontSize: 12 }}>
                      {formatDateTime(conflictItemB.start_time, timezone)} - {formatDateTime(conflictItemB.end_time, timezone)}
                    </Text>
                  </div>
                </Space>
              </Card>
            ) : null}
          </Space>
        )}
      </Modal>

      <Modal
        title={`修改时间：${editTarget?.title ?? ""}`}
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false);
          setEditTarget(null);
          editForm.resetFields();
        }}
        onOk={() => void handleEditSubmit()}
        okText="保存"
        cancelText="取消"
        confirmLoading={editSubmitting}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="标题" name="title">
            <Input disabled />
          </Form.Item>
          <Form.Item
            label="开始时间"
            name="start_time"
            rules={[{ required: true, message: "请选择开始时间" }]}
          >
            <DatePicker
              showTime={{ format: "HH:mm" }}
              format="YYYY-MM-DD HH:mm"
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Form.Item
            label="结束时间"
            name="end_time"
            rules={[{ required: true, message: "请选择结束时间" }]}
          >
            <DatePicker
              showTime={{ format: "HH:mm" }}
              format="YYYY-MM-DD HH:mm"
              style={{ width: "100%" }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
