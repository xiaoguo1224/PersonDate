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
  low: 25,
  medium: 40,
  high: 60,
};

const PETAL_COLORS = [
  "#FFB7C5",
  "#FFC0CB",
  "#FF69B4",
  "#FF1493",
  "#FFD1DC",
  "#fff0f5",
];

function SakuraTree() {
  const trunkColor = "#4A3728";
  const branchColor = "#5D4037";

  const crownCircles = [
    { left: -120, top: -350, size: 250 },
    { left: 0, top: -420, size: 280 },
    { left: 120, top: -350, size: 240 },
    { left: -80, top: -280, size: 220 },
    { left: 60, top: -300, size: 200 },
    { left: -40, top: -380, size: 260 },
    { left: 80, top: -400, size: 230 },
    { left: -100, top: -320, size: 210 },
    { left: 40, top: -340, size: 190 },
    { left: -60, top: -400, size: 240 },
    { left: 100, top: -370, size: 220 },
    { left: -20, top: -360, size: 250 },
  ];

  const crownColors = [
    "rgba(255, 183, 197, 0.45)",
    "rgba(255, 192, 203, 0.4)",
    "rgba(255, 105, 180, 0.3)",
    "rgba(255, 20, 147, 0.2)",
    "rgba(255, 209, 220, 0.5)",
    "rgba(255, 240, 245, 0.55)",
  ];

  return (
    <div
      style={{
        position: "fixed",
        left: "-2%",
        bottom: 0,
        width: 500,
        height: 600,
        pointerEvents: "none",
        zIndex: 0,
      }}
    >
      {/* 主树干 */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: "50%",
          transform: "translateX(-50%)",
          width: 36,
          height: 320,
          backgroundColor: trunkColor,
          borderRadius: "12px 12px 16px 16px",
        }}
      />
      {/* 分叉枝干 1 */}
      <div
        style={{
          position: "absolute",
          bottom: 200,
          left: "50%",
          width: 80,
          height: 12,
          backgroundColor: branchColor,
          borderRadius: 6,
          transform: "translateX(-70%) rotate(-30deg)",
          transformOrigin: "right center",
        }}
      />
      {/* 分叉枝干 2 */}
      <div
        style={{
          position: "absolute",
          bottom: 250,
          left: "50%",
          width: 65,
          height: 10,
          backgroundColor: branchColor,
          borderRadius: 6,
          transform: "translateX(0%) rotate(25deg)",
          transformOrigin: "left center",
        }}
      />
      {/* 分叉枝干 3 */}
      <div
        style={{
          position: "absolute",
          bottom: 170,
          left: "50%",
          width: 70,
          height: 10,
          backgroundColor: branchColor,
          borderRadius: 6,
          transform: "translateX(-30%) rotate(-15deg)",
          transformOrigin: "right center",
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

      // 树冠区域的起始 x 范围
      const treeCenterVw = 12;
      const treeSpreadVw = 10;

      petals.forEach((petal) => {
        const size = gsap.utils.random(6, 15);
        const color =
          PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)];
        const startXVw = gsap.utils.random(
          treeCenterVw - treeSpreadVw,
          treeCenterVw + treeSpreadVw
        );
        const startYVh = gsap.utils.random(10, 40);
        const duration = gsap.utils.random(6, 14);
        const delay = gsap.utils.random(0, 10);
        const swayRange = gsap.utils.random(40, 120);

        gsap.set(petal, {
          x: `${startXVw}vw`,
          y: `${startYVh}vh`,
          width: size,
          height: size * 0.65,
          opacity: gsap.utils.random(0.5, 0.9),
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
          rotation: `+=${gsap.utils.random(270, 720)}`,
          duration: gsap.utils.random(3, 8),
          repeat: -1,
          ease: "none",
          delay,
        });

        // high 性能时花瓣有呼吸效果
        if (performance === "high") {
          gsap.to(petal, {
            scale: gsap.utils.random(0.7, 1.2),
            duration: gsap.utils.random(2, 5),
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
        background: "linear-gradient(180deg, #FFB7C5 0%, #FFC0CB 20%, #FFE4E9 50%, #fff0f5 100%)",
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
