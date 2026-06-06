"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";

export function useLoginAnimation() {
  useGSAP(() => {
    const mm = gsap.matchMedia();

    mm.add(
      {
        reduceMotion: "(prefers-reduced-motion: reduce)",
      },
      (context) => {
        const { reduceMotion } = context.conditions ?? {};

        if (reduceMotion) {
          gsap.set(".auth-card", { autoAlpha: 1 });
          return;
        }

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

        // 卡片入场动画
        const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

        // 卡片整体：从下方淡入 + 轻微上浮
        tl.from(".auth-card", {
          y: 40,
          scale: 0.97,
          autoAlpha: 0,
          duration: 0.8,
        });

        // 品牌标识区
        tl.from(
          ".auth-card__brand",
          { y: 16, autoAlpha: 0, duration: 0.5 },
          "-=0.3",
        );

        // 标题 + 副标题
        tl.from(
          ".auth-card__header",
          { y: 14, autoAlpha: 0, duration: 0.5 },
          "-=0.2",
        );

        // 表单项依次入场
        tl.from(
          ".auth-card .ant-form-item",
          {
            y: 12,
            autoAlpha: 0,
            duration: 0.4,
            stagger: 0.08,
          },
          "-=0.15",
        );

        // 登录按钮
        tl.from(
          ".auth-card .ant-btn-primary",
          { y: 12, autoAlpha: 0, duration: 0.4 },
          "-=0.1",
        );

        // 分割线 + 底部区域
        tl.from(
          ".auth-card__divider, .auth-card__footer",
          { y: 10, autoAlpha: 0, duration: 0.4 },
          "-=0.1",
        );

        return () => {
          tl.kill();
        };
      },
    );
  });
}
