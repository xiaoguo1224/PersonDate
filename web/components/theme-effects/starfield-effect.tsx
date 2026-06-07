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
  low: 150,
  medium: 250,
  high: 400,
};

const STAR_COLORS = [
  (a: number) => `rgba(255, 255, 255, ${a})`,
  (a: number) => `rgba(255, 253, 220, ${a})`,
  (a: number) => `rgba(212, 168, 83, ${a})`,
  (a: number) => `rgba(200, 210, 255, ${a})`,
];

function createMeteor(container: HTMLDivElement, accentColor: string) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = gsap.utils.random(150, 250);

  const meteor = document.createElement("div");
  Object.assign(meteor.style, {
    position: "absolute",
    width: `${width}px`,
    height: "4px",
    background: `linear-gradient(90deg, transparent, ${accentColor}aa, ${accentColor}, #fff)`,
    borderRadius: "2px",
    pointerEvents: "none",
    willChange: "transform, opacity",
    boxShadow: `0 0 12px 3px ${accentColor}88, 0 0 30px 6px ${accentColor}44, 0 0 60px 10px ${accentColor}22`,
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
    .to(
      nebula,
      {
        x: startX + gsap.utils.random(-100, 100),
        y: startY + gsap.utils.random(-80, 80),
        duration: gsap.utils.random(15, 25),
        ease: "sine.inOut",
      },
      0
    )
    .to(nebula, {
      opacity: 0,
      duration: gsap.utils.random(4, 8),
      ease: "sine.inOut",
    });
}

function createMilkyWay(container: HTMLDivElement) {
  const milkyWay = document.createElement("div");
  Object.assign(milkyWay.style, {
    position: "absolute",
    top: "10%",
    left: "-10%",
    width: "120%",
    height: "30%",
    background:
      "linear-gradient(135deg, transparent 20%, rgba(255,255,255,0.03) 40%, rgba(200,200,255,0.05) 50%, rgba(255,255,255,0.03) 60%, transparent 80%)",
    transform: "rotate(-15deg)",
    filter: "blur(20px)",
    pointerEvents: "none",
  });
  container.appendChild(milkyWay);

  gsap.to(milkyWay, {
    rotation: 3,
    duration: 120,
    repeat: -1,
    yoyo: true,
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
        const size = gsap.utils.random(0.5, 3);
        const x = gsap.utils.random(0, 100);
        const y = gsap.utils.random(0, 100);
        const colorFn =
          STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
        const alpha = gsap.utils.random(0.3, 0.9);

        gsap.set(star, {
          x: `${x}vw`,
          y: `${y}vh`,
          width: size,
          height: size,
          borderRadius: "50%",
          backgroundColor: colorFn(alpha),
        });

        const flickerSpeed = gsap.utils.random(0.4, 3.0);
        gsap.to(star, {
          opacity: gsap.utils.random(0.1, 1),
          duration: flickerSpeed,
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

      // 银河带（所有性能等级）
      createMilkyWay(container);

      // 流星（medium/high）
      if (performance !== "low") {
        const meteorCtx = gsap.context(() => {
          const spawnMeteor = () => {
            createMeteor(container, accentColor);
            gsap.delayedCall(gsap.utils.random(2, 4), spawnMeteor);
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
            gsap.delayedCall(gsap.utils.random(15, 25), spawnNebula);
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
