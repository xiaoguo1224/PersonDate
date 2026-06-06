"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";

export function useLandingAnimation() {
  useGSAP(() => {
    const mm = gsap.matchMedia();

    mm.add(
      {
        isDesktop: "(min-width: 992px)",
        reduceMotion: "(prefers-reduced-motion: reduce)",
      },
      (context) => {
        const { isDesktop, reduceMotion } = context.conditions ?? {};

        if (reduceMotion) {
          gsap.set(
            ".landing-nav, .landing-hero__text, .landing-hero__demo, .landing-section, .landing-cta, .landing-feature-card, .landing-step",
            { autoAlpha: 1 },
          );
          return;
        }

        // 粒子背景用 Canvas 已自带动画，不需要 GSAP 干预

        // 背景光晕漂移
        gsap.to(".landing-bg-orb--blue", {
          x: "10vw",
          y: "6vh",
          scale: 1.05,
          duration: 18,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
        });
        gsap.to(".landing-bg-orb--purple", {
          x: "-6vw",
          y: "-8vh",
          scale: 1.08,
          duration: 15,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
        });

        // ===== 导航栏 =====
        gsap.from(".landing-nav", {
          y: -24,
          autoAlpha: 0,
          duration: 0.6,
          ease: "power3.out",
        });

        // ===== Hero 区入场 =====
        const heroTl = gsap.timeline({ defaults: { ease: "power3.out" }, delay: 0.1 });

        heroTl.from(".landing-hero__badge", { y: 28, autoAlpha: 0, duration: 0.6 });
        heroTl.from(".landing-hero__title", { y: 36, autoAlpha: 0, duration: 0.7 }, "-=0.25");
        heroTl.from(".landing-hero__subtitle", { y: 24, autoAlpha: 0, duration: 0.6 }, "-=0.2");
        heroTl.from(".landing-hero__actions", { y: 20, autoAlpha: 0, duration: 0.5 }, "-=0.15");
        heroTl.from(".landing-hero__stats", { y: 16, autoAlpha: 0, duration: 0.5 }, "-=0.1");

        // 右侧 demo 面板从右侧滑入（桌面端）
        if (isDesktop) {
          heroTl.from(
            ".landing-hero__demo",
            { x: 60, autoAlpha: 0, duration: 0.8 },
            "-=0.5",
          );
        } else {
          heroTl.from(
            ".landing-hero__demo",
            { y: 40, autoAlpha: 0, duration: 0.7 },
            "-=0.3",
          );
        }

        // ===== 特性卡片（滚动触发） =====
        const featureObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              featureObserver.unobserve(entry.target);

              gsap.from(".landing-feature-card", {
                y: 50,
                autoAlpha: 0,
                duration: 0.7,
                stagger: 0.12,
                ease: "power3.out",
                clearProps: "transform",
              });
            }
          },
          { threshold: 0.1 },
        );

        const features = document.getElementById("features");
        if (features) featureObserver.observe(features);

        // ===== 步骤区（滚动触发） =====
        const stepObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              stepObserver.unobserve(entry.target);

              gsap.from(".landing-step", {
                y: 40,
                autoAlpha: 0,
                duration: 0.7,
                stagger: 0.18,
                ease: "power3.out",
                clearProps: "transform",
              });
            }
          },
          { threshold: 0.15 },
        );

        const steps = document.getElementById("steps");
        if (steps) stepObserver.observe(steps);

        // ===== CTA 区（滚动触发） =====
        const ctaObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              ctaObserver.unobserve(entry.target);

              gsap.from(".landing-cta__card", {
                y: 50,
                autoAlpha: 0,
                scale: 0.97,
                duration: 0.9,
                ease: "power3.out",
                clearProps: "transform",
              });
            }
          },
          { threshold: 0.2 },
        );

        const cta = document.querySelector(".landing-cta");
        if (cta) ctaObserver.observe(cta);

        return () => {
          featureObserver.disconnect();
          stepObserver.disconnect();
          ctaObserver.disconnect();
        };
      },
    );
  });
}
