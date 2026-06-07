# 主题 GSAP 背景特效 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 blue-white、black-gold、pink 三个主题分别实现独立的 GSAP 背景特效，替代当前统一的粒子动画。

**Architecture:** 独立组件方案，每个主题一个特效组件，BackgroundAnimation 根据 themeName 条件渲染。共享 usePerformance hook 做性能自适应。主题切换时新旧组件同时挂载，交叉淡入淡出。

**Tech Stack:** React 18, GSAP 3.15, @gsap/react, TypeScript, CSS-in-JS (inline style)

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 新增 | `web/components/theme-effects/use-performance.ts` | 设备性能检测 hook |
| 新增 | `web/components/theme-effects/bubble-effect.tsx` | blue-white 气泡上升特效 |
| 新增 | `web/components/theme-effects/starfield-effect.tsx` | black-gold 星空闪烁+流星特效 |
| 新增 | `web/components/theme-effects/petal-effect.tsx` | pink 花瓣飘落特效 |
| 新增 | `web/components/theme-effects/index.ts` | 导出入口 |
| 重写 | `web/components/background-animation.tsx` | 从粒子动画改为特效分发器 |
| 不改 | `web/components/theme-provider.tsx` | CSS vars 和 token 逻辑不变 |
| 不改 | `web/app/dashboard/layout.tsx` | 已挂载 BackgroundAnimation，无需改动 |

---

### Task 1: usePerformance 性能检测 hook

**Files:**
- Create: `web/components/theme-effects/use-performance.ts`

- [ ] **Step 1: 创建 usePerformance hook**

```typescript
"use client";

import { useMemo } from "react";

export type PerformanceLevel = "low" | "medium" | "high";

export function usePerformance(): PerformanceLevel {
  return useMemo(() => {
    if (typeof window === "undefined") return "medium";

    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReduced) return "low";

    const cores = navigator.hardwareConcurrency || 4;
    const memory = (navigator as Navigator & { deviceMemory?: number })
      .deviceMemory || 4;

    if (cores <= 2 || memory <= 2) return "low";
    if (cores >= 8 && memory >= 8) return "high";
    return "medium";
  }, []);
}
```

- [ ] **Step 2: 创建 index.ts 导出入口**

```typescript
export { usePerformance } from "./use-performance";
export type { PerformanceLevel } from "./use-performance";
```

- [ ] **Step 3: 验证 TypeScript 编译通过**

Run: `cd web && pnpm typecheck`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add web/components/theme-effects/use-performance.ts web/components/theme-effects/index.ts
git commit -m "feat(theme): 新增性能检测 hook usePerformance"
```

---

### Task 2: BubbleEffect 气泡特效（blue-white）

**Files:**
- Create: `web/components/theme-effects/bubble-effect.tsx`
- Modify: `web/components/theme-effects/index.ts`

**Spec:** blue-white 主题，15-25 个蓝色气泡从底部匀速上升，high 性能时带 scale 脉冲。

- [ ] **Step 1: 创建 BubbleEffect 组件**

```typescript
"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useCallback, useRef } from "react";
import { usePerformance, type PerformanceLevel } from "./use-performance";

interface BubbleEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}

const COUNT_MAP: Record<PerformanceLevel, number> = {
  low: 10,
  medium: 18,
  high: 25,
};

const BUBBLE_COLORS = ["#1677ff", "#40a9ff", "#69c0ff"];

