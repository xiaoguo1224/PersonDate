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
  low: 12,
  medium: 18,
  high: 28,
};

const PETAL_COLORS = [
  "#FFB7C5",
  "#FFC0CB",
  "#FF8FB1",
  "#FF69B4",
  "#FFD1DC",
  "#fff0f5",
];

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
      const startXVw = [6, 10, 15, 20, 26, 32];

      petals.forEach((petal, index) => {
        const size = gsap.utils.random(7, 15);
        const color = PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)];
        const xIndex = index % startXVw.length;
        const startXVwValue = gsap.utils.random(startXVw[xIndex] - 3, startXVw[xIndex] + 6);
        const startYVh = gsap.utils.random(-8, 34);
        const duration = gsap.utils.random(8, 16);
        const delay = gsap.utils.random(0, 8);
        const swayRange = gsap.utils.random(24, 96);

        gsap.set(petal, {
          x: `${startXVwValue}vw`,
          y: `${startYVh}vh`,
          width: size,
          height: size * 0.66,
          opacity: gsap.utils.random(0.4, 0.78),
          backgroundColor: color,
          borderRadius: "50% 0 50% 0",
          rotation: gsap.utils.random(0, 360),
          filter: "drop-shadow(0 0 6px rgba(255, 183, 197, 0.16))",
        });

        gsap.timeline({
          repeat: -1,
          delay,
          defaults: { ease: "none" },
        }).to(petal, {
          keyframes: [
            { x: `${startXVwValue}vw`, y: `${startYVh}vh`, duration: 0 },
            {
              x: `+=${swayRange * 0.42}`,
              y: `+=${vh * 0.16}`,
              duration: duration * 0.22,
            },
            {
              x: `-=${swayRange * 0.72}`,
              y: `+=${vh * 0.2}`,
              duration: duration * 0.22,
            },
            {
              x: `+=${swayRange * 0.56}`,
              y: `+=${vh * 0.25}`,
              duration: duration * 0.28,
            },
            {
              x: `-=${swayRange * 0.28}`,
              y: `${vh + 60}`,
              duration: duration * 0.28,
            },
          ],
        });

        gsap.to(petal, {
          rotation: `+=${gsap.utils.random(180, 540)}`,
          duration: gsap.utils.random(4, 9),
          repeat: -1,
          ease: "none",
          delay,
        });

        if (performance === "high") {
          gsap.to(petal, {
            scale: gsap.utils.random(0.82, 1.08),
            duration: gsap.utils.random(2.8, 6.2),
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
        { opacity: 1, duration: 0.8, ease: "power2.out" },
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
          "radial-gradient(circle at 22% 12%, rgba(255, 255, 255, 0.34), transparent 18%), radial-gradient(circle at 78% 10%, rgba(255, 192, 203, 0.2), transparent 20%), radial-gradient(circle at 50% 0%, rgba(255, 183, 197, 0.12), transparent 28%)",
        opacity: 0.9,
        filter: "blur(2px)",
      }}
    />
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
