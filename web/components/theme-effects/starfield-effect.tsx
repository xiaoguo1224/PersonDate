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
  low: 100,
  medium: 150,
  high: 200,
};

function createMeteor(container: HTMLDivElement, accentColor: string) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = gsap.utils.random(120, 220);

  const meteor = document.createElement("div");
  Object.assign(meteor.style, {
    position: "absolute",
    width: `${width}px`,
    height: "3px",
    background: `linear-gradient(90deg, transparent, ${accentColor}88, ${accentColor})`,
    borderRadius: "2px",
    pointerEvents: "none",
    willChange: "transform, opacity",
    boxShadow: `0 0 8px 2px ${accentColor}66, 0 0 20px 4px ${accentColor}33`,
  });
  container.appendChild(meteor);

  gsap.fromTo(
    meteor,
    {
      x: gsap.utils.random(vw * 0.3, vw + 100),
      y: gsap.utils.random(-80, -20),
      opacity: 0,
      rotation: gsap.utils.random(30, 45),
    },
    {
      x: gsap.utils.random(-300, -100),
      y: vh * gsap.utils.random(0.5, 0.8),
      opacity: 1,
      duration: gsap.utils.random(1.0, 2.0),
      ease: "none",
      onUpdate: function () {
        const progress = this.progress();
        if (progress > 0.6) {
          meteor.style.opacity = String(1 - (progress - 0.6) / 0.4);
        }
      },
      onComplete: () => {
        meteor.remove();
      },
    }
  );
}

function createNebula(container: HTMLDivElement, accentColor: string) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const size = gsap.utils.random(150, 350);

  const nebula = document.createElement("div");
  Object.assign(nebula.style, {
    position: "absolute",
    width: `${size}px`,
    height: `${size}px`,
    borderRadius: "50%",
    background: `radial-gradient(circle, ${accentColor}18, ${accentColor}08, transparent)`,
    filter: "blur(30px)",
    pointerEvents: "none",
    willChange: "transform, opacity",
  });
  container.appendChild(nebula);

  const startX = gsap.utils.random(0, vw - size);
  const startY = gsap.utils.random(0, vh - size);

  gsap.set(nebula, { x: startX, y: startY, opacity: 0 });

  const tl = gsap.timeline({
    onComplete: () => {
      nebula.remove();
    },
  });

  tl.to(nebula, {
    opacity: gsap.utils.random(0.3, 0.6),
    duration: gsap.utils.random(4, 8),
    ease: "sine.inOut",
  })
    .to(nebula, {
      x: startX + gsap.utils.random(-100, 100),
      y: startY + gsap.utils.random(-80, 80),
      duration: gsap.utils.random(15, 25),
      ease: "sine.inOut",
    }, 0)
    .to(nebula, {
      opacity: 0,
      duration: gsap.utils.random(4, 8),
      ease: "sine.inOut",
    });
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
        const size = gsap.utils.random(1, 3);
        const x = gsap.utils.random(0, 100);
        const y = gsap.utils.random(0, 100);

        gsap.set(star, {
          x: `${x}vw`,
          y: `${y}vh`,
          width: size,
          height: size,
          borderRadius: "50%",
          backgroundColor: `rgba(212, 168, 83, ${gsap.utils.random(0.3, 0.8)})`,
        });

        gsap.to(star, {
          opacity: gsap.utils.random(0.15, 1),
          duration: gsap.utils.random(0.8, 2.5),
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          delay: gsap.utils.random(0, 3),
        });
      });

      const accentColor =
        getComputedStyle(document.documentElement)
          .getPropertyValue("--accent")
          .trim() || "#d4a853";

      const cleanupFns: Array<() => void> = [];

      // 流星（medium/high）
      if (performance !== "low") {
        const meteorCtx = gsap.context(() => {
          const spawnMeteor = () => {
            createMeteor(container, accentColor);
            gsap.delayedCall(gsap.utils.random(3, 5), spawnMeteor);
          };
          gsap.delayedCall(gsap.utils.random(2, 4), spawnMeteor);
        });
        cleanupFns.push(() => meteorCtx.revert());
      }

      // 星云（high only）
      if (performance === "high") {
        const nebulaCtx = gsap.context(() => {
          const spawnNebula = () => {
            createNebula(container, accentColor);
            gsap.delayedCall(gsap.utils.random(20, 35), spawnNebula);
          };
          gsap.delayedCall(gsap.utils.random(5, 12), spawnNebula);
        });
        cleanupFns.push(() => nebulaCtx.revert());
      }

      if (cleanupFns.length > 0) {
        return () => cleanupFns.forEach((fn) => fn());
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