export default function BubbleEffect({
  visible,
  onFadeOutComplete,
}: BubbleEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const performance = usePerformance();
  const count = COUNT_MAP[performance];

  useGSAP(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const bubbles = container.querySelectorAll<HTMLDivElement>(".bubble");
      if (!bubbles.length) return;

      const vh = window.innerHeight;

      bubbles.forEach((bubble) => {
        const size = gsap.utils.random(20, 80);
        const x = gsap.utils.random(5, 95);
        const color =
          BUBBLE_COLORS[Math.floor(Math.random() * BUBBLE_COLORS.length)];
        const duration = gsap.utils.random(8, 15);
        const delay = gsap.utils.random(0, 10);

        gsap.set(bubble, {
          x: `${x}vw`,
          y: vh + 50,
          width: size,
          height: size,
          opacity: gsap.utils.random(0.1, 0.4),
          borderRadius: "50%",
          backgroundColor: color,
          boxShadow: `0 0 ${size * 0.4}px ${color}40`,
        });

        const tl = gsap.timeline({ repeat: -1, delay });

        tl.to(bubble, {
          y: -100,
          duration,
          ease: "none",
        });

        if (performance === "high") {
          tl.to(
            bubble,
            {
              scale: 1.2,
              duration: 0.15,
              ease: "sine.out",
            },
            `-=${0.3}`
          );
          tl.to(bubble, {
            scale: 1,
            duration: 0.15,
            ease: "sine.in",
          });
        }
      });

      // 淡入
      gsap.fromTo(
        container,
        { opacity: 0 },
        { opacity: 1, duration: 0.6, ease: "power2.out" }
      );
    },
    { scope: containerRef }
  );

  // 处理可见性变化
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

  // 当 visible 变为 false 时触发淡出
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
          className="bubble"
          style={{
            position: "absolute",
            willChange: "transform, opacity",
          }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 更新 index.ts 导出**

在 `web/components/theme-effects/index.ts` 中添加：

```typescript
export { default as BubbleEffect } from "./bubble-effect";
```

- [ ] **Step 3: TypeScript 编译检查**

Run: `cd web && pnpm typecheck`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add web/components/theme-effects/bubble-effect.tsx web/components/theme-effects/index.ts
git commit -m "feat(theme): 实现 BubbleEffect 气泡上升特效"
```

---

### Task 3: StarfieldEffect 星空特效（black-gold）

**Files:**
- Create: `web/components/theme-effects/starfield-effect.tsx`
- Modify: `web/components/theme-effects/index.ts`

**Spec:** black-gold 主题，40-80 个金色星点闪烁，medium/high 性能时每 5-8 秒出现流星。

- [ ] **Step 1: 创建 StarfieldEffect 组件**

```typescript
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

      // 星点闪烁
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

        // 用 gsap.context 管理流星生命周期，确保卸载时清理
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

      // 淡入
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
```

- [ ] **Step 2: 更新 index.ts 导出**

在 `web/components/theme-effects/index.ts` 中添加：

```typescript
export { default as StarfieldEffect } from "./starfield-effect";
```

- [ ] **Step 3: TypeScript 编译检查**

Run: `cd web && pnpm typecheck`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add web/components/theme-effects/starfield-effect.tsx web/components/theme-effects/index.ts
git commit -m "feat(theme): 实现 StarfieldEffect 星空闪烁流星特效"
```

---

### Task 4: PetalEffect 花瓣特效（pink）

**Files:**
- Create: `web/components/theme-effects/petal-effect.tsx`
- Modify: `web/components/theme-effects/index.ts`

**Spec:** pink 主题，12-20 个花瓣从顶部飘落，带正弦摆动和旋转，high 性能时带 scale 变化。

- [ ] **Step 1: 创建 PetalEffect 组件**

```typescript
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

        // 飘落 + 正弦摆动
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

        // 持续旋转
        gsap.to(petal, {
          rotation: "+=360",
          duration: gsap.utils.random(4, 8),
          repeat: -1,
          ease: "none",
          delay,
        });

        // high 性能：scale 变化
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

      // 淡入
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
```

- [ ] **Step 2: 更新 index.ts 导出**

在 `web/components/theme-effects/index.ts` 中添加：

```typescript
export { default as PetalEffect } from "./petal-effect";
```

- [ ] **Step 3: TypeScript 编译检查**

Run: `cd web && pnpm typecheck`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add web/components/theme-effects/petal-effect.tsx web/components/theme-effects/index.ts
git commit -m "feat(theme): 实现 PetalEffect 花瓣飘落特效"
```

---

### Task 5: 重写 BackgroundAnimation 为特效分发器

**Files:**
- Modify: `web/components/background-animation.tsx`

**Spec:** 删除现有粒子逻辑，根据 themeName 条件渲染对应特效组件，管理切换过渡。

- [ ] **Step 1: 重写 background-animation.tsx**

```typescript
"use client";

import { useCallback, useEffect, useState } from "react";
import { useTheme, type ThemeName } from "./theme-provider";
import { BubbleEffect, StarfieldEffect, PetalEffect } from "./theme-effects";

const EFFECT_MAP: Record<
  ThemeName,
  React.ComponentType<{
    visible: boolean;
    onFadeOutComplete?: () => void;
  }>
> = {
  "blue-white": BubbleEffect,
  "black-gold": StarfieldEffect,
  pink: PetalEffect,
};

export default function BackgroundAnimation() {
  const { themeName } = useTheme();
  const [currentTheme, setCurrentTheme] = useState<ThemeName>(themeName);
  const [prevTheme, setPrevTheme] = useState<ThemeName | null>(null);

  useEffect(() => {
    if (themeName !== currentTheme) {
      setPrevTheme(currentTheme);
      setCurrentTheme(themeName);
    }
  }, [themeName, currentTheme]);

  const handlePrevFadeOut = useCallback(() => {
    setPrevTheme(null);
  }, []);

  const CurrentEffect = EFFECT_MAP[currentTheme];
  const PrevEffect = prevTheme ? EFFECT_MAP[prevTheme] : null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 0,
      }}
      aria-hidden="true"
    >
      {PrevEffect && (
        <PrevEffect visible={false} onFadeOutComplete={handlePrevFadeOut} />
      )}
      <CurrentEffect visible={true} />
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 编译检查**

