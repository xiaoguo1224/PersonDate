"use client";

import { useMemo } from "react";

export type PerformanceLevel = "low" | "medium" | "high";

export function usePerformance(): PerformanceLevel {
  return useMemo(() => {
    if (typeof window === "undefined") return "medium";

    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReduced) return "low";

    const cores = navigator.hardwareConcurrency || 4;
    const memory = (navigator as Navigator & { deviceMemory?: number })
      .deviceMemory || 4;

    if (cores <= 2 || memory <= 2) return "low";
    if (cores >= 8 && memory >= 8) return "high";
    return "medium";
  }, []);
}
