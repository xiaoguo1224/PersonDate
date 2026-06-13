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
  low: 260,
  medium: 420,
  high: 650,
};

const STAR_COLORS = [
  (a: number) => `rgba(255, 255, 255, ${a})`,
  (a: number) => `rgba(255, 252, 224, ${a})`,
  (a: number) => `rgba(212, 168, 83, ${a})`,
  (a: number) => `rgba(200, 210, 255, ${a})`,
];

function createMeteor(container: HTMLDivElement, accentColor: string) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = gsap.utils.random(140, 260);

  const meteor = document.createElement("div");
  Object.assign(meteor.style, {
    position: "absolute",
    width: `${width}px`,
    height: "4px",
    borderRadius: "999px",
    pointerEvents: "none",
    willChange: "transform, opacity",
    background: `linear-gradient(90deg, transparent 0%, ${accentColor}aa 58%, ${accentColor} 82%, #fff 100%)`,
    boxShadow: `0 0 12px 3px ${accentColor}88, 0 0 30px 6px ${accentColor}44, 0 0 60px 10px ${accentColor}22`,
  });
  container.appendChild(meteor);

  gsap.fromTo(
    meteor,
    {
      x: gsap.utils.random(vw * 0.25, vw + 120),
      y: gsap.utils.random(-90, -20),
      opacity: 0,
      rotation: gsap.utils.random(28, 42),
    },
    {
      x: gsap.utils.random(-340, -120),
      y: vh * gsap.utils.random(0.45, 0.82),
      opacity: 1,
      duration: gsap.utils.random(1.0, 1.8),
      ease: "none",
      onUpdate: function () {
        const progress = this.progress();
        if (progress > 0.62) {
          meteor.style.opacity = String(1 - (progress - 0.62) / 0.38);
        }
      },
      onComplete: () => {
        meteor.remove();
      },
    },
  );
}

function createNebula(container: HTMLDivElement, accentColor: string) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const size = gsap.utils.random(180, 360);

  const nebula = document.createElement("div");
  Object.assign(nebula.style, {
    position: "absolute",
    width: `${size}px`,
    height: `${size}px`,
    borderRadius: "50%",
    pointerEvents: "none",
    willChange: "transform, opacity",
    background: `radial-gradient(circle, ${accentColor}26, ${accentColor}0b 52%, transparent 74%)`,
    filter: "blur(30px)",
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
    opacity: gsap.utils.random(0.28, 0.56),
    duration: gsap.utils.random(4, 7),
    ease: "sine.inOut",
  })
    .to(
      nebula,
      {
        x: startX + gsap.utils.random(-120, 120),
        y: startY + gsap.utils.random(-90, 90),
        duration: gsap.utils.random(14, 24),
        ease: "sine.inOut",
      },
      0,
    )
    .to(nebula, {
      opacity: 0,
      duration: gsap.utils.random(4, 7),
      ease: "sine.inOut",
    });
}

function createConstellation(container: HTMLDivElement) {
  const clusters = [
    { left: "10%", top: "26%", width: "240px", rotate: "-12deg" },
    { left: "62%", top: "18%", width: "320px", rotate: "8deg" },
    { left: "46%", top: "64%", width: "200px", rotate: "18deg" },
  ];

  clusters.forEach((cluster, index) => {
    const line = document.createElement("div");
    Object.assign(line.style, {
      position: "absolute",
      left: cluster.left,
      top: cluster.top,
      width: cluster.width,
      height: "1px",
      transform: `rotate(${cluster.rotate})`,
      transformOrigin: "left center",
      pointerEvents: "none",
      opacity: String(0.16 + index * 0.04),
      background:
        "linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.48), rgba(212, 168, 83, 0.58), rgba(255, 255, 255, 0.12), transparent)",
      filter: "blur(0.2px)",
    });
    container.appendChild(line);

    gsap.to(line, {
      opacity: `+=${gsap.utils.random(0.05, 0.12)}`,
      duration: gsap.utils.random(5, 9),
      repeat: -1,
      yoyo: true,
      ease: "sine.inOut",
    });
  });
}

function createAurora(container: HTMLDivElement) {
  const aurora = document.createElement("div");
  Object.assign(aurora.style, {
    position: "absolute",
    inset: "-10% -15% auto -15%",
    height: "42vh",
    pointerEvents: "none",
    opacity: "0.52",
    background:
      "linear-gradient(90deg, transparent 0%, rgba(212, 168, 83, 0.12) 18%, rgba(255, 255, 255, 0.06) 42%, rgba(212, 168, 83, 0.12) 60%, transparent 100%)",
    filter: "blur(34px)",
    transform: "rotate(-10deg)",
    mixBlendMode: "screen",
  });
  container.appendChild(aurora);

  gsap.to(aurora, {
    x: "4vw",
    y: "2vh",
    scale: 1.03,
    duration: 16,
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

      const accentColor =
        getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#d4a853";

      stars.forEach((star) => {
        const size = gsap.utils.random(0.6, 3.8);
        const x = gsap.utils.random(0, 100);
        const y = gsap.utils.random(0, 100);
        const colorFn = STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
        const alpha = gsap.utils.random(0.34, 1);
        const hasGlow = size > 2.1 && Math.random() > 0.65;
        const twinkle = gsap.utils.random(0.8, 3.5);

        gsap.set(star, {
          x: `${x}vw`,
          y: `${y}vh`,
          width: size,
          height: size,
          borderRadius: "50%",
          backgroundColor: colorFn(alpha),
          boxShadow: hasGlow
            ? `0 0 ${size * 2}px ${colorFn(0.36)}, 0 0 ${size * 4}px ${colorFn(0.16)}`
            : "none",
        });

        gsap.to(star, {
          opacity: gsap.utils.random(0.22, 1),
          duration: twinkle,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          delay: gsap.utils.random(0, 4),
        });

        if (Math.random() > 0.94) {
          gsap.to(star, {
            scale: gsap.utils.random(1.08, 1.45),
            duration: gsap.utils.random(1.8, 4.2),
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
            delay: gsap.utils.random(0, 3),
          });
        }
      });

      createAurora(container);
      createConstellation(container);

      const cleanupFns: Array<() => void> = [];

      if (performance !== "low") {
        const meteorCtx = gsap.context(() => {
          const spawnMeteor = () => {
            createMeteor(container, accentColor);
            gsap.delayedCall(gsap.utils.random(2.5, 4.5), spawnMeteor);
          };
          gsap.delayedCall(gsap.utils.random(2, 4), spawnMeteor);
        });
        cleanupFns.push(() => meteorCtx.revert());
      }

      if (performance === "high") {
        const nebulaCtx = gsap.context(() => {
          const spawnNebula = () => {
            createNebula(container, accentColor);
            gsap.delayedCall(gsap.utils.random(14, 24), spawnNebula);
          };
          gsap.delayedCall(gsap.utils.random(4, 10), spawnNebula);
        });
        cleanupFns.push(() => nebulaCtx.revert());
      }

      gsap.fromTo(
        container,
        { opacity: 0 },
        { opacity: 1, duration: 0.8, ease: "power2.out" },
      );

      return () => {
        cleanupFns.forEach((fn) => fn());
      };
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
            "radial-gradient(circle at 18% 18%, rgba(212, 168, 83, 0.1), transparent 22%), radial-gradient(circle at 82% 14%, rgba(125, 211, 252, 0.08), transparent 20%), radial-gradient(circle at 52% 8%, rgba(255, 255, 255, 0.08), transparent 26%)",
          opacity: 0.95,
          mixBlendMode: "screen",
        }}
      />
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
