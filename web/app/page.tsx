"use client";

import {
  BellOutlined,
  CheckCircleOutlined,
  CloudSyncOutlined,
  CustomerServiceOutlined,
  DashboardOutlined,
  MessageOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Space, Typography } from "antd";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useLandingAnimation } from "@/hooks/use-landing-animation";

const { Title, Paragraph, Text } = Typography;

const FEATURES = [
  {
    icon: <ThunderboltOutlined />,
    title: "自然语言创建",
    desc: "像聊天一样发送「明天下午 3 点开会」，Agent 自动识别并创建日程。",
  },
  {
    icon: <NodeIndexOutlined />,
    title: "智能冲突检测",
    desc: "自动检测时间冲突，给出调整建议，避免安排撞车。",
  },
  {
    icon: <CloudSyncOutlined />,
    title: "微信深度集成",
    desc: "绑定微信后直接在聊天窗口下达指令，无需打开任何应用。",
  },
  {
    icon: <ScheduleOutlined />,
    title: "每日自动规划",
    desc: "结合日程与待办，智能生成每日时间线计划草案。",
  },
  {
    icon: <CheckCircleOutlined />,
    title: "任务全生命周期",
    desc: "创建、追踪、标记完成，任务状态与日程联动。",
  },
  {
    icon: <BellOutlined />,
    title: "准时提醒",
    desc: "到点自动推送提醒，不出任何重要安排。",
  },
];

const STEPS = [
  {
    icon: <CustomerServiceOutlined />,
    title: "注册并绑定微信",
    desc: "在 Web 端使用邀请码注册，绑定微信账号。",
  },
  {
    icon: <ThunderboltOutlined />,
    title: "自然语言对话",
    desc: "在微信中像聊天一样发送日程指令，无需特定格式。",
  },
  {
    icon: <DashboardOutlined />,
    title: "Agent 自动执行",
    desc: "系统自动识别意图、创建日程、检测冲突、生成计划。",
  },
];

const DEMO_EVENTS = [
  { time: "09:00", title: "项目晨会", tag: "日程", color: "#2563eb" },
  { time: "10:30", title: "客户需求沟通", tag: "日程", color: "#2563eb" },
  { time: "14:00", title: "产品评审", tag: "日程", color: "#d97706" },
  { time: "15:30", title: "写季度报告", tag: "待办", color: "#059669" },
  { time: "19:00", title: "健身", tag: "提醒", color: "#dc2626" },
];

