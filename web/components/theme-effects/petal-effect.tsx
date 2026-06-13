"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useRef } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface SakuraEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 32,
  medium: 54,
  high: 84,
};

const PETAL_COLORS = [
  "#FFB7C5",
  "#FFC0CB",
  "#FF8FB1",
  "#FF69B4",
  "#FFD1DC",
  "#fff0f5",
];

function SakuraTree() {
  const blossomSpots = [
    { left: -170, top: -380, size: 280, opacity: 0.5 },
    { left: -35, top: -460, size: 360, opacity: 0.58 },
    { left: 110, top: -390, size: 290, opacity: 0.48 },
    { left: -220, top: -250, size: 210, opacity: 0.38 },
    { left: 10, top: -290, size: 240, opacity: 0.44 },
    { left: 180, top: -240, size: 190, opacity: 0.34 },
    { left: -110, top: -200, size: 230, opacity: 0.45 },
    { left: 60, top: -180, size: 220, opacity: 0.4 },
    { left: -160, top: -120, size: 180, opacity: 0.28 },
    { left: 140, top: -100, size: 170, opacity: 0.26 },
    { left: -70, top: -520, size: 170, opacity: 0.18 },
    { left: 210, top: -470, size: 150, opacity: 0.16 },
  ];

  const branchStyle = {
    position: "absolute" as const,
    bottom: 0,
    left: "50%",
    transformOrigin: "center bottom",
    background: "linear-gradient(180deg, #6c4a3b, #4d362a 60%, #37251e)",
    boxShadow: "0 10px 28px rgba(68, 47, 38, 0.18)",
    borderRadius: 999,
  };

  return (
    <div
      className="sakura-tree"
      style={{
        position: "fixed",
        left: "26%",
        bottom: "-10%",
        width: 900,
        height: 980,
        pointerEvents: "none",
        zIndex: 0,
        transformOrigin: "50% 100%",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "12% 8% auto 0",
          height: "48%",
          background:
            "radial-gradient(circle at 50% 45%, rgba(255, 192, 203, 0.4), transparent 30%), radial-gradient(circle at 40% 40%, rgba(255, 183, 197, 0.34), transparent 34%), radial-gradient(circle at 60% 32%, rgba(255, 240, 245, 0.26), transparent 36%)",
          filter: "blur(24px)",
          opacity: 0.72,
          mixBlendMode: "screen",
        }}
      />
      <div
        style={{
          ...branchStyle,
          left: "50%",
          bottom: 0,
          width: 70,
          height: 500,
          transform: "translateX(-50%)",
        }}
      />
      <div
        style={{
          ...branchStyle,
          width: 180,
          height: 16,
          bottom: 245,
          transform: "translateX(-70%) rotate(-26deg)",
        }}
      />
      <div
        style={{
          ...branchStyle,
          width: 160,
          height: 14,
          bottom: 300,
          transform: "translateX(-6%) rotate(18deg)",
        }}
      />
      <div
        style={{
          ...branchStyle,
          width: 150,
          height: 12,
          bottom: 185,
          transform: "translateX(-38%) rotate(-12deg)",
        }}
      />
      <div
        style={{
          ...branchStyle,
          width: 128,
          height: 11,
          bottom: 360,
          transform: "translateX(20%) rotate(28deg)",
        }}
      />
      <div
        style={{
          ...branchStyle,
          width: 112,
          height: 10,
          bottom: 430,
          transform: "translateX(34%) rotate(36deg)",
        }}
      />

      <div
        className="sakura-tree__crown"
        style={{
          position: "absolute",
          inset: 0,
          mixBlendMode: "screen",
        }}
      >
        {blossomSpots.map((spot, i) => (
          <div
            key={i}
            className="sakura-tree__bloom"
            style={{
              position: "absolute",
              left: "50%",
              bottom: 420 + spot.top * -0.08,
              marginLeft: spot.left,
              width: spot.size,
              height: spot.size,
              borderRadius: "50%",
              background:
                "radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.95), rgba(255, 192, 203, 0.52) 44%, rgba(255, 183, 197, 0.22) 68%, transparent 84%)",
              opacity: spot.opacity,
              filter: `blur(${spot.size > 240 ? 4 : 2}px)`,
              transform: `translateY(${spot.top * 0.02}px)`,
            }}
          />
        ))}
      </div>

      <div
        style={{
          position: "absolute",
          left: "32%",
          bottom: 110,
          width: 300,
          height: 140,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(255, 182, 193, 0.22), rgba(255, 182, 193, 0.1) 52%, transparent 78%)",
          filter: "blur(16px)",
          opacity: 0.9,
        }}
      />

      <div
        style={{
          position: "absolute",
          left: "50%",
          bottom: 0,
          width: 520,
          height: 120,
          transform: "translateX(-58%)",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(232, 67, 147, 0.16), rgba(232, 67, 147, 0.08) 45%, transparent 74%)",
          filter: "blur(18px)",
          opacity: 0.85,
        }}
      />
    </div>
  );
}

