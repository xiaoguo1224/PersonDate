# Web Dashboard 全面响应式适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Web Dashboard 在手机、平板和不同尺寸桌面上都能稳定可用，同时保留现有桌面驾驶舱风格与 owner/member 权限隔离。

**Architecture:** 先拆分 dashboard 壳层的导航与响应式判断，把“桌面侧栏”和“手机顶部 Tab + 更多菜单”变成同一套导航数据的两种呈现；再按页面族群分别调整布局密度、滚动容器、弹窗宽度和触控热区。最后补一组基于 Playwright 的视口回归测试，覆盖手机、平板和桌面三类关键尺寸。

**Tech Stack:** Next.js App Router, React 19, TypeScript, Ant Design 5, GSAP, Playwright, pnpm。

## Global Constraints

- 手机端必须完整覆盖 `320px`、`375px`、`390px`、`414px` 常见宽度。
- `>= 1280px` 保持完整桌面驾驶舱布局；`< 768px` 切换为手机顶部 Tab 栏 + 更多菜单。
- 保持 Ant Design，不替换技术栈，不改后端 API。
- owner/member 菜单隔离不变，后端权限校验不变。
- 小屏和 `prefers-reduced-motion` 下要减轻背景动画和重动效。
- 不引入原生 App、小程序或新的路由体系。

---

### Task 1: 拆分响应式导航壳层

**Files:**
- Modify: `web/components/dashboard-shell.tsx`
- Modify: `web/app/globals.css`
- Create: `web/components/dashboard-navigation.tsx`
- Create: `web/components/dashboard-mobile-nav.tsx`
- Create: `web/hooks/use-responsive-breakpoint.ts`

**Interfaces:**
- `useResponsiveBreakpoint(): { isMobile: boolean; isTablet: boolean; isDesktop: boolean }`
- `buildDashboardNavigation(role: UserRole): NavigationSection[]`
- `DashboardDesktopNavigation({ items, pathname, onNavigate })`
- `DashboardMobileNavigation({ items, pathname, onNavigate, onMore, onLogout })`

**Step 1: 抽离导航数据和角色过滤**

把 `web/components/dashboard-shell.tsx` 里的导航配置拆到 `web/components/dashboard-navigation.tsx`，保留当前 owner/member 权限过滤规则不变，并把“日志”“设置”这类分组显式建模成 `NavigationSection`。

**Step 2: 新增屏幕尺寸判断 hook**

在 `web/hooks/use-responsive-breakpoint.ts` 中封装 `window.matchMedia`，固定使用 `768px`、`992px`、`1280px` 三档判断，返回 `isMobile`、`isTablet`、`isDesktop`，供 shell、页面和测试共用。

**Step 3: 把桌面侧栏与手机顶部导航拆成两个组件**

在 `web/components/dashboard-mobile-nav.tsx` 中实现手机顶部 Tab 栏与“更多”入口，Tab 只保留高频入口，更多菜单承载次级页面。桌面端继续保留侧边栏，但改为从共享导航数据生成菜单。

**Step 4: 让 shell 按断点切换渲染结构**

修改 `web/components/dashboard-shell.tsx`，当 `isMobile` 为真时隐藏 `Sider`，显示顶部 Tab 栏与简化后的顶栏动作；当 `isDesktop` 为真时保留现有完整侧栏和头像下拉。`pathname` 仍然作为选中态来源，不改路由逻辑。

**Step 5: 补全壳层级 CSS**

在 `web/app/globals.css` 中增加移动端壳层规则：收紧 `dashboard-content` 内边距、减小顶栏高度、限制桌面侧栏最小宽度、为手机导航和更多菜单设置安全点击区域。

**Step 6: 跑一次桌面构建校验**

Run: `cd web && pnpm build`

Expected: Next.js 构建通过，`dashboard-shell`、新增导航组件和全局样式没有类型或语法错误。

**Step 7: 提交**

```bash
git add web/components/dashboard-shell.tsx web/components/dashboard-navigation.tsx web/components/dashboard-mobile-nav.tsx web/hooks/use-responsive-breakpoint.ts web/app/globals.css
git commit -m "feat(web): 拆分响应式导航壳层"
```

---

### Task 2: 适配登录、注册、首页和动效降噪

**Files:**
- Modify: `web/components/auth-layout.tsx`
- Modify: `web/hooks/use-login-animation.ts`
- Modify: `web/hooks/use-landing-animation.ts`
- Modify: `web/components/background-animation.tsx`
- Modify: `web/app/page.tsx`
- Modify: `web/app/globals.css`

**Interfaces:**
- `AuthLayout` 在 `xs` 断点下变成单列布局，CTA 与底部说明收窄
- `BackgroundAnimation` 在 `isMobile` 或 `prefers-reduced-motion` 时不渲染重型背景效果
- `useLoginAnimation`、`useLandingAnimation` 保留桌面动画，但在小屏下降低或跳过非必要动效

