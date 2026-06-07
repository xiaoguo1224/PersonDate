"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useRef } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface PetalEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 8,
  medium: 15,
  high: 20,
};

const PETAL_COLORS = ["#e84393", "#fd79a8", "#fab1a0"];

export default function PetalEffect({
  visible,
  onFadeOutComplete,
}: PetalEffectProps) {
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
      const vw = window.innerWidth;

      petals.forEach((petal) => {
        const size = gsap.utils.random(15, 30);
        const startX = gsap.utils.random(5, 95);
        const color =
          PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)];
        const duration = gsap.utils.random(10, 18);
        const delay = gsap.utils.random(0, 12);
        const swayAmount = gsap.utils.random(30, 80);

        gsap.set(petal, {
          x: `${startX}vw`,
          y: -50,
          width: size,
          height: size * 0.7,
          opacity: gsap.utils.random(0.3, 0.7),
          backgroundColor: color,
          borderRadius: "50% 0 50% 0",
          transform: `rotate(${gsap.utils.random(0, 360)}deg)`,
        });

        const tl = gsap.timeline({
          repeat: -1,
          delay,
          defaults: { ease: "none" },
        });

        const keyframes = [
          { x: `${startX}vw`, y: -50 },
          {
            x: `${startX + (swayAmount / vw) * 100}vw`,
            y: vh * 0.25,
          },
          { x: `${startX}vw`, y: vh * 0.5 },
          {
            x: `${startX - (swayAmount / vw) * 100}vw`,
            y: vh * 0.75,
          },
          { x: `${startX}vw`, y: vh + 50 },
        ];

        tl.to(petal, {
          keyframes: keyframes.map((kf) => ({
            ...kf,
            duration: duration / 4,
          })),
        });

        gsap.to(petal, {
          rotation: "+=360",
          duration: gsap.utils.random(4, 8),
          repeat: -1,
          ease: "none",
          delay,
        });

        if (performance === "high") {
          gsap.to(petal, {
            scale: gsap.utils.random(0.8, 1.2),
            duration: gsap.utils.random(3, 6),
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
            delay,
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
