"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useRef } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface BubbleEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 10,
  medium: 18,
  high: 25,
};

const BUBBLE_COLORS = ["#1677ff", "#40a9ff", "#69c0ff"];

export default function BubbleEffect({
  visible,
  onFadeOutComplete,
}: BubbleEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const performance = usePerformance();
  const count = COUNT_MAP[performance];

  useGSAP(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const bubbles = container.querySelectorAll<HTMLDivElement>(".bubble");
      if (!bubbles.length) return;

      const vh = window.innerHeight;

      bubbles.forEach((bubble) => {
        const size = gsap.utils.random(20, 80);
        const x = gsap.utils.random(5, 95);
        const color =
          BUBBLE_COLORS[Math.floor(Math.random() * BUBBLE_COLORS.length)];
        const duration = gsap.utils.random(8, 15);
        const delay = gsap.utils.random(0, 10);

        gsap.set(bubble, {
          x: `${x}vw`,
          y: vh + 50,
          width: size,
          height: size,
          opacity: gsap.utils.random(0.1, 0.4),
          borderRadius: "50%",
          backgroundColor: color,
          boxShadow: `0 0 ${size * 0.4}px ${color}40`,
        });

        const tl = gsap.timeline({ repeat: -1, delay });

        tl.to(bubble, {
          y: -100,
          duration,
          ease: "none",
        });

        if (performance === "high") {
          tl.to(
            bubble,
            {
              scale: 1.2,
              duration: 0.15,
              ease: "sine.out",
            },
            `-=${0.3}`
          );
          tl.to(bubble, {
            scale: 1,
            duration: 0.15,
            ease: "sine.in",
          });
        }
      });

      gsap.fromTo(
        container,
        { opacity: 0 },
        { opacity: 1, duration: 0.6, ease: "power2.out" }
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
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bubble"
          style={{
            position: "absolute",
            willChange: "transform, opacity",
          }}
        />
      ))}
    </div>
  );
}