**Step 1: 让 auth 卡片在小屏下可完整阅读**

修改 `web/components/auth-layout.tsx` 和 `web/app/globals.css`，把登录/注册卡片改成小屏单列、全宽按钮、减少外边距和卡片圆角，避免 320px 宽度下输入框和说明文字被压缩。

**Step 2: 让登录与注册页继承新的 auth 容器规则**

确认 `web/components/auth-layout.tsx` 的响应式改动已经覆盖登录与注册页的表单区，让 `Input`、`Input.Password`、`Button` 在手机端撑满容器，并把次要提示文字收纳为更紧凑的块级说明。

**Step 3: 首页 hero 在手机端自动堆叠**

修改 `web/app/page.tsx`，让首屏 hero 从桌面的左右双栏降级为手机端上下堆叠，演示面板和 CTA 区在窄屏下保持垂直节奏，不再要求横向并排展示。

**Step 4: 将登录与首页动效做降噪处理**

在 `web/hooks/use-login-animation.ts`、`web/hooks/use-landing-animation.ts` 和 `web/components/background-animation.tsx` 中加入手机端与 `prefers-reduced-motion` 保护：小屏优先保留静态视觉层，跳过持续漂移、粒子和循环动画。

**Step 5: 补一轮入口页构建检查**

Run: `cd web && pnpm build`

Expected: 登录、注册和首页在桌面与手机宽度下都能通过构建，且 reduced motion 分支没有遗漏。

**Step 6: 提交**

```bash
git add web/components/auth-layout.tsx web/hooks/use-login-animation.ts web/hooks/use-landing-animation.ts web/components/background-animation.tsx web/app/page.tsx web/app/globals.css
git commit -m "feat(web): 适配入口页与动效降噪"
```

---

### Task 3: 让今日安排、日历和时间可视化在窄屏可用

**Files:**
- Modify: `web/app/dashboard/today/page.tsx`
- Modify: `web/app/dashboard/calendar/page.tsx`
- Modify: `web/components/gantt-chart.tsx`
- Modify: `web/components/conflict-resolution-modal.tsx`
- Modify: `web/app/globals.css`

**Interfaces:**
- `GanttChart` 继续接受 `items/baseDate/timezone/maxHeight/onEventClick`，新增可选 `compact?: boolean` 以便手机端切换更紧凑的渲染节奏
- `ConflictResolutionModal` 在手机端使用接近全屏的宽度，并把操作按钮堆叠显示

**Step 1: 把今日页主内容改成更强的响应式网格**

修改 `web/app/dashboard/today/page.tsx`，让今日概览从固定四卡横排降为自适应网格，平板自动 2 列、手机自动 1 列；把行动按钮和时间轴操作区改成可换行的布局，避免窄屏下按钮挤在一行。

**Step 2: 让今日页右侧侧栏在手机上顺序下移**

继续调整 `web/app/dashboard/today/page.tsx`，让“智能助手”“冲突事项”“提醒任务”在手机端自然流入内容主列下面，而不是维持双栏结构。卡片内部的标题、标签和操作按钮要保证可点击，不依赖 hover。

**Step 3: 日历页保持视图能力但允许布局降级**

修改 `web/app/dashboard/calendar/page.tsx`，让月视图保持 7 列网格，周视图和日视图继续横向滚动；在手机上优先展示可读性更高的视图，并减少顶部筛选和切换控件的横向占位。

**Step 4: 让甘特图在窄屏下继续可读**

修改 `web/components/gantt-chart.tsx`，引入 `compact` 模式后保留时间轴信息，但压缩标签宽度与行高；当容器宽度不足时仍以横向滚动方式展示，不强行挤进一屏。

**Step 5: 让冲突确认弹窗适配手机**

修改 `web/components/conflict-resolution-modal.tsx`，在小屏使用更宽的弹窗并将操作按钮纵向堆叠，避免多个 `Button` 并排时挤压文本和时间范围信息。

**Step 6: 补今日/日历页面构建检查**

Run: `cd web && pnpm build`

Expected: 今日页、日历页、甘特图和冲突弹窗在桌面与手机断点下都能编译通过。

**Step 7: 提交**

```bash
git add web/app/dashboard/today/page.tsx web/app/dashboard/calendar/page.tsx web/components/gantt-chart.tsx web/components/conflict-resolution-modal.tsx web/app/globals.css
git commit -m "feat(web): 适配今日页和日历页"
```

---

### Task 4: 让列表型业务页在手机上可扫读可操作