export default function SakuraEffect({
  visible,
  onFadeOutComplete,
}: SakuraEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const performance = usePerformance();
  const count = COUNT_MAP[performance];

  useGSAP(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const petals = container.querySelectorAll<HTMLDivElement>(".petal");
      if (!petals.length) return;

      const vh = window.innerHeight;
      const startXVw = [7, 10, 13, 17, 20, 24, 28];

      petals.forEach((petal, index) => {
        const size = gsap.utils.random(6, 16);
        const color = PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)];
        const xIndex = index % startXVw.length;
        const startXVwValue = gsap.utils.random(startXVw[xIndex] - 4, startXVw[xIndex] + 8);
        const startYVh = gsap.utils.random(8, 40);
        const duration = gsap.utils.random(6, 14);
        const delay = gsap.utils.random(0, 10);
        const swayRange = gsap.utils.random(34, 120);

        gsap.set(petal, {
          x: `${startXVwValue}vw`,
          y: `${startYVh}vh`,
          width: size,
          height: size * 0.66,
          opacity: gsap.utils.random(0.52, 0.9),
          backgroundColor: color,
          borderRadius: "50% 0 50% 0",
          rotation: gsap.utils.random(0, 360),
          filter: "drop-shadow(0 0 4px rgba(255, 183, 197, 0.18))",
        });

        gsap.timeline({
          repeat: -1,
          delay,
          defaults: { ease: "none" },
        }).to(petal, {
          keyframes: [
            { x: `${startXVwValue}vw`, y: `${startYVh}vh`, duration: 0 },
            {
              x: `+=${swayRange * 0.45}`,
              y: `+=${vh * 0.18}`,
              duration: duration * 0.24,
            },
            {
              x: `-=${swayRange * 0.85}`,
              y: `+=${vh * 0.22}`,
              duration: duration * 0.24,
            },
            {
              x: `+=${swayRange * 0.65}`,
              y: `+=${vh * 0.26}`,
              duration: duration * 0.26,
            },
            {
              x: `-=${swayRange * 0.35}`,
              y: `${vh + 60}`,
              duration: duration * 0.26,
            },
          ],
        });

        gsap.to(petal, {
          rotation: `+=${gsap.utils.random(240, 720)}`,
          duration: gsap.utils.random(3, 8),
          repeat: -1,
          ease: "none",
          delay,
        });

        if (performance === "high") {
          gsap.to(petal, {
            scale: gsap.utils.random(0.74, 1.15),
            duration: gsap.utils.random(2.4, 5.2),
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
            delay: gsap.utils.random(0, 3),
          });
        }
      });

      gsap.to(".sakura-tree", {
        rotation: -1.5,
        duration: 6,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        transformOrigin: "50% 100%",
      });
      gsap.to(".sakura-tree__crown", {
        y: -6,
        duration: 5,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
      });

      gsap.fromTo(
        container,
        { opacity: 0 },
        { opacity: 1, duration: 0.9, ease: "power2.out" },
      );
    },
    { scope: containerRef, dependencies: [count, performance] },
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
        willChange: "transform, opacity",
      }}
      aria-hidden="true"
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 22% 12%, rgba(255, 255, 255, 0.6), transparent 18%), radial-gradient(circle at 78% 10%, rgba(255, 192, 203, 0.28), transparent 20%), radial-gradient(circle at 50% 0%, rgba(255, 183, 197, 0.18), transparent 28%)",
          opacity: 0.96,
        }}
      />
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
