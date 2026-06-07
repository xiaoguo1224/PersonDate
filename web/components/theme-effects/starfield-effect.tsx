"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useRef } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface StarfieldEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 30,
  medium: 50,
  high: 80,
};

const STAR_COLORS = ["#d4a853", "#f5d799", "#b8860b"];

function createMeteor(container: HTMLDivElement, accentColor: string) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = gsap.utils.random(80, 150);

  const meteor = document.createElement("div");
  Object.assign(meteor.style, {
    position: "absolute",
    width: `${width}px`,
    height: "2px",
    background: `linear-gradient(90deg, transparent, ${accentColor})`,
    borderRadius: "1px",
    pointerEvents: "none",
    willChange: "transform, opacity",
  });
  container.appendChild(meteor);

  gsap.fromTo(
    meteor,
    {
      x: vw + 50,
      y: -50,
      opacity: 0,
      rotation: 35,
    },
    {
      x: -200,
      y: vh * 0.6,
      opacity: 1,
      duration: gsap.utils.random(0.8, 1.5),
      ease: "none",
      onUpdate: function () {
        const progress = this.progress();
        if (progress > 0.7) {
          meteor.style.opacity = String(1 - (progress - 0.7) / 0.3);
        }
      },
      onComplete: () => {
        meteor.remove();
      },
    }
  );
}

export default function StarfieldEffect({
  visible,
  onFadeOutComplete,
}: StarfieldEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const performance = usePerformance();
  const count = COUNT_MAP[performance];

  useGSAP(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const stars = container.querySelectorAll<HTMLDivElement>(".star");
      if (!stars.length) return;

      stars.forEach((star) => {
        const size = gsap.utils.random(2, 4);
        const x = gsap.utils.random(0, 100);
        const y = gsap.utils.random(0, 100);
        const color =
          STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];

        gsap.set(star, {
          x: `${x}vw`,
          y: `${y}vh`,
          width: size,
          height: size,
          borderRadius: "50%",
          backgroundColor: color,
        });

        gsap.to(star, {
          opacity: gsap.utils.random(0.2, 1),
          duration: gsap.utils.random(1, 3),
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          delay: gsap.utils.random(0, 3),
        });
      });

      // 流星（medium/high）
      if (performance !== "low") {
        const accentColor =
          getComputedStyle(document.documentElement)
            .getPropertyValue("--accent")
            .trim() || "#d4a853";

        const meteorCtx = gsap.context(() => {
          const spawnMeteor = () => {
            createMeteor(container, accentColor);
            gsap.delayedCall(gsap.utils.random(5, 8), spawnMeteor);
          };
          gsap.delayedCall(gsap.utils.random(3, 6), spawnMeteor);
        });

        return () => {
          meteorCtx.revert();
        };
      }

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
          className="star"
          style={{
            position: "absolute",
            willChange: "transform, opacity",
          }}
        />
      ))}
    </div>
  );
}