**Files:**
- Modify: `web/app/dashboard/tasks/page.tsx`
- Modify: `web/app/dashboard/conflicts/page.tsx`
- Modify: `web/app/dashboard/reminders/page.tsx`
- Modify: `web/app/dashboard/agent-logs/page.tsx`
- Modify: `web/app/dashboard/message-logs/page.tsx`
- Modify: `web/app/dashboard/wechat-outbound/page.tsx`
- Modify: `web/app/dashboard/wechat-status/page.tsx`
- Modify: `web/app/globals.css`

**Interfaces:**
- 各页继续使用现有 API 和数据类型，不改后端请求协议
- 统一引入更紧凑的移动端列表节奏：筛选折叠、操作收纳、摘要优先、详情可展开

**Step 1: 把任务页从“桌面列表”改成“移动卡片列表”**

修改 `web/app/dashboard/tasks/page.tsx`，让筛选区在手机端折叠成单列，任务项改为更紧凑的卡片布局，完成、编辑、删除等操作收进尾部按钮组或“更多”菜单，避免一条任务占满过多宽度。

**Step 2: 让冲突页和提醒页在手机上先看摘要**

修改 `web/app/dashboard/conflicts/page.tsx` 和 `web/app/dashboard/reminders/page.tsx`，在手机端优先展示时间、状态、严重程度、失败原因等摘要信息，长说明折叠，次级操作放到卡片底部，减少首屏高度。

**Step 3: 让 Agent 日志、消息日志和出站队列可纵向扫读**

修改 `web/app/dashboard/agent-logs/page.tsx`、`web/app/dashboard/message-logs/page.tsx` 和 `web/app/dashboard/wechat-outbound/page.tsx`，把行内密集字段改成分块布局，长 JSON、长文本和工具调用细节默认折叠，避免手机端出现横向滚动条。

**Step 4: 微信通道状态页改成仪表盘卡片**

修改 `web/app/dashboard/wechat-status/page.tsx`，把连接状态、账号统计、消息统计和最近消息流改为卡片网格和纵向时间线，手机端不再强制并排显示多个统计块。

**Step 5: 统一列表页的移动端间距和按钮热区**

在 `web/app/globals.css` 中补充移动端列表样式，确保标签、按钮和复制类操作在 375px 宽度下仍有足够触控面积。

**Step 6: 跑一次构建校验**

Run: `cd web && pnpm build`

Expected: 以上列表页在编译期通过，且桌面桌面布局没有被移动端样式误伤。

**Step 7: 提交**

```bash
git add web/app/dashboard/tasks/page.tsx web/app/dashboard/conflicts/page.tsx web/app/dashboard/reminders/page.tsx web/app/dashboard/agent-logs/page.tsx web/app/dashboard/message-logs/page.tsx web/app/dashboard/wechat-outbound/page.tsx web/app/dashboard/wechat-status/page.tsx web/app/globals.css
git commit -m "feat(web): 适配列表型业务页"
```

---

### Task 5: 让表单和管理页在手机上保持单列与全宽操作

**Files:**
- Modify: `web/app/dashboard/wechat-binding/page.tsx`
- Modify: `web/app/dashboard/account/page.tsx`
- Modify: `web/app/dashboard/settings/page.tsx`
- Modify: `web/app/dashboard/model-config/page.tsx`
- Modify: `web/app/dashboard/notification-settings/page.tsx`
- Modify: `web/app/dashboard/invite-codes/page.tsx`
- Modify: `web/app/dashboard/users/page.tsx`
- Modify: `web/app/globals.css`

**Interfaces:**
- 保持现有页面路由与 API 不变
- 统一让表单在手机端降为单列，`Button`、`Input`、`Select`、`DatePicker` 全宽显示
- 如果需要页头概览，优先复用 `SectionPage` 的结构而不是再写一套新壳

**Step 1: 把微信绑定页收成单列操作流**

修改 `web/app/dashboard/wechat-binding/page.tsx`，让登录会话、二维码展示、状态刷新和解绑操作在手机端按纵向顺序排列，二维码和状态卡不再并排挤压。

**Step 2: 把账号和设置页改成单列表单**

修改 `web/app/dashboard/account/page.tsx`、`web/app/dashboard/settings/page.tsx`、`web/app/dashboard/model-config/page.tsx`、`web/app/dashboard/notification-settings/page.tsx`，在手机端把原本可能并排的表单项全部改为单列，敏感项和高风险操作保留明显区分。

**Step 3: 管理页在窄屏下更强调选择与确认**

修改 `web/app/dashboard/invite-codes/page.tsx` 和 `web/app/dashboard/users/page.tsx`，让邀请码、使用次数、状态标签和启用/禁用操作在窄屏下分行显示，避免列表列数过多导致信息失焦。

**Step 4: 用全局样式统一表单和管理页的默认节奏**

在 `web/app/globals.css` 里补全表单与管理页的默认响应式规则，让未来新增的管理页面也自然继承单列布局、全宽按钮和紧凑卡片间距。

