"use client";

import { App, ConfigProvider, theme } from "antd";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import blueWhiteWallpaper from "./theme-assets/blue-white-wallpaper.png";
import blackGoldWallpaper from "./theme-assets/black-gold-wallpaper.png";
import pinkSakuraWallpaper from "./theme-assets/pink-sakura-wallpaper.png";

export type ThemeName = "blue-white" | "black-gold" | "pink";

type ThemeContextValue = {
  themeName: ThemeName;
  setThemeName: (name: ThemeName) => void;
};

const STORAGE_KEY = "dashboard-theme";

const ThemeContext = createContext<ThemeContextValue>({
  themeName: "blue-white",
  setThemeName: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

type ThemeDef = {
  algorithm: typeof theme.defaultAlgorithm | typeof theme.darkAlgorithm;
  token: Record<string, unknown>;
  cssVars: Record<string, string>;
};

const themeConfigs: Record<ThemeName, ThemeDef> = {
  "blue-white": {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: "#1677ff",
      borderRadius: 20,
      fontFamily: 'var(--font-noto-sans-sc), "PingFang SC", "Microsoft YaHei", sans-serif',
    },
    cssVars: {
      "--bg-primary": "#f7fbff",
      "--bg-secondary": "#eef6ff",
      "--bg-card": "#ffffff",
      "--bg-card-hover": "#fbfdff",
      "--text-primary": "#193a63",
      "--text-secondary": "#5f7596",
      "--text-tertiary": "#9db0c6",
      "--border-color": "rgba(255, 255, 255, 0.56)",
      "--border-radius": "20px",
      "--border-radius-lg": "24px",
      "--border-radius-pill": "999px",
      "--accent": "#1677ff",
      "--accent-hover": "#4096ff",
      "--accent-light": "rgba(22, 119, 255, 0.12)",
      "--accent-gradient": "linear-gradient(135deg, #1e88ff, #7cc8ff)",
      "--card-shadow": "0 10px 30px rgba(47, 94, 164, 0.08)",
      "--card-shadow-hover": "0 18px 48px rgba(47, 94, 164, 0.12)",
      "--card-border": "1px solid rgba(255,255,255,0.62)",
      "--card-bg": "rgba(255, 255, 255, 0.72)",
      "--sidebar-gradient": "rgba(255, 255, 255, 0.66)",
      "--hero-gradient": "linear-gradient(135deg, rgba(255,255,255,0.84), rgba(232, 244, 255, 0.7))",
      "--btn-radius": "18px",
      "--tag-radius": "999px",
      "--tag-bg-opacity": "0.08",
      "--input-bg": "rgba(255, 255, 255, 0.74)",
      "--input-border": "1px solid rgba(255,255,255,0.6)",
      "--font-weight-heading": "700",
      "--font-weight-body": "400",
      "--tag-style": "pill",
      "--body-bg": "linear-gradient(180deg, rgba(255,255,255,0.34) 0%, rgba(234, 244, 255, 0.6) 45%, rgba(220, 236, 252, 0.78) 100%)",
      "--shell-bg": "radial-gradient(circle at top left, rgba(255, 255, 255, 0.38), transparent 24%), radial-gradient(circle at bottom right, rgba(96, 165, 250, 0.1), transparent 28%)",
      "--topbar-bg": "rgba(255, 255, 255, 0.54)",
      "--hero-bg": "linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(244, 249, 255, 0.6))",
      "--hero-decorator": "rgba(59, 130, 246, 0.1)",
      "--empty-bg": "rgba(255, 255, 255, 0.66)",
      "--card-inner-bg": "rgba(255, 255, 255, 0.6)",
      "--nav-hover-bg": "rgba(59, 130, 246, 0.08)",
      "--nav-selected-bg": "linear-gradient(135deg, rgba(59, 130, 246, 0.14), rgba(96, 165, 250, 0.18))",
      "--brand-mark-from": "#3b82f6",
      "--brand-mark-to": "#8fd3ff",
      "--brand-mark-shadow": "rgba(59, 130, 246, 0.12)",
      "--avatar-from": "#8ec9ff",
      "--avatar-to": "#e8f4ff",
      "--avatar-alt-to": "#b8dcff",
      "--glass-border": "rgba(255,255,255,0.62)",
      "--hero-decorator-alt": "rgba(14, 165, 233, 0.1)",
      "--card-preview-bg": "rgba(255, 255, 255, 0.58)",
      "--shadow": "0 22px 52px rgba(55, 94, 156, 0.1)",
      "--shadow-soft": "0 14px 36px rgba(55, 94, 156, 0.06)",
      "--surface": "rgba(255, 255, 255, 0.68)",
      "--theme-backdrop-image": `url('${blueWhiteWallpaper.src}')`,
      "--theme-backdrop-overlay": "linear-gradient(180deg, rgba(255,255,255,0.16), rgba(228, 241, 255, 0.36), rgba(205, 229, 248, 0.16))",
    },
  },
  "black-gold": {
    algorithm: theme.darkAlgorithm,
    token: {
      colorPrimary: "#d4a853",
      borderRadius: 20,
      fontFamily: 'var(--font-noto-serif-sc), "PingFang SC", serif',
      colorBgContainer: "#1a1a1a",
      colorBgElevated: "#222222",
      colorBgLayout: "#0d0d0d",
    },
    cssVars: {
      "--bg-primary": "#0d0d0d",
      "--bg-secondary": "#0a0b10",
      "--bg-card": "#10131b",
      "--bg-card-hover": "#151924",
      "--text-primary": "#f6ead0",
      "--text-secondary": "#bba37b",
      "--text-tertiary": "#8f7a58",
      "--border-color": "rgba(224, 179, 92, 0.12)",
      "--border-radius": "20px",
      "--border-radius-lg": "24px",
      "--border-radius-pill": "999px",
      "--accent": "#e0b35c",
      "--accent-hover": "#f2cf83",
      "--accent-light": "rgba(224,179,92,0.1)",
      "--accent-gradient": "linear-gradient(135deg, #e0b35c, #ffd98a)",
      "--card-shadow": "0 18px 50px rgba(0,0,0,0.28)",
      "--card-shadow-hover": "0 22px 64px rgba(0,0,0,0.4)",
      "--card-border": "1px solid rgba(224,179,92,0.12)",
      "--card-bg": "rgba(10, 12, 18, 0.66)",
      "--sidebar-gradient": "rgba(6, 8, 14, 0.72)",
      "--hero-gradient": "linear-gradient(135deg, rgba(18, 18, 24, 0.78), rgba(11, 11, 16, 0.76))",
      "--btn-radius": "16px",
      "--tag-radius": "999px",
      "--tag-bg-opacity": "0.12",
      "--input-bg": "rgba(12, 14, 22, 0.72)",
      "--input-border": "1px solid rgba(224,179,92,0.15)",
      "--font-weight-heading": "500",
      "--font-weight-body": "400",
      "--tag-style": "flat",
      "--body-bg": "linear-gradient(180deg, rgba(5,6,10,0.92) 0%, rgba(8,10,15,0.88) 52%, rgba(4,5,8,0.95) 100%)",
      "--shell-bg": "radial-gradient(circle at top left, rgba(224, 179, 92, 0.06), transparent 24%), radial-gradient(circle at bottom right, rgba(125, 211, 252, 0.03), transparent 30%)",
      "--topbar-bg": "rgba(7, 8, 12, 0.72)",
      "--hero-bg": "linear-gradient(135deg, rgba(12, 14, 20, 0.68), rgba(8, 9, 14, 0.7))",
      "--hero-decorator": "rgba(224, 179, 92, 0.12)",
      "--empty-bg": "rgba(10, 12, 18, 0.64)",
      "--card-inner-bg": "rgba(14, 16, 24, 0.62)",
      "--nav-hover-bg": "rgba(224, 179, 92, 0.08)",
      "--nav-selected-bg": "linear-gradient(135deg, rgba(224, 179, 92, 0.16), rgba(255, 217, 138, 0.14))",
      "--brand-mark-from": "#d2a34f",
      "--brand-mark-to": "#f0cf7a",
      "--brand-mark-shadow": "rgba(224, 179, 92, 0.12)",
      "--avatar-from": "#d2a34f",
      "--avatar-to": "#f5df9a",
      "--avatar-alt-to": "#a57b2a",
      "--glass-border": "rgba(224, 179, 92, 0.1)",
      "--hero-decorator-alt": "rgba(180, 140, 60, 0.06)",
      "--card-preview-bg": "rgba(8, 10, 14, 0.58)",
      "--shadow": "0 24px 84px rgba(0, 0, 0, 0.34)",
      "--shadow-soft": "0 12px 40px rgba(0, 0, 0, 0.22)",
      "--surface": "rgba(12, 14, 20, 0.78)",
      "--theme-backdrop-image": `url('${blackGoldWallpaper.src}')`,
      "--theme-backdrop-overlay": "linear-gradient(180deg, rgba(1, 2, 5, 0.26), rgba(2, 3, 6, 0.48), rgba(5, 6, 10, 0.3))",
    },
  },
  "pink": {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: "#e84393",
      borderRadius: 22,
      fontFamily: 'var(--font-noto-serif-sc), "PingFang SC", serif',
      colorBgContainer: "#ffffff",
      colorBgElevated: "#ffffff",
      colorBgLayout: "#fef6fb",
    },
    cssVars: {
      "--bg-primary": "#fff7fa",
      "--bg-secondary": "#ffeef4",
      "--bg-card": "#ffffff",
      "--bg-card-hover": "#fffafc",
      "--text-primary": "#5a2738",
      "--text-secondary": "#8e6474",
      "--text-tertiary": "#c09cac",
      "--border-color": "rgba(255, 255, 255, 0.52)",
      "--border-radius": "22px",
      "--border-radius-lg": "24px",
      "--border-radius-pill": "999px",
      "--accent": "#e84393",
      "--accent-hover": "#f45da1",
      "--accent-light": "rgba(232,67,147,0.1)",
      "--accent-gradient": "linear-gradient(135deg, #e84393, #ff8eb7)",
      "--card-shadow": "0 10px 30px rgba(231, 111, 147, 0.08)",
      "--card-shadow-hover": "0 18px 48px rgba(231, 111, 147, 0.12)",
      "--card-border": "1px solid rgba(255,255,255,0.64)",
      "--card-bg": "rgba(255, 255, 255, 0.7)",
      "--sidebar-gradient": "rgba(255, 255, 255, 0.62)",
      "--hero-gradient": "linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(255, 244, 249, 0.58))",
      "--btn-radius": "18px",
      "--tag-radius": "999px",
      "--tag-bg-opacity": "0.1",
      "--input-bg": "rgba(255, 255, 255, 0.72)",
      "--input-border": "1px solid rgba(255,255,255,0.6)",
      "--font-weight-heading": "600",
      "--font-weight-body": "400",
      "--tag-style": "pill",
      "--body-bg": "linear-gradient(180deg, rgba(255, 252, 253, 0.44) 0%, rgba(255, 239, 244, 0.62) 48%, rgba(255, 224, 233, 0.82) 100%)",
      "--shell-bg": "radial-gradient(circle at top left, rgba(232, 67, 147, 0.08), transparent 24%), radial-gradient(circle at bottom right, rgba(255, 192, 203, 0.08), transparent 30%)",
      "--topbar-bg": "rgba(255, 255, 255, 0.58)",
      "--hero-bg": "linear-gradient(135deg, rgba(255, 255, 255, 0.74), rgba(255, 242, 247, 0.62))",
      "--hero-decorator": "rgba(232, 67, 147, 0.1)",
      "--empty-bg": "rgba(255, 255, 255, 0.64)",
      "--card-inner-bg": "rgba(255, 255, 255, 0.6)",
      "--nav-hover-bg": "rgba(232, 67, 147, 0.08)",
      "--nav-selected-bg": "linear-gradient(135deg, rgba(232, 67, 147, 0.14), rgba(255, 160, 196, 0.18))",
      "--brand-mark-from": "#e84393",
      "--brand-mark-to": "#ff9cc0",
      "--brand-mark-shadow": "rgba(232, 67, 147, 0.12)",
      "--avatar-from": "#f06a9d",
      "--avatar-to": "#ffc3d8",
      "--avatar-alt-to": "#ff90b2",
      "--glass-border": "rgba(255,255,255,0.62)",
      "--hero-decorator-alt": "rgba(240, 98, 146, 0.08)",
      "--card-preview-bg": "rgba(255, 255, 255, 0.56)",
      "--shadow": "0 22px 52px rgba(230, 118, 159, 0.08)",
      "--shadow-soft": "0 14px 36px rgba(230, 118, 159, 0.05)",
      "--surface": "rgba(255, 255, 255, 0.68)",
      "--theme-backdrop-image": `url('${pinkSakuraWallpaper.src}')`,
      "--theme-backdrop-overlay": "linear-gradient(180deg, rgba(255,248,250,0.12), rgba(255,235,241,0.18), rgba(255,219,231,0.08))",
    },
  },
};

export default function ThemeProvider({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [themeName, setThemeState] = useState<ThemeName>("blue-white");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeName | null;
    if (saved && saved in themeConfigs) {
      setThemeState(saved);
    }
  }, []);

  const setThemeName = useCallback((name: ThemeName) => {
    setThemeState(name);
    localStorage.setItem(STORAGE_KEY, name);
  }, []);

  const config = themeConfigs[themeName];

  useEffect(() => {
    const root = document.documentElement;
    for (const [key, value] of Object.entries(config.cssVars)) {
      root.style.setProperty(key, value);
    }
  }, [config.cssVars]);

  const value = useMemo(() => ({ themeName, setThemeName }), [themeName, setThemeName]);

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider
        theme={{
          algorithm: config.algorithm,
          token: config.token as Record<string, unknown>,
        }}
      >
        <App>{children}</App>
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}
