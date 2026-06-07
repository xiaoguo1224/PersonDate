"use client";

import { App, Card, DatePicker, Empty, Input, List, Pagination, Segmented, Space, Spin, Tag, Typography } from "antd";
import { CheckOutlined, CloseOutlined, SearchOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useDashboardTimezone } from "@/components/dashboard-preferences";
import { formatDateTime, type ConflictItem } from "@/lib/dashboard";
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

export default function ConflictsPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const { timezone } = useDashboardTimezone();
  const { modal, message } = App.useApp();
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterDate, setFilterDate] = useState<Dayjs | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [keyword, setKeyword] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

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
      await requestJson(`/api/conflicts/${id}/resolve`, { method: "POST" }, accessToken);
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

  const filteredConflicts = useMemo(() => {
    if (!filterDate) return conflicts;
    const dateKey = filterDate.format("YYYY-MM-DD");
    return conflicts.filter((c) => {
      const detectedKey = dayjs(c.detected_at).format("YYYY-MM-DD");
      return detectedKey === dateKey;
    });
  }, [conflicts, filterDate]);

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
            <DatePicker
              placeholder="按日期筛选"
              allowClear
              value={filterDate}
              onChange={(value) => setFilterDate(value)}
              style={{ minWidth: 180 }}
            />
            {filterDate && (
              <Tag closable onClose={() => setFilterDate(null)} style={{ cursor: "pointer" }}>
                日期：{filterDate.format("YYYY-MM-DD")}
              </Tag>
            )}
          </Space>
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
        <Card className="section-card" variant="borderless" title={filterDate ? `${filterDate.format("YYYY-MM-DD")} 的冲突` : "冲突列表"}>
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
          <Empty description={filterDate ? `${filterDate.format("YYYY-MM-DD")} 无冲突` : "当前没有冲突事项"} />
        </div>
      )}
    </Space>
  );
}
