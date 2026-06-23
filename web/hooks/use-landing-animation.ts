"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";

export function useLandingAnimation() {
  useGSAP((_, contextSafe) => {
    const mm = gsap.matchMedia();

    mm.add(
      {
        isDesktop: "(min-width: 992px)",
        isCompact: "(max-width: 767px)",
        reduceMotion: "(prefers-reduced-motion: reduce)",
      },
      (context) => {
        const { isDesktop, isCompact, reduceMotion } = context.conditions ?? {};

        if (reduceMotion) {
          gsap.set(
            ".landing-nav, .landing-hero__text, .landing-hero__demo, .landing-section, .landing-cta, .landing-feature-card, .landing-step, .robot-row, .robot-arm__draw, .robot-arm__tip, .landing-hero__stats, .landing-hero__actions, .landing-cta__card",
            { autoAlpha: 1 },
          );
          gsap.set(".robot-arm__draw", { strokeDashoffset: 0 });
          gsap.set(".robot-row", { autoAlpha: 1 });
          return;
        }

        if (!isCompact) {
          // ===== 背景光晕漂移 =====
          gsap.to(".landing-bg-orb--blue", {
            x: "10vw", y: "6vh", scale: 1.05,
            duration: 18, repeat: -1, yoyo: true, ease: "sine.inOut",
          });
          gsap.to(".landing-bg-orb--pink", {
            x: "-6vw", y: "-8vh", scale: 1.08,
            duration: 15, repeat: -1, yoyo: true, ease: "sine.inOut",
          });
        }

        // ===== 机器人写日历 =====
        let robotTl: gsap.core.Timeline | null = null;
        if (!isCompact) {
          robotTl = gsap.timeline({ repeat: -1, defaults: { ease: "power2.inOut" } });

          // 1. 手臂伸出（stroke 从无到有）
          robotTl.to(".robot-arm__draw", {
            strokeDashoffset: 0,
            duration: 0.9,
            ease: "power2.out",
          });

          // 2. 笔尖发光 + 第一行出现
          robotTl.to(".robot-arm__tip", { scale: 1.8, duration: 0.3 }, "-=0.3");
          robotTl.to(".robot-row--1", { autoAlpha: 1, duration: 0.35 }, "-=0.2");
          robotTl.to(".robot-arm__tip", { scale: 1, duration: 0.25 });

          // 3. 笔尖微颤 + 第二行出现
          robotTl.to(".robot-arm__pen", { x: 2, duration: 0.12 }, "-=0.1");
          robotTl.to(".robot-arm__pen", { x: 0, duration: 0.12 });
          robotTl.to(".robot-row--2", { autoAlpha: 1, duration: 0.35 }, "-=0.25");
          robotTl.to(".robot-arm__tip", { scale: 1.8, duration: 0.3 }, "-=0.2");
          robotTl.to(".robot-arm__tip", { scale: 1, duration: 0.25 });

          // 4. 笔尖微颤 + 第三行出现
          robotTl.to(".robot-arm__pen", { x: 2, duration: 0.12 });
          robotTl.to(".robot-arm__pen", { x: 0, duration: 0.12 });
          robotTl.to(".robot-row--3", { autoAlpha: 1, duration: 0.35 }, "-=0.25");
          robotTl.to(".robot-arm__tip", { scale: 1.8, duration: 0.3 }, "-=0.2");
          robotTl.to(".robot-arm__tip", { scale: 1, duration: 0.25 });

          // 5. 写完后短暂停顿，然后手臂收回
          robotTl.to({}, { duration: 0.8 });
          robotTl.to(".robot-row", { autoAlpha: 0, duration: 0.25 });
          robotTl.to(".robot-arm__draw", {
            strokeDashoffset: 140,
            duration: 0.7,
            ease: "power2.in",
          }, "-=0.2");

          // 6. 停顿后重新循环
          robotTl.to({}, { duration: 0.6 });
        } else {
          gsap.set(".robot-arm__draw", { strokeDashoffset: 0 });
          gsap.set(".robot-arm__tip", { scale: 1 });
          gsap.set(".robot-row", { autoAlpha: 1 });
        }

        // ===== 导航栏 =====
        gsap.from(".landing-nav", {
          y: -24, autoAlpha: 0, duration: 0.6, ease: "power3.out",
        });

        // ===== Hero 入场 =====
        const heroTl = gsap.timeline({
          defaults: { ease: "power3.out" },
          delay: isCompact ? 0 : 0.1,
        });

        heroTl.from(".landing-hero__badge", { y: isCompact ? 18 : 28, autoAlpha: 0, duration: isCompact ? 0.4 : 0.6 });
        heroTl.from(".landing-hero__title", { y: isCompact ? 24 : 36, autoAlpha: 0, duration: isCompact ? 0.5 : 0.7 }, "-=0.25");
        heroTl.from(".landing-hero__subtitle", { y: isCompact ? 18 : 24, autoAlpha: 0, duration: isCompact ? 0.42 : 0.6 }, "-=0.2");
        heroTl.from(".landing-hero__actions", { y: isCompact ? 16 : 20, autoAlpha: 0, duration: isCompact ? 0.4 : 0.5 }, "-=0.15");
        heroTl.from(".landing-hero__stats", { y: isCompact ? 12 : 16, autoAlpha: 0, duration: isCompact ? 0.38 : 0.5 }, "-=0.1");

        if (isDesktop) {
          heroTl.from(".landing-hero__demo", { x: 60, autoAlpha: 0, duration: 0.8 }, "-=0.5");
        } else {
          heroTl.from(".landing-hero__demo", { y: isCompact ? 24 : 40, autoAlpha: 0, duration: isCompact ? 0.45 : 0.7 }, isCompact ? "-=0.2" : "-=0.3");
        }

        const animateFeatures = (contextSafe ?? ((fn: () => void) => fn))(() => {
          gsap.from(".landing-feature-card", {
            y: isCompact ? 28 : 50,
            autoAlpha: 0,
            duration: isCompact ? 0.5 : 0.7,
            stagger: isCompact ? 0.08 : 0.12,
            ease: "power3.out",
            clearProps: "transform",
          });
        });

        const animateSteps = (contextSafe ?? ((fn: () => void) => fn))(() => {
          gsap.from(".landing-step", {
            y: isCompact ? 24 : 40,
            autoAlpha: 0,
            duration: isCompact ? 0.5 : 0.7,
            stagger: isCompact ? 0.1 : 0.18,
            ease: "power3.out",
            clearProps: "transform",
          });
        });

        const animateCta = (contextSafe ?? ((fn: () => void) => fn))(() => {
          gsap.from(".landing-cta__card", {
            y: isCompact ? 24 : 50,
            autoAlpha: 0,
            scale: isCompact ? 0.985 : 0.97,
            duration: isCompact ? 0.6 : 0.9,
            ease: "power3.out",
            clearProps: "transform",
          });
        });

        // ===== 特性卡片（滚动触发） =====
        const featureObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              featureObserver.unobserve(entry.target);
              animateFeatures();
            }
          },
          { threshold: 0.1 },
        );
        const features = document.getElementById("features");
        if (features) featureObserver.observe(features);

        // ===== 步骤区 =====
        const stepObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              stepObserver.unobserve(entry.target);
              animateSteps();
            }
          },
          { threshold: 0.15 },
        );
        const steps = document.getElementById("steps");
        if (steps) stepObserver.observe(steps);

        // ===== CTA =====
        const ctaObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              ctaObserver.unobserve(entry.target);
              animateCta();
            }
          },
          { threshold: 0.2 },
        );
        const cta = document.querySelector(".landing-cta");
        if (cta) ctaObserver.observe(cta);

        return () => {
          robotTl?.kill();
          featureObserver.disconnect();
          stepObserver.disconnect();
          ctaObserver.disconnect();
        };
      },
    );
  });
}