**Step 5: 运行构建检查**

Run: `cd web && pnpm build`

Expected: 表单页和管理页在手机与桌面宽度下都能编译通过，且输入控件不会溢出。

**Step 6: 提交**

```bash
git add web/app/dashboard/wechat-binding/page.tsx web/app/dashboard/account/page.tsx web/app/dashboard/settings/page.tsx web/app/dashboard/model-config/page.tsx web/app/dashboard/notification-settings/page.tsx web/app/dashboard/invite-codes/page.tsx web/app/dashboard/users/page.tsx web/app/globals.css
git commit -m "feat(web): 适配表单和管理页"
```

---

### Task 6: 加入视口回归测试和响应式验收脚本

**Files:**
- Modify: `web/package.json`
- Create: `web/playwright.config.ts`
- Create: `web/tests/responsive/dashboard-shell.spec.ts`
- Create: `web/tests/responsive/landing-auth.spec.ts`
- Create: `web/tests/responsive/dashboard-pages.spec.ts`
- Create: `web/tests/responsive/test-utils.ts`

**Interfaces:**
- `seedAuthSession(page, session)`：向 `localStorage` 写入真实的 `schedule-agent.auth` 结构
- `assertNoHorizontalOverflow(page)`：断言 `document.documentElement.scrollWidth <= window.innerWidth + 1`
- `assertMobileNavVisible(page)`：断言手机顶部 Tab 栏显示，桌面侧栏隐藏

**Step 1: 安装并配置 Playwright**

在 `web/package.json` 中加入 `@playwright/test` 和 `test:responsive` 脚本，新增 `web/playwright.config.ts`，默认跑 Chromium，并固定三个视口组：手机 `390x844`、平板 `1024x768`、桌面 `1440x900`。安装浏览器时执行 `cd web && pnpm exec playwright install chromium`。

**Step 2: 写 dashboard 壳层的响应式断言**

创建 `web/tests/responsive/dashboard-shell.spec.ts`，先用 `seedAuthSession()` 和 `/api/auth/me` 拦截把用户带进 dashboard，再断言手机端 `.dashboard-mobile-nav` 可见、`.dashboard-sidebar` 不可见，桌面端则相反。

**Step 3: 写入口页的移动端断言**

创建 `web/tests/responsive/landing-auth.spec.ts`，覆盖 `/`、`/login`、`/register` 三个页面，检查 375px 宽度下 hero、表单和 CTA 不溢出，且 `prefers-reduced-motion` 打开时页面仍可正常展示。

**Step 4: 写核心业务页的无横向溢出断言**

创建 `web/tests/responsive/dashboard-pages.spec.ts`，覆盖 `/dashboard/today`、`/dashboard/calendar`、`/dashboard/tasks`、`/dashboard/conflicts`、`/dashboard/reminders`、`/dashboard/agent-logs`、`/dashboard/wechat-binding`、`/dashboard/settings` 等页面，逐页调用 `assertNoHorizontalOverflow(page)`。

**Step 5: 跑 Playwright 视口测试**

Run: `cd web && pnpm exec playwright test tests/responsive`

Expected: 三组视口都通过，页面没有意外横向滚动，手机端导航和主要页面结构符合预期。

**Step 6: 最终构建与人工复核**

Run: `cd web && pnpm build`

然后人工检查手机、平板、笔记本和大屏四类尺寸，重点确认今日页、日历页、任务页和管理页的操作区没有被截断。

**Step 7: 提交**

```bash
git add web/package.json web/playwright.config.ts web/tests/responsive/dashboard-shell.spec.ts web/tests/responsive/landing-auth.spec.ts web/tests/responsive/dashboard-pages.spec.ts web/tests/responsive/test-utils.ts
git commit -m "test(web): 增加响应式回归测试"
```

---

## Coverage Check

- 壳层导航与断点切换：Task 1
- 入口页、登录页、注册页和动效降噪：Task 2
- 今日安排、日历、甘特图与冲突弹窗：Task 3
- 任务、冲突、提醒、日志与通道状态列表页：Task 4
- 微信绑定、账号、系统设置和管理页：Task 5
- 视口回归测试与验收脚本：Task 6

## Notes for Execution

- 每个 Task 都应在独立提交后再进入下一 Task，避免一轮改动覆盖太多页面。
- 优先先改共享壳层和共享组件，再改页面，这样后续页面能直接复用新的响应式规则。
- 如果某个页面为了手机端需要新增公共类名，优先放到 `web/app/globals.css`，避免把样式散落到多个页面文件里。
- 如果测试脚本需要登录态，优先用 `localStorage` 的 `schedule-agent.auth` 结构和 `/api/auth/me` 拦截，不要给测试引入额外后端依赖。
