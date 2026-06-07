"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useEffect, useRef, useState } from "react";
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
  layer: "high" | "mid" | "low";
}

function generateCloudDefs(count: number): CloudDef[] {
  return Array.from({ length: count }, (_, i) => {
    const size = gsap.utils.random(150, 350);
    const speedFactor = 1 - (size - 150) / 300;
    const layerRoll = Math.random();
    const layer: CloudDef["layer"] =
      layerRoll < 0.3 ? "high" : layerRoll < 0.65 ? "mid" : "low";

    return {
      size,
      y: layer === "high"
        ? gsap.utils.random(5, 25)
        : layer === "mid"
          ? gsap.utils.random(25, 50)
          : gsap.utils.random(50, 75),
      opacity: layer === "high"
        ? gsap.utils.random(0.6, 0.8)
        : layer === "mid"
          ? gsap.utils.random(0.7, 0.85)
          : gsap.utils.random(0.8, 0.9),
      speedFactor:
        layer === "high"
          ? gsap.utils.random(0.8, 1.2)
          : layer === "mid"
            ? gsap.utils.random(0.5, 0.8)
            : gsap.utils.random(0.3, 0.5),
      layer,
    };
  });
}

function CloudShape({ def }: { def: CloudDef }) {
  const baseColor = `rgba(255, 255, 255, ${def.opacity})`;
  const w = def.size;
  const h = def.size * 0.5;

  return (
    <div
      style={{
        position: "relative",
        width: w,
        height: h,
      }}
    >
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: "10%",
          width: "80%",
          height: "60%",
          borderRadius: "50%",
          backgroundColor: baseColor,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "20%",
          left: "5%",
          width: "45%",
          height: "70%",
          borderRadius: "50%",
          backgroundColor: baseColor,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "25%",
          left: "30%",
          width: "50%",
          height: "80%",
          borderRadius: "50%",
          backgroundColor: baseColor,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "10%",
          right: "5%",
          width: "40%",
          height: "55%",
          borderRadius: "50%",
          backgroundColor: baseColor,
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
  const [mounted, setMounted] = useState(false);
  const count = mounted ? COUNT_MAP[performance] : COUNT_MAP.medium;
  const [cloudDefs] = useState(() => generateCloudDefs(18));

  useEffect(() => {
    setMounted(true);
  }, []);

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

        const baseDuration = gsap.utils.random(20, 40);
        const duration = baseDuration / def.speedFactor;
        const delay = gsap.utils.random(0, duration);

        gsap.set(cloud, {
          x: -def.size - 100,
          y: `${def.y}vh`,
        });

        gsap.to(cloud, {
          x: vw + def.size + 100,
          duration,
          ease: "none",
          repeat: -1,
          delay,
        });

        // high 性能时云朵有轻微垂直漂浮
        if (performance === "high") {
          gsap.to(cloud, {
            y: `+=${gsap.utils.random(-15, 15)}`,
            duration: gsap.utils.random(8, 15),
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
            delay: gsap.utils.random(0, 5),
          });
        }
      });

      gsap.fromTo(
        container,
        { opacity: 0 },
        { opacity: 1, duration: 1, ease: "power2.out" }
      );
    },
    { scope: containerRef }
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
    [onFadeOutComplete]
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
        willChange: "transform, opacity",
      }}
      aria-hidden="true"
    >
      {cloudDefs.slice(0, count).map((def, i) => (
        <div
          key={i}
          className="cloud"
          style={{
            position: "absolute",
            willChange: "transform, opacity",
          }}
        >
          <CloudShape def={def} />
        </div>
      ))}
    </div>
  );
}
