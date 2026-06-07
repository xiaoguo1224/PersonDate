# 主题 GSAP 背景特效设计

## 概述

当前三个主题（blue-white、black-gold、pink）仅切换颜色和 Ant Design token，背景动画对所有主题都是相同的浮动粒子。本次改造为每个主题实现完全独立的 GSAP 背景特效。

## 目标

- blue-white：蓝色气泡从底部上升
- black-gold：星空闪烁 + 流星划过
- pink：花瓣从上方飘落
- 设备性能自适应（粒子数量、复杂度）
- 主题切换时平滑过渡（淡入淡出）
- Dashboard 内页生效，登录页保持现有独立动画

## 方案选择

**独立组件 + 条件渲染**。三种特效的视觉形态和 GSAP 动画逻辑差异大，强行统一会导致引擎过度复杂。每个主题一个独立组件，`BackgroundAnimation` 根据 `themeName` 条件渲染。

## 文件结构

```
web/components/theme-effects/
  bubble-effect.tsx          # blue-white: 气泡上升
  starfield-effect.tsx       # black-gold: 星空闪烁+流星
  petal-effect.tsx           # pink: 花瓣飘落
  use-performance.ts         # 设备性能检测 hook
  index.ts                   # 导出入口
```

改动文件：
- `web/components/background-animation.tsx`：重写为分发器，删除现有粒子逻辑

新增文件：
- `web/components/theme-effects/` 下 5 个文件

不动的文件：
- `web/components/theme-provider.tsx`：CSS vars 和 Ant Design token 逻辑不变
- `web/components/dashboard-shell.tsx`：ThemeSwitcher 逻辑不变
- `web/app/globals.css`：不新增全局样式，粒子样式写在组件内部
- `web/hooks/use-login-animation.ts`：登录页保持现有动画

## 性能检测

`usePerformance()` hook 返回 `{ level: 'low' | 'medium' | 'high' }`。

检测指标：
- `navigator.hardwareConcurrency`（CPU 核心数）
- `navigator.deviceMemory`（内存，仅 Chrome 支持）
- `matchMedia('(prefers-reduced-motion: reduce)')`（用户偏好）

等级划分：
- low：`prefers-reduced-motion` 为 reduce，或 CPU 核心 <= 2，或内存 <= 2GB。粒子数量减半，禁用复杂叠加效果
- medium：默认等级。标准粒子数量
- high：CPU 核心 >= 8 且内存 >= 8GB。全粒子数量 + 额外细节效果

低性能设备上所有特效只保留最基础的运动，不渲染叠加效果（如气泡脉冲、流星拖尾、花瓣缩放变化）。

## 特效设计

### BubbleEffect（blue-white）

粒子数量：high=25 / medium=18 / low=10

每个气泡：
- 随机大小：20-80px
- 半透明：opacity 0.1-0.4
- 颜色：从 themeConfigs['blue-white'].cssVars 中获取 --accent（主色）和 --accent-light（浅色），再通过 HSL 调整亮度生成 2-3 个色阶随机使用
- 形状：圆形（border-radius: 50%）
- 带轻微模糊光晕（box-shadow）

运动：
- 从底部随机 x 位置出发，匀速上升到顶部后重置到底部，循环
- GSAP 独立 tween，`y` 从 `viewportHeight` 到 `-100`
- duration：8-15s 随机
- delay：0-10s 随机错开
- easing：`none`（匀速）

叠加效果（仅 high 性能）：
- 气泡到达顶部时 scale 脉冲 1 -> 1.2 -> 1，duration 0.3s

### StarfieldEffect（black-gold）

星点数量：high=80 / medium=50 / low=30

每个星点：
- 大小：2-4px
- 颜色：从 themeConfigs['black-gold'].cssVars 中获取 --accent（主色）和 --accent-light（浅色），通过 HSL 调整亮度生成 2-3 个色阶随机使用
- 形状：圆形
- 随机分布在整个视口

闪烁动画：
- GSAP timeline 循环，`opacity` 在 0.2-1 之间变化
- duration：1-3s 随机
- easing：`sine.inOut`
- 每个星点独立 timeline，起始时间随机