/** Agent 写入日历演示 */
function ScheduleDemo() {
  const [visibleCount, setVisibleCount] = useState(0);
  const [phase, setPhase] = useState<"idle" | "typing" | "writing">("idle");

  useEffect(() => {
    const start = () => {
      setVisibleCount(0);
      setPhase("idle");

      DEMO_EVENTS.forEach((_, i) => {
        setTimeout(() => {
          setPhase("typing");
          setTimeout(() => {
            setPhase("writing");
            setVisibleCount(i + 1);
          }, 600);
        }, i * 1800);
      });

      setTimeout(() => {
        setPhase("idle");
        start();
      }, DEMO_EVENTS.length * 1800 + 3000);
    };

    const tid = setTimeout(start, 1200);
    return () => clearTimeout(tid);
  }, []);

  return (
    <div className="demo-panel">
      <div className="demo-panel__header">
        <div className="demo-panel__header-left">
          <SafetyCertificateOutlined className="demo-panel__header-icon" />
          <span className="demo-panel__header-title">Schedule Agent</span>
        </div>
        <span className="demo-panel__status">
          <span className="demo-panel__status-dot" />
          工作中
        </span>
      </div>

      <div className="demo-panel__chat">
        <div className="demo-chat demo-chat--user">
          <div className="demo-chat__icon">
            <MessageOutlined />
          </div>
          <div className="demo-chat__bubble demo-chat__bubble--user">
            明天下午 3 点开会
          </div>
        </div>
        {visibleCount >= 1 && (
          <div className="demo-chat demo-chat--agent">
            <div className="demo-chat__icon demo-chat__icon--agent">
              <SafetyCertificateOutlined />
            </div>
            <div className="demo-chat__bubble demo-chat__bubble--agent">
              已创建日程：项目晨会（09:00-10:00）
            </div>
          </div>
        )}
        {visibleCount >= 2 && (
          <div className="demo-chat demo-chat--user">
            <div className="demo-chat__icon">
              <MessageOutlined />
            </div>
            <div className="demo-chat__bubble demo-chat__bubble--user">
              约客户上午聊需求
            </div>
          </div>
        )}
        {visibleCount >= 2 && (
          <div className="demo-chat demo-chat--agent">
            <div className="demo-chat__icon demo-chat__icon--agent">
              <SafetyCertificateOutlined />
            </div>
            <div className="demo-chat__bubble demo-chat__bubble--agent">
              已创建日程：客户需求沟通（10:30-11:30）
            </div>
          </div>
        )}

        {phase === "writing" && visibleCount < DEMO_EVENTS.length && (
          <div className="demo-chat demo-chat--agent">
            <div className="demo-chat__icon demo-chat__icon--agent">
              <SafetyCertificateOutlined />
            </div>
            <div className="demo-chat__bubble demo-chat__bubble--agent demo-chat__bubble--writing">
              <span className="demo-typing">
                <span className="demo-typing__dot" />
                <span className="demo-typing__dot" />
                <span className="demo-typing__dot" />
              </span>
              Agent 正在写入日历...
            </div>
          </div>
        )}
      </div>

      <div className="demo-panel__timeline">
        <div className="demo-timeline__label">今日安排</div>
        {DEMO_EVENTS.slice(0, visibleCount).map((ev, i) => (
          <div key={i} className="demo-event" style={{ "--event-color": ev.color } as React.CSSProperties}>
            <div className="demo-event__dot" />
            <div className="demo-event__time">{ev.time}</div>
            <div className="demo-event__body">
              <span className="demo-event__title">{ev.title}</span>
              <span className="demo-event__tag" style={{ background: `${ev.color}18`, color: ev.color }}>
                {ev.tag}
              </span>
            </div>
          </div>
        ))}
        {visibleCount > 0 && visibleCount < DEMO_EVENTS.length && (
          <div className="demo-event demo-event--pending">
            <div className="demo-event__dot demo-event__dot--pulse" />
            <div className="demo-event__time">--:--</div>
            <div className="demo-event__body">
              <span className="demo-event__title demo-event__title--ghost">等待下一条指令...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** 机器人写日历 - 大背景 SVG */
function RobotWritingCalendar() {
  return (
    <div className="robot-bg" aria-hidden="true">
      <svg
        viewBox="0 0 600 500"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="robot-bg__svg"
      >
        {/* 机器人身体 */}
        <g className="robot-bg__body">
          <rect x="220" y="40" width="120" height="100" rx="24" fill="url(#robotGrad)" opacity="0.18" />
          <rect x="220" y="40" width="120" height="100" rx="24" stroke="url(#robotStroke)" strokeWidth="0.6" opacity="0.15" />
          <circle cx="260" cy="82" r="6" fill="#2563eb" opacity="0.2" />
          <circle cx="300" cy="82" r="6" fill="#2563eb" opacity="0.2" />
          <line x1="280" y1="40" x2="280" y2="20" stroke="#2563eb" strokeWidth="0.5" opacity="0.15" />
          <circle cx="280" cy="18" r="4" fill="#2563eb" opacity="0.15" />

          <rect x="238" y="155" width="84" height="110" rx="16" fill="url(#robotGrad)" opacity="0.15" />
          <rect x="238" y="155" width="84" height="110" rx="16" stroke="url(#robotStroke)" strokeWidth="0.6" opacity="0.12" />
          <rect x="254" y="175" width="52" height="28" rx="6" fill="#2563eb" opacity="0.08" />
          <text x="267" y="193" fontSize="8" fill="#2563eb" opacity="0.2" fontFamily="monospace">AI</text>

          {/* 左臂 */}
          <path
            d="M238 180 C200 160, 160 140, 130 120"
            stroke="#2563eb"
            strokeWidth="0.5"
            opacity="0.1"
            fill="none"
            strokeDasharray="3 3"
          />

          {/* 底座 */}
          <rect x="254" y="270" width="52" height="12" rx="6" fill="#2563eb" opacity="0.1" />
        </g>

        {/* 右臂（GSAP 动效目标） */}
        <g className="robot-arm">
          {/* 手臂路径 - GSAP 用 stroke-dashoffset 做"画出"效果 */}
          <path
            className="robot-arm__draw"
            d="M322 180 C360 200, 400 230, 430 270"
            stroke="#2563eb"
            strokeWidth="0.5"
            opacity="0.12"
            fill="none"
            strokeDasharray="140"
            strokeDashoffset="140"
          />
          {/* 笔 + 笔尖 */}
          <g className="robot-arm__pen">
            <line x1="430" y1="270" x2="445" y2="290" stroke="#2563eb" strokeWidth="0.6" opacity="0.15" />
            <circle cx="448" cy="294" r="2.5" fill="#2563eb" opacity="0.08" className="robot-arm__tip" />
          </g>
        </g>

        {/* 日历 */}
        <g className="robot-bg__calendar" opacity="0.13">
          <rect x="410" y="230" width="140" height="170" rx="10" fill="white" stroke="#2563eb" strokeWidth="0.4" />
          <rect x="410" y="230" width="140" height="30" rx="10" fill="#2563eb" opacity="0.08" />
          <rect x="410" y="246" width="140" height="14" fill="#2563eb" opacity="0.08" />
          <text x="455" y="249" fontSize="10" fill="#2563eb" opacity="0.25" textAnchor="middle" fontFamily="sans-serif" fontWeight="600">6 月</text>

          {/* 日程条目 — 逐条出现 */}
          <g className="robot-row robot-row--1" opacity="0">
            <line x1="424" y1="278" x2="518" y2="278" stroke="#2563eb" strokeWidth="0.3" />
            <circle cx="430" cy="286" r="2" fill="#2563eb" />
            <text x="438" y="289" fontSize="7" fill="#2563eb">09:00 项目晨会</text>
          </g>

          <g className="robot-row robot-row--2" opacity="0">
            <line x1="424" y1="304" x2="518" y2="304" stroke="#2563eb" strokeWidth="0.3" />
            <circle cx="430" cy="312" r="2" fill="#2563eb" />
            <text x="438" y="315" fontSize="7" fill="#2563eb">10:30 客户沟通</text>
          </g>

          <g className="robot-row robot-row--3" opacity="0">
            <line x1="424" y1="330" x2="518" y2="330" stroke="#2563eb" strokeWidth="0.3" />
            <circle cx="430" cy="338" r="2" fill="#2563eb" />
            <text x="438" y="341" fontSize="7" fill="#2563eb">14:00 产品评审</text>
          </g>

          {/* 写入光标 */}
          <line x1="424" y1="352" x2="424" y2="368" stroke="#2563eb" strokeWidth="0.5" opacity="0.15" className="robot-bg__cursor" />
        </g>

        {/* 数据流向 */}
        <g opacity="0.08">
          <path
            d="M280 270 C300 310, 360 340, 420 350"
            stroke="#2563eb"
            strokeWidth="0.3"
            fill="none"
            strokeDasharray="2 4"
            className="robot-bg__flow"
          />
          <path
            d="M280 260 C320 330, 380 380, 440 380"
            stroke="#2563eb"
            strokeWidth="0.2"
            fill="none"
            strokeDasharray="2 4"
            className="robot-bg__flow"
          />
        </g>

        <circle cx="340" cy="300" r="1.5" fill="#2563eb" opacity="0.12" className="robot-bg__particle" />
        <circle cx="360" cy="340" r="1" fill="#2563eb" opacity="0.1" className="robot-bg__particle" />
        <circle cx="380" cy="290" r="1.5" fill="#2563eb" opacity="0.08" className="robot-bg__particle" />
        <circle cx="400" cy="370" r="1" fill="#2563eb" opacity="0.1" className="robot-bg__particle" />

        <defs>
          <linearGradient id="robotGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#2563eb" />
            <stop offset="100%" stopColor="#60a5fa" />
          </linearGradient>
          <linearGradient id="robotStroke" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#2563eb" />
            <stop offset="100%" stopColor="#93c5fd" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

export default function LandingPage() {
  useLandingAnimation();

  return (
    <main className="landing-root">
      {/* 机器人写日历大背景 */}
      <RobotWritingCalendar />

      {/* 粒子背景 */}
      <ParticleBackground />

      {/* 背景装饰光晕 */}
      <div className="landing-bg-orb landing-bg-orb--blue" />
      <div className="landing-bg-orb landing-bg-orb--pink" />
      <div className="landing-bg-grid" />

      {/* 顶部导航 */}
      <nav className="landing-nav">
        <div className="landing-nav__inner">
          <Space className="landing-nav__brand">
            <SafetyCertificateOutlined className="landing-nav__icon" />
            <span className="landing-nav__name">Schedule Agent</span>
          </Space>
          <Space size={10}>
            <Link href="/login">
              <Button type="text" className="landing-nav__login">
                登录
              </Button>
            </Link>
            <Link href="/register">
              <Button type="primary" className="landing-nav__register">
                注册
              </Button>
            </Link>
          </Space>
        </div>
      </nav>

      <div className="landing-content">
        {/* ===== Hero ===== */}
        <section className="landing-hero">
          <div className="landing-hero__inner">
            <div className="landing-hero__text">
              <div className="landing-hero__badge">
                <SafetyCertificateOutlined />
                <span>微信智能安排规划 Agent</span>
              </div>

              <Title className="landing-hero__title">
                把自然语言
                <br />
                变成可执行的安排
              </Title>

              <Paragraph className="landing-hero__subtitle">
                通过微信聊天直接创建日程、管理任务、检测冲突、生成每日计划。
                <br />
                让 Agent 接管琐碎安排，把注意力留给真正重要的工作和生活。
              </Paragraph>

              <Space size={14} className="landing-hero__actions">
                <Link href="/login">
                  <Button type="primary" size="large" icon={<DashboardOutlined />}>
                    进入驾驶舱
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="large" className="landing-btn-ghost">
                    注册体验
                  </Button>
                </Link>
              </Space>

              <div className="landing-hero__stats">
                {[
                  { label: "意图识别", value: "NLU" },
                  { label: "冲突检测", value: "精确" },
                  { label: "响应方式", value: "微信推送" },
                ].map((s) => (
                  <div key={s.label} className="landing-hero__stat">
                    <Text className="landing-hero__stat-label">
                      {s.label}
                    </Text>
                    <Text className="landing-hero__stat-value">{s.value}</Text>
                  </div>
                ))}
              </div>
            </div>

            <div className="landing-hero__demo">
              <ScheduleDemo />
            </div>
          </div>
        </section>

        {/* ===== 核心能力 ===== */}
        <section className="landing-section" id="features">
          <div className="landing-section__header">
            <Title level={2} className="landing-section__title">
              核心能力
            </Title>
            <Paragraph className="landing-section__subtitle">
              六大能力覆盖日程管理全场景
            </Paragraph>
          </div>

          <div className="landing-features">
            {FEATURES.map((f, i) => (
              <div key={i} className="landing-feature-card">
                <div className="landing-feature-card__glow" />
                <div className="landing-feature-card__icon">{f.icon}</div>
                <div className="landing-feature-card__body">
                  <Title level={4} className="landing-feature-card__title">
                    {f.title}
                  </Title>
                  <Paragraph className="landing-feature-card__desc">
                    {f.desc}
                  </Paragraph>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ===== 三步上手 ===== */}
        <section className="landing-section" id="steps">
          <div className="landing-section__header">
            <Title level={2} className="landing-section__title">
              三步上手
            </Title>
            <Paragraph className="landing-section__subtitle">
              从注册到使用，只需简单三步
            </Paragraph>
          </div>

          <div className="landing-steps">
            {STEPS.map((s, i) => (
              <div key={i} className="landing-step">
                <div className="landing-step__number">{i + 1}</div>
                <div className="landing-step__icon">{s.icon}</div>
                <div className="landing-step__body">
                  <Title level={4} className="landing-step__title">
                    {s.title}
                  </Title>
                  <Paragraph className="landing-step__desc">{s.desc}</Paragraph>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ===== CTA ===== */}
        <section className="landing-cta">
          <div className="landing-cta__card">
            <Title level={3} className="landing-cta__title">
              准备好让 Agent 接管你的琐碎安排了？
            </Title>
            <Paragraph className="landing-cta__desc">
              无需学习，打开微信即可开始。
            </Paragraph>
            <Link href="/login">
              <Button type="primary" size="large" icon={<ThunderboltOutlined />}>
                立即开始
              </Button>
            </Link>
          </div>
        </section>
      </div>

      {/* 页脚 */}
      <footer className="landing-footer">
        <Text type="secondary">
          Schedule Agent &copy; 2026 &mdash; 微信智能安排规划系统
        </Text>
      </footer>
    </main>
  );
}

/** 粒子背景 */
function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = (canvas.width = window.innerWidth);
    let h = (canvas.height = window.innerHeight);
    let animId: number;

    const particles: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = [];
    const COUNT = 45;

    for (let i = 0; i < COUNT; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 1.8 + 0.5,
        a: Math.random() * 0.15 + 0.04,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(37, 99, 235, ${p.a})`;
        ctx.fill();
      }

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 140) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(37, 99, 235, ${0.03 * (1 - dist / 140)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(draw);
    };

    draw();

    const resize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        width: "100vw",
        height: "100vh",
      }}
    />
  );
}
