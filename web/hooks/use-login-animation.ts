"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";

export function useLoginAnimation() {
  useGSAP(() => {
    const mm = gsap.matchMedia();

    mm.add(
      {
        reduceMotion: "(prefers-reduced-motion: reduce)",
        isCompact: "(max-width: 767px)",
      },
      (context) => {
        const { reduceMotion, isCompact } = context.conditions ?? {};

        if (reduceMotion) {
          gsap.set(
            ".auth-card, .auth-card__brand, .auth-card__header, .auth-card .ant-form-item, .auth-card .ant-btn-primary, .auth-card__divider, .auth-card__footer",
            {
              autoAlpha: 1,
              x: 0,
              y: 0,
              scale: 1,
            },
          );
          return;
        }

        if (!isCompact) {
          // 背景光晕持续漂移
          gsap.to(".auth-bg-orb--blue", {
            x: "12vw",
            y: "8vh",
            scale: 1.06,
            duration: 14,
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
          });
          gsap.to(".auth-bg-orb--purple", {
            x: "-8vw",
            y: "-6vh",
            scale: 1.1,
            duration: 16,
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut",
          });
        }

        // 卡片入场动画
        const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
        const entryDistance = isCompact ? 24 : 40;
        const cardScale = isCompact ? 0.985 : 0.97;
        const itemStagger = isCompact ? 0.04 : 0.08;
        const offset = isCompact ? "-=0.18" : "-=0.3";

        // 卡片整体：从下方淡入 + 轻微上浮
        tl.from(".auth-card", {
          y: entryDistance,
          scale: cardScale,
          autoAlpha: 0,
          duration: isCompact ? 0.45 : 0.8,
        });

        // 品牌标识区
        tl.from(
          ".auth-card__brand",
          { y: 12, autoAlpha: 0, duration: isCompact ? 0.3 : 0.5 },
          offset,
        );

        // 标题 + 副标题
        tl.from(
          ".auth-card__header",
          { y: 10, autoAlpha: 0, duration: isCompact ? 0.3 : 0.5 },
          isCompact ? "-=0.12" : "-=0.2",
        );

        // 表单项依次入场
        tl.from(
          ".auth-card .ant-form-item",
          {
            y: 8,
            autoAlpha: 0,
            duration: isCompact ? 0.24 : 0.4,
            stagger: itemStagger,
          },
          isCompact ? "-=0.08" : "-=0.15",
        );

        // 登录按钮
        tl.from(
          ".auth-card .ant-btn-primary",
          { y: 8, autoAlpha: 0, duration: isCompact ? 0.26 : 0.4 },
          "-=0.08",
        );

        // 分割线 + 底部区域
        tl.from(
          ".auth-card__divider, .auth-card__footer",
          { y: 8, autoAlpha: 0, duration: isCompact ? 0.24 : 0.4 },
          "-=0.08",
        );

        return () => {
          tl.kill();
        };
      },
    );
  });
}
