"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useMemo, useRef } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface CloudEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 8,
  medium: 12,
  high: 18,
};

interface CloudDef {
  size: number;
  y: number;
  opacity: number;
  speedFactor: number;
  blur: number;
  lane: "high" | "mid" | "low";
}

function generateCloudDefs(count: number): CloudDef[] {
  return Array.from({ length: count }, () => {
    const laneRoll = Math.random();
    const lane: CloudDef["lane"] =
      laneRoll < 0.3 ? "high" : laneRoll < 0.68 ? "mid" : "low";
    const size = gsap.utils.random(200, 420);

    return {
      size,
      y:
          lane === "high"
          ? gsap.utils.random(4, 16)
          : lane === "mid"
            ? gsap.utils.random(20, 42)
            : gsap.utils.random(42, 72),
      opacity:
        lane === "high"
          ? gsap.utils.random(0.56, 0.82)
          : lane === "mid"
            ? gsap.utils.random(0.62, 0.84)
            : gsap.utils.random(0.68, 0.9),
      speedFactor:
        lane === "high"
          ? gsap.utils.random(0.95, 1.22)
          : lane === "mid"
            ? gsap.utils.random(0.6, 0.86)
            : gsap.utils.random(0.42, 0.62),
      blur: lane === "high" ? gsap.utils.random(0.8, 1.6) : gsap.utils.random(0.6, 1.2),
      lane,
    };
  });
}

function CloudShape({ def }: { def: CloudDef }) {
  const w = def.size;
  const h = def.size * 0.56;
  const base = `rgba(255, 255, 255, ${def.opacity})`;
  const highlight = `rgba(255, 255, 255, ${Math.min(def.opacity + 0.16, 0.98)})`;
  const shadow = `rgba(255, 255, 255, ${Math.max(def.opacity - 0.2, 0.2)})`;

  return (
    <div
      style={{
        position: "relative",
        width: w,
        height: h,
        filter: `blur(${def.blur}px)`,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "18% 6% 10%",
          borderRadius: "999px",
          background: `linear-gradient(180deg, ${highlight}, ${base})`,
          boxShadow: "0 0 24px rgba(255, 255, 255, 0.14)",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "10%",
          left: "6%",
          width: "40%",
          height: "78%",
          borderRadius: "50%",
          background: shadow,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "20%",
          left: "24%",
          width: "32%",
          height: "88%",
          borderRadius: "50%",
          background: highlight,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "18%",
          right: "8%",
          width: "42%",
          height: "74%",
          borderRadius: "50%",
          background: base,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: "12%",
          width: "72%",
          height: "34%",
          borderRadius: "999px",
          background: "rgba(255, 255, 255, 0.18)",
        }}
      />
    </div>
  );
}

export default function CloudEffect({
  visible,
  onFadeOutComplete,
}: CloudEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const performance = usePerformance();
  const cloudDefs = useMemo(
    () => generateCloudDefs(COUNT_MAP[performance]),
    [performance],
  );

  useGSAP(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const clouds = container.querySelectorAll<HTMLDivElement>(".cloud");
      if (!clouds.length) return;

      const vw = window.innerWidth;

      clouds.forEach((cloud, i) => {
        const def = cloudDefs[i];
        if (!def) return;

        const duration = gsap.utils.random(16, 34) / def.speedFactor;
        const delay = gsap.utils.random(0, duration);
        const drift = gsap.utils.random(16, 36);

        gsap.set(cloud, {
          x: -def.size - 120,
          y: `${def.y}vh`,
          scale: gsap.utils.random(0.92, 1.08),
          opacity: def.opacity,
        });

        gsap.to(cloud, {
          x: vw + def.size + 120,
          duration,
          delay,
          ease: "none",
          repeat: -1,
        });

        gsap.to(cloud, {
          y: `+=${drift}`,
          duration: gsap.utils.random(7, 14),
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          delay: gsap.utils.random(0, 3),
        });

        if (performance === "high") {
          gsap.to(cloud, {
            scale: `+=${gsap.utils.random(0.04, 0.08)}`,
            duration: gsap.utils.random(5, 9),
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
            delay: gsap.utils.random(0, 4),
          });
        }
      });

      gsap.fromTo(
        container,
        { opacity: 0 },
        { opacity: 1, duration: 0.9, ease: "power2.out" },
      );

      return () => {
        gsap.killTweensOf(clouds);
      };
    },
    { scope: containerRef, dependencies: [cloudDefs, performance] },
  );

  const handleVisibilityChange = useCallback(
    (isVisible: boolean) => {
      const container = containerRef.current;
      if (!container) return;

      if (!isVisible) {
        gsap.to(container, {
          opacity: 0,
          duration: 0.6,
          ease: "power2.in",
          onComplete: onFadeOutComplete,
        });
      }
    },
    [onFadeOutComplete],
  );

  useGSAP(() => {
    if (!visible) {
      handleVisibilityChange(false);
    }
  }, [visible]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 0,
        opacity: 0,
        overflow: "hidden",
        mixBlendMode: "screen",
        willChange: "transform, opacity",
      }}
      aria-hidden="true"
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 18% 14%, rgba(255, 255, 255, 0.4), transparent 18%), radial-gradient(circle at 82% 16%, rgba(147, 197, 253, 0.24), transparent 18%), radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.16), transparent 24%)",
          opacity: 0.96,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "-12% -10% auto -10%",
          height: "42vh",
          background:
            "linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.06), transparent)",
          filter: "blur(18px)",
          transform: "rotate(-2deg)",
        }}
      />
      {cloudDefs.map((def, i) => (
        <div
          key={i}
          className="cloud"
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            willChange: "transform, opacity",
          }}
        >
          <CloudShape def={def} />
        </div>
      ))}
    </div>
  );
}
