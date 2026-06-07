"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useRef } from "react";

const PARTICLE_COUNT = 18;

export default function BackgroundAnimation() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const container = containerRef.current;
    if (!container) return;

    const dots = container.querySelectorAll<HTMLDivElement>(".bg-particle");
    if (!dots.length) return;

    dots.forEach((dot) => {
      const x = gsap.utils.random(0, 100);
      const y = gsap.utils.random(0, 100);
      const size = gsap.utils.random(2, 5);
      const duration = gsap.utils.random(12, 25);
      const delay = gsap.utils.random(0, 10);

      gsap.set(dot, {
        x: `${x}vw`,
        y: `${y}vh`,
        width: size,
        height: size,
        opacity: gsap.utils.random(0.08, 0.2),
      });

      gsap.to(dot, {
        y: `+=${gsap.utils.random(-15, 15)}vh`,
        x: `+=${gsap.utils.random(-10, 10)}vw`,
        opacity: gsap.utils.random(0.02, 0.12),
        duration,
        delay,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
      });
    });

    const lines = container.querySelectorAll<HTMLDivElement>(".bg-line");
    if (lines.length) {
      gsap.fromTo(
        lines,
        { scaleX: 0, transformOrigin: "left" },
        {
          scaleX: 1,
          duration: 2,
          stagger: 0.15,
          ease: "power3.out",
          delay: 0.5,
        },
      );
    }
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="dashboard-bg-animation" aria-hidden="true">
      {Array.from({ length: PARTICLE_COUNT }).map((_, i) => (
        <div key={i} className="bg-particle" />
      ))}
      <div className="bg-line" style={{ top: "15%", left: "5%", width: "90%", opacity: 0.03 }} />
      <div className="bg-line" style={{ top: "45%", left: "10%", width: "80%", opacity: 0.02 }} />
      <div className="bg-line" style={{ top: "75%", left: "3%", width: "94%", opacity: 0.025 }} />
    </div>
  );
}