Run: `cd web && pnpm typecheck`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add web/components/background-animation.tsx
git commit -m "feat(theme): 重写 BackgroundAnimation 为特效分发器"
```

---

### Task 6: 视觉验证与手动测试

**Files:** 无新增/修改

- [ ] **Step 1: 启动开发服务器**

Run: `cd web && pnpm dev`

- [ ] **Step 2: 验证 blue-white 主题**

1. 访问 Dashboard 页面
2. 确认主题为 blue-white（默认）
3. 验证：蓝色气泡从底部缓慢上升
4. 验证：气泡大小不一，半透明，有光晕
5. 验证：气泡匀速上升，到达顶部后重置到底部循环

- [ ] **Step 3: 验证 black-gold 主题**

1. 点击侧边栏底部主题切换器的金色圆点
2. 验证：背景变为深色，金色星点随机闪烁
3. 验证：每 5-8 秒有一条流星从右上划到左下
4. 验证：主题切换时旧特效淡出、新特效淡入，无空白期

- [ ] **Step 4: 验证 pink 主题**

1. 点击主题切换器的粉色圆点
2. 验证：粉色花瓣从顶部飘落
3. 验证：花瓣有左右摆动 + 旋转
4. 验证：切换过渡平滑

- [ ] **Step 5: 验证性能降级**

1. 在 Chrome DevTools 中模拟低端设备（Performance > CPU 4x slowdown）
2. 刷新页面
3. 验证：粒子数量减少

- [ ] **Step 6: 验证 reduced-motion**

1. 在 Chrome DevTools > Emulation > Rendering 中勾选 "Emulate CSS prefers-reduced-motion: reduce"
2. 刷新页面
3. 验证：特效使用最少粒子数量

- [ ] **Step 7: 验证登录页不受影响**

1. 访问 `/login` 页面
2. 验证：登录页保持原有的光球漂移动画，不显示主题特效

- [ ] **Step 8: Commit 最终状态**

```bash
git add -A
git commit -m "feat(theme): 完成主题 GSAP 背景特效实现"
```