流星（仅 medium/high 性能）：
- 每 5-8 秒出现一条
- 起点：右上角 (viewportWidth + 50, -50)
- 终点：左下方 (-200, viewportHeight * 0.6)
- duration：0.8-1.5s
- 实现：细长 div（2px 高，80-150px 宽），带线性渐变背景（从透明到 --accent 色）
- GSAP `fromTo`，opacity 0 -> 1 -> 0
- high 性能：流星拖尾更长（150-200px）

### PetalEffect（pink）

花瓣数量：high=20 / medium=15 / low=8

每个花瓣：
- 大小：15-30px
- 颜色：从 themeConfigs['pink'].cssVars 中获取 --accent（主色）和 --accent-light（浅色），通过 HSL 调整亮度生成 2-3 个色阶随机使用
- 半透明：opacity 0.3-0.7
- 形状：CSS 椭圆旋转（`border-radius: 50% 0 50% 0` + 倾斜）
- 随机初始 x 位置

飘落动画：
- GSAP timeline，每个花瓣独立
- `y`：从 -50 到 viewportHeight + 50
- `x`：通过 GSAP keyframes 模拟正弦摆动（3-5 个关键帧，左右偏移 30-80px）
- `rotation`：持续旋转 0 -> 360 度
- duration：10-18s 随机
- delay：0-12s 随机错开
- easing：`none`（匀速飘落）

叠加效果（仅 high 性能）：
- 飘落过程中 scale 在 0.8-1.2 之间缓慢变化
- 花瓣颜色在飘落中轻微变化（通过 GSAP `colorProps` 或 CSS filter hue-rotate）

## 主题切换过渡

`background-animation.tsx` 核心逻辑：新旧特效组件同时挂载，交叉淡入淡出，旧组件淡出完成后卸载。

1. 维护 `prevTheme` 和 `currentTheme` 两个状态
2. `themeName` 变化时：
   - `prevTheme` = 当前 `currentTheme`
   - `currentTheme` = 新 `themeName`
   - 两个组件同时渲染：旧组件 `visible=false`（淡出），新组件 `visible=true`（淡入）
   - 旧组件淡出完成后（0.6s），从 DOM 卸载
3. 通过 `onFadeOutComplete` 回调管理旧组件卸载

组件接口：

```typescript
interface ThemeEffectProps {
  visible: boolean;
  onFadeOutComplete?: () => void;
}
```

每个特效组件：
- `visible=true` 时 GSAP 执行 `opacity: 0 -> 1`，duration 0.6s
- `visible=false` 时 GSAP 执行 `opacity: 1 -> 0`，duration 0.6s，完成后调用 `onFadeOutComplete`

## Dashboard 集成

`dashboard/layout.tsx` 已挂载 `<BackgroundAnimation />`，无需改动。

`background-animation.tsx` 改造后：

```typescript
// 伪代码
const EFFECT_MAP = {
  'blue-white': BubbleEffect,
  'black-gold': StarfieldEffect,
  'pink': PetalEffect,
};

function BackgroundAnimation() {
  const { themeName } = useTheme();
  const [currentTheme, setCurrentTheme] = useState(themeName);
  const [prevTheme, setPrevTheme] = useState<string | null>(null);

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
    <div className="background-animation-container">
      {PrevEffect && <PrevEffect visible={false} onFadeOutComplete={handlePrevFadeOut} />}
      <CurrentEffect visible={true} />
    </div>
  );
}
```

## 约束

- 所有特效使用 `position: fixed`，`pointer-events: none`，不阻挡用户交互
- 使用 `will-change: transform, opacity` 提示浏览器优化
- 每个特效组件在 `useGSAP` 的 cleanup 中销毁所有 tween 和 DOM 元素
- 不使用 `innerHTML`，粒子元素通过 GSAP 直接操作 DOM 或 React ref
- CSS 变量颜色从 `theme-provider.tsx` 的 `cssVars` 中获取，不硬编码（确保未来新增主题时颜色可配）
