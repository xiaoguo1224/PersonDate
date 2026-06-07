"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useEffect, useRef, useState } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface SakuraEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 15,
  medium: 20,
  high: 25,
};

const PETAL_COLORS = ["#e84393", "#fd79a8", "#fab1a0", "#ffc0cb"];

function SakuraTree() {
  const trunkColor = "#5D4037";
  const crownColors = [
    "rgba(255, 182, 193, 0.5)",
    "rgba(255, 192, 203, 0.45)",
    "rgba(253, 121, 168, 0.35)",
    "rgba(232, 67, 147, 0.25)",
    "rgba(255, 218, 225, 0.5)",
  ];

  const crownCircles = [
    { left: -60, top: -180, size: 160 },
    { left: 10, top: -220, size: 180 },
    { left: 70, top: -180, size: 150 },
    { left: -30, top: -140, size: 140 },
    { left: 40, top: -150, size: 130 },
    { left: -10, top: -200, size: 170 },
    { left: 50, top: -210, size: 140 },
    { left: -50, top: -160, size: 120 },
  ];

  return (
    <div
      style={{
        position: "fixed",
        left: "5%",
        bottom: 0,
        width: 200,
        height: 350,
        pointerEvents: "none",
        zIndex: 0,
      }}
    >
      {/* 树干 */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: "50%",
          transform: "translateX(-50%)",
          width: 24,
          height: 200,
          backgroundColor: trunkColor,
          borderRadius: "8px 8px 12px 12px",
        }}
      />
      {/* 树枝 */}
      <div
        style={{
          position: "absolute",
          bottom: 120,
          left: "50%",
          width: 60,
          height: 8,
          backgroundColor: trunkColor,
          borderRadius: 4,
          transform: "translateX(-60%) rotate(-25deg)",
          transformOrigin: "right center",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 150,
          left: "50%",
          width: 50,
          height: 7,
          backgroundColor: trunkColor,
          borderRadius: 4,
          transform: "translateX(0%) rotate(20deg)",
          transformOrigin: "left center",
        }}
      />
      {/* 树冠 */}
      {crownCircles.map((c, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            bottom: 0,
            left: "50%",
            marginLeft: c.left,
            marginTop: c.top,
            width: c.size,
            height: c.size,
            borderRadius: "50%",
            backgroundColor: crownColors[i % crownColors.length],
          }}
        />
      ))}
    </div>
  );
}

export default function SakuraEffect({
  visible,
  onFadeOutComplete,
}: SakuraEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const performance = usePerformance();
  const [mounted, setMounted] = useState(false);
  const count = mounted ? COUNT_MAP[performance] : COUNT_MAP.medium;

  useEffect(() => {
    setMounted(true);
  }, []);

  useGSAP(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const petals = container.querySelectorAll<HTMLDivElement>(".petal");
      if (!petals.length) return;

      const vh = window.innerHeight;

      // 树冠区域的起始 x 范围（屏幕左侧 5% + 树冠偏移）
      const treeCenterVw = 15;
      const treeSpreadVw = 8;

      petals.forEach((petal) => {
        const size = gsap.utils.random(8, 20);
        const color =
          PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)];
        const startXVw = gsap.utils.random(
          treeCenterVw - treeSpreadVw,
          treeCenterVw + treeSpreadVw
        );
        const startYVh = gsap.utils.random(15, 40);
        const duration = gsap.utils.random(8, 16);
        const delay = gsap.utils.random(0, 10);
        const swayRange = gsap.utils.random(40, 100);

        gsap.set(petal, {
          x: `${startXVw}vw`,
          y: `${startYVh}vh`,
          width: size,
          height: size * 0.65,
          opacity: gsap.utils.random(0.5, 0.85),
          backgroundColor: color,
          borderRadius: "50% 0 50% 0",
          rotation: gsap.utils.random(0, 360),
        });

        const tl = gsap.timeline({
          repeat: -1,
          delay,
          defaults: { ease: "none" },
        });

        tl.to(petal, {
          keyframes: [
            {
              x: `${startXVw}vw`,
              y: `${startYVh}vh`,
              duration: 0,
            },
            {
              x: `+=${swayRange * 0.6}`,
              y: `+=${vh * 0.2}`,
              duration: duration * 0.25,
            },
            {
              x: `-=${swayRange}`,
              y: `+=${vh * 0.25}`,
              duration: duration * 0.25,
            },
            {
              x: `+=${swayRange * 0.8}`,
              y: `+=${vh * 0.25}`,
              duration: duration * 0.25,
            },
            {
              x: `-=${swayRange * 0.4}`,
              y: `${vh + 50}`,
              duration: duration * 0.25,
            },
          ],
        });

        gsap.to(petal, {
          rotation: `+=${gsap.utils.random(270, 540)}`,
          duration: gsap.utils.random(4, 8),
          repeat: -1,
          ease: "none",
          delay,
        });

        if (performance !== "low") {
          gsap.to(petal, {
            scale: gsap.utils.random(0.8, 1.15),
            duration: gsap.utils.random(3, 6),
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
            delay: gsap.utils.random(0, 3),
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
      <SakuraTree />
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="petal"
          style={{
            position: "absolute",
            willChange: "transform, opacity",
          }}
        />
      ))}
    </div>
  );
}
