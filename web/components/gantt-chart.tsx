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

type GanttBar = {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  barLeft: number;
  barWidth: number;
  startLabel: string;
  endLabel: string;
  type: "event" | "task" | "break";
};

const HOURS = Array.from({ length: 24 }, (_, i) => i);

function buildBars(
  items: GanttItem[],
  baseDate: string,
  timezone: string,
): GanttBar[] {
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
      const barLeft = (startMinutes / totalMinutes) * 100;
      const barWidth = (durationMinutes / totalMinutes) * 100;

      return {
        id: item.id,
        title: item.title,
        start_time: item.start_time,
        end_time: item.end_time ?? item.start_time,
        barLeft: Math.min(barLeft, 97),
        barWidth: Math.max(barWidth, 2),
        startLabel: formatClock(item.start_time, timezone),
        endLabel: formatClock(item.end_time ?? item.start_time, timezone),
        type: item.type ?? "event",
      } as GanttBar;
    })
    .filter((item): item is GanttBar => item !== null);
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
  const ganttRef = useRef<HTMLDivElement | null>(null);

  const bars = useMemo(
    () => buildBars(items, baseDate, timezone),
    [items, baseDate, timezone],
  );

  useGSAP(
    () => {
      gsap.from(ganttRef.current?.querySelectorAll(".gantt-bar") ?? [], {
        scaleX: 0,
        transformOrigin: "left center",
        duration: 0.4,
        stagger: 0.04,
        ease: "power3.out",
        clearProps: "scaleX",
      });
    },
    { scope: ganttRef, dependencies: [bars.length] },
  );

  const barColors: Record<string, string> = {
    event: "linear-gradient(135deg, #3b82f6, #60a5fa)",
    task: "linear-gradient(135deg, #10b981, #34d399)",
    break: "linear-gradient(135deg, #f59e0b, #fbbf24)",
  };

  return (
    <div
      ref={ganttRef}
      className="gantt-chart"
      style={maxHeight ? { maxHeight } : undefined}
    >
      <div className="gantt-chart__axis">
        {HOURS.filter((h) => h % 3 === 0).map((h) => (
          <span key={h}>{String(h).padStart(2, "0")}:00</span>
        ))}
        <span>24:00</span>
      </div>
      <div className="gantt-chart__body">
        <div className="gantt-chart__grid">
          {HOURS.filter((h) => h % 3 === 0).map((h) => (
            <div
              key={h}
              className="gantt-chart__hour-line"
              style={{ left: `${(h / 24) * 100}%` }}
            />
          ))}
        </div>
        {bars.length === 0 ? (
          <div className="gantt-chart__empty">暂无安排</div>
        ) : (
          bars.map((bar) => (
            <div
              key={bar.id}
              className="gantt-chart__track"
              onClick={() => onEventClick?.(bar)}
            >
              <div
                className="gantt-bar"
                style={{
                  left: `${bar.barLeft}%`,
                  width: `${bar.barWidth}%`,
                  background: barColors[bar.type] ?? barColors.event,
                }}
              >
                <span className="gantt-bar__title">{bar.title}</span>
                <span className="gantt-bar__time">
                  {bar.startLabel}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
