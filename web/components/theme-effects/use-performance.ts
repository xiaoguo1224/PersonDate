"use client";

import { useEffect, useState } from "react";

export type PerformanceLevel = "low" | "medium" | "high";

export function usePerformance(): PerformanceLevel {
  const [performance, setPerformance] = useState<PerformanceLevel>("medium");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const update = () => {
      const prefersReduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      if (prefersReduced) {
        setPerformance("low");
        return;
      }

      const cores = navigator.hardwareConcurrency || 4;
      const memory = (navigator as Navigator & { deviceMemory?: number })
        .deviceMemory || 4;

      if (cores <= 2 || memory <= 2) {
        setPerformance("low");
        return;
      }
      if (cores >= 8 && memory >= 8) {
        setPerformance("high");
        return;
      }
      setPerformance("medium");
    };

    update();

    const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = () => update();

    if (reduceQuery.addEventListener) {
      reduceQuery.addEventListener("change", handleChange);
      return () => reduceQuery.removeEventListener("change", handleChange);
    }

    reduceQuery.addListener(handleChange);
    return () => reduceQuery.removeListener(handleChange);
  }, []);

  return performance;
}
