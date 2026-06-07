"use client";

import { useGSAP } from "@gsap/react";
import dayjs from "dayjs";
import gsap from "gsap";
import { useMemo, useRef } from "react";

import { formatClock } from "@/lib/dashboard";

export type GanttItem = {
  id: string;
  title: string;
  start_time: string;
  end_time?: string | null;
  status?: string;
  type?: "event" | "task" | "break";
};

type GanttRow = {
  source: GanttItem;
  id: string;
  title: string;
  startLabel: string;
  endLabel: string;
  type: "event" | "task" | "break";
  barLeft: number;
  barWidth: number;
};

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const TICK_HOURS = HOURS.filter((h) => h % 3 === 0);

const BAR_COLORS: Record<string, string> = {
  event: "linear-gradient(135deg, #3b82f6, #60a5fa)",
  task: "linear-gradient(135deg, #10b981, #34d399)",
  break: "linear-gradient(135deg, #f59e0b, #fbbf24)",
};

const TYPE_LABELS: Record<string, string> = {
  event: "日程",
  task: "任务",
  break: "休息",
};

function buildRows(
  items: GanttItem[],
  baseDate: string,
  timezone: string,
): GanttRow[] {
  const dayStart = dayjs(baseDate).startOf("day");
  const nextDayStart = dayStart.add(1, "day");
  const totalMinutes = 24 * 60;

  return items
    .filter((item) => item.status !== "deleted")
    .map((item) => {
      const start = dayjs(item.start_time);
      const rawEnd = dayjs(item.end_time ?? item.start_time);
      const end = rawEnd.isAfter(start) ? rawEnd : start.add(60, "minute");

      if (end.isBefore(dayStart) || start.isAfter(nextDayStart)) {
        return null;
      }

      const clampedStart = start.isBefore(dayStart) ? dayStart : start;
      const clampedEnd = end.isAfter(nextDayStart) ? nextDayStart : end;
      const startMinutes = clampedStart.diff(dayStart, "minute", true);
      const durationMinutes = Math.max(
        15,
        clampedEnd.diff(clampedStart, "minute", true),
      );
      const barLeft = Math.min((startMinutes / totalMinutes) * 100, 97);
      const barWidth = Math.max((durationMinutes / totalMinutes) * 100, 2);

      return {
        source: item,
        id: item.id,
        title: item.title,
        startLabel: formatClock(item.start_time, timezone),
        endLabel: formatClock(item.end_time ?? item.start_time, timezone),
        type: item.type ?? "event",
        barLeft,
        barWidth,
      };
    })
    .filter((r): r is GanttRow => r !== null)
    .sort((a, b) => a.barLeft - b.barLeft);
}

export default function GanttChart({
  items,
  baseDate,
  timezone,
  maxHeight,
  onEventClick,
}: Readonly<{
  items: GanttItem[];
  baseDate: string;
  timezone: string;
  maxHeight?: number;
  onEventClick?: (item: GanttItem) => void;
}>) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  const rows = useMemo(
    () => buildRows(items, baseDate, timezone),
    [items, baseDate, timezone],
  );

  useGSAP(
    () => {
      gsap.from(rootRef.current?.querySelectorAll(".gantt-row") ?? [], {
        x: -16,
        opacity: 0,
        duration: 0.35,
        stagger: 0.04,
        ease: "power3.out",
        clearProps: "all",
      });
    },
    { scope: rootRef, dependencies: [rows.length] },
  );

  return (
    <div
      ref={rootRef}
      className="gantt-chart"
      style={maxHeight ? { maxHeight } : undefined}
    >
      <div className="gantt-chart__header">
        <div className="gantt-chart__label-col">
          <span className="gantt-chart__col-title">安排</span>
        </div>
        <div className="gantt-chart__timeline-col">
          {TICK_HOURS.map((h) => (
            <span key={h} className="gantt-chart__tick">
              {String(h).padStart(2, "0")}:00
            </span>
          ))}
          <span className="gantt-chart__tick">24:00</span>
        </div>
      </div>

      <div className="gantt-chart__gridlines">
        {TICK_HOURS.map((h) => (
          <div
            key={h}
            className="gantt-chart__gridline"
            style={{ left: `${(h / 24) * 100}%` }}
          />
        ))}
      </div>

      <div className="gantt-chart__body">
        {rows.length === 0 ? (
          <div className="gantt-chart__empty">暂无安排</div>
        ) : (
          rows.map((row) => (
            <div
              key={row.id}
              className="gantt-row"
              onClick={() => onEventClick?.(row.source)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onEventClick?.(row.source);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="gantt-row__label">
                <span
                  className="gantt-row__dot"
                  style={{ background: BAR_COLORS[row.type] ?? BAR_COLORS.event }}
                />
                <span className="gantt-row__title">{row.title}</span>
                <span className="gantt-row__time">
                  {row.startLabel} - {row.endLabel}
                </span>
                <span className="gantt-row__tag">{TYPE_LABELS[row.type] ?? "日程"}</span>
              </div>
              <div className="gantt-row__bar-track">
                <div
                  className="gantt-row__bar"
                  style={{
                    left: `${row.barLeft}%`,
                    width: `${row.barWidth}%`,
                    background: BAR_COLORS[row.type] ?? BAR_COLORS.event,
                  }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
