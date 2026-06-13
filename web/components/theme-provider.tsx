"use client";

import { App, ConfigProvider, theme } from "antd";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

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
      borderRadius: 8,
      fontFamily: 'var(--font-noto-sans-sc), "PingFang SC", "Microsoft YaHei", sans-serif',
    },
    cssVars: {
      "--bg-primary": "#ffffff",
      "--bg-secondary": "#f0f5ff",
      "--bg-card": "#ffffff",
      "--bg-card-hover": "#f8fbff",
      "--text-primary": "#1a1a2e",
      "--text-secondary": "#64748b",
      "--text-tertiary": "#94a3b8",
      "--border-color": "rgba(148, 163, 184, 0.15)",
      "--border-radius": "8px",
      "--border-radius-lg": "12px",
      "--border-radius-pill": "999px",
      "--accent": "#1677ff",
      "--accent-hover": "#4096ff",
      "--accent-light": "#e6f4ff",
      "--accent-gradient": "linear-gradient(135deg, #1677ff, #40a9ff)",
      "--card-shadow": "0 4px 16px rgba(0,0,0,0.06)",
      "--card-shadow-hover": "0 8px 32px rgba(0,0,0,0.10)",
      "--card-border": "1px solid rgba(148,163,184,0.1)",
      "--card-bg": "rgba(255, 255, 255, 0.78)",
      "--sidebar-gradient": "rgba(255, 255, 255, 0.75)",
      "--hero-gradient": "linear-gradient(135deg, rgba(22,119,255,0.06), rgba(22,119,255,0.02))",
      "--btn-radius": "8px",
      "--tag-radius": "6px",
      "--tag-bg-opacity": "0.08",
      "--input-bg": "#f7f9fc",
      "--input-border": "1px solid rgba(148,163,184,0.18)",
      "--font-weight-heading": "700",
      "--font-weight-body": "400",
      "--tag-style": "flat",
      "--body-bg": "radial-gradient(circle at 18% 8%, rgba(255, 255, 255, 0.92) 0%, rgba(255, 255, 255, 0.48) 12%, transparent 28%), radial-gradient(circle at 80% 12%, rgba(186, 230, 253, 0.42) 0%, rgba(186, 230, 253, 0.18) 16%, transparent 34%), radial-gradient(circle at 50% 0%, rgba(96, 165, 250, 0.18) 0%, transparent 32%), linear-gradient(180deg, #fbfeff 0%, #edf8ff 42%, #dceeff 100%)",
      "--shell-bg": "radial-gradient(circle at top left, rgba(255, 255, 255, 0.42), transparent 24%), radial-gradient(circle at bottom right, rgba(96, 165, 250, 0.1), transparent 28%), linear-gradient(180deg, rgba(255, 255, 255, 0.1), transparent 58%)",
      "--topbar-bg": "rgba(255, 255, 255, 0.72)",
      "--hero-bg": "linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(241, 248, 255, 0.9))",
      "--hero-decorator": "rgba(59, 130, 246, 0.12)",
      "--empty-bg": "linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(248, 252, 255, 0.96))",
      "--card-inner-bg": "linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(247, 250, 253, 0.92))",
      "--nav-hover-bg": "rgba(59, 130, 246, 0.08)",
      "--nav-selected-bg": "linear-gradient(135deg, rgba(59, 130, 246, 0.16), rgba(96, 165, 250, 0.2))",
      "--brand-mark-from": "#3b82f6",
      "--brand-mark-to": "#7dd3fc",
      "--brand-mark-shadow": "rgba(59, 130, 246, 0.18)",
      "--avatar-from": "#93c5fd",
      "--avatar-to": "#dbeafe",
      "--avatar-alt-to": "#bfdbfe",
      "--glass-border": "rgba(148, 163, 184, 0.14)",
      "--hero-decorator-alt": "rgba(14, 165, 233, 0.12)",
      "--card-preview-bg": "rgba(255, 255, 255, 0.64)",
      "--shadow": "0 24px 60px rgba(15, 23, 42, 0.08)",
      "--shadow-soft": "0 12px 32px rgba(15, 23, 42, 0.05)",
      "--surface": "rgba(255, 255, 255, 0.9)",
    },
  },
  "black-gold": {
    algorithm: theme.darkAlgorithm,
    token: {
      colorPrimary: "#d4a853",
      borderRadius: 4,
      colorBgContainer: "#1a1a1a",
      colorBgElevated: "#222222",
      colorBgLayout: "#0d0d0d",
    },
    cssVars: {
      "--bg-primary": "#0d0d0d",
      "--bg-secondary": "#151515",
      "--bg-card": "#1a1a1a",
      "--bg-card-hover": "#222222",
      "--text-primary": "#f0e6d3",
      "--text-secondary": "#a09080",
      "--text-tertiary": "#706050",
      "--border-color": "rgba(212, 168, 83, 0.12)",
      "--border-radius": "4px",
      "--border-radius-lg": "6px",
      "--border-radius-pill": "999px",
      "--accent": "#d4a853",
      "--accent-hover": "#e0b86a",
      "--accent-light": "rgba(212,168,83,0.08)",
      "--accent-gradient": "linear-gradient(135deg, #d4a853, #f0d890)",
      "--card-shadow": "0 4px 20px rgba(0,0,0,0.4)",
      "--card-shadow-hover": "0 8px 40px rgba(0,0,0,0.5)",
      "--card-border": "1px solid rgba(212,168,83,0.12)",
      "--card-bg": "rgba(15, 15, 30, 0.75)",
      "--sidebar-gradient": "rgba(10, 10, 26, 0.82)",
      "--hero-gradient": "linear-gradient(135deg, rgba(212,168,83,0.08), rgba(212,168,83,0.02))",
      "--btn-radius": "4px",
      "--tag-radius": "3px",
      "--tag-bg-opacity": "0.12",
      "--input-bg": "#1a1a1a",
      "--input-border": "1px solid rgba(212,168,83,0.15)",
      "--font-weight-heading": "600",
      "--font-weight-body": "400",
      "--tag-style": "flat",
      "--body-bg": "radial-gradient(circle at 16% 14%, rgba(212, 168, 83, 0.2) 0%, rgba(212, 168, 83, 0.08) 18%, transparent 34%), radial-gradient(circle at 82% 12%, rgba(125, 211, 252, 0.08) 0%, transparent 24%), radial-gradient(circle at 50% -5%, rgba(255, 255, 255, 0.1) 0%, transparent 32%), linear-gradient(180deg, #05050b 0%, #070712 38%, #020204 100%)",
      "--shell-bg": "radial-gradient(circle at top left, rgba(212, 168, 83, 0.06), transparent 24%), radial-gradient(circle at bottom right, rgba(125, 211, 252, 0.04), transparent 30%)",
      "--topbar-bg": "rgba(10, 10, 22, 0.82)",
      "--hero-bg": "linear-gradient(135deg, rgba(18, 18, 34, 0.92), rgba(12, 12, 24, 0.88))",
      "--hero-decorator": "rgba(212, 168, 83, 0.12)",
      "--empty-bg": "linear-gradient(180deg, rgba(18, 18, 32, 0.92), rgba(10, 10, 20, 0.86))",
      "--card-inner-bg": "linear-gradient(180deg, rgba(24, 24, 42, 0.88), rgba(12, 12, 24, 0.84))",
      "--nav-hover-bg": "rgba(212, 168, 83, 0.08)",
      "--nav-selected-bg": "linear-gradient(135deg, rgba(212, 168, 83, 0.2), rgba(255, 230, 160, 0.18))",
      "--brand-mark-from": "#b8860b",
      "--brand-mark-to": "#d4a853",
      "--brand-mark-shadow": "rgba(212, 168, 83, 0.18)",
      "--avatar-from": "#d4a853",
      "--avatar-to": "#f5d799",
      "--avatar-alt-to": "#b8860b",
      "--glass-border": "rgba(212, 168, 83, 0.16)",
      "--hero-decorator-alt": "rgba(180, 140, 60, 0.08)",
      "--card-preview-bg": "rgba(15, 15, 30, 0.64)",
      "--shadow": "0 24px 80px rgba(0, 0, 0, 0.35)",
      "--shadow-soft": "0 12px 40px rgba(0, 0, 0, 0.25)",
      "--surface": "rgba(18, 18, 32, 0.9)",
    },
  },
  "pink": {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: "#e84393",
      borderRadius: 16,
      colorBgContainer: "#ffffff",
      colorBgElevated: "#ffffff",
      colorBgLayout: "#fef6fb",
    },
    cssVars: {
      "--bg-primary": "#fef6fb",
      "--bg-secondary": "#fce4ec",
      "--bg-card": "#ffffff",
      "--bg-card-hover": "#fff5f9",
      "--text-primary": "#4a1a2e",
      "--text-secondary": "#8a5a6e",
      "--text-tertiary": "#b08a9e",
      "--border-color": "rgba(232, 67, 147, 0.1)",
      "--border-radius": "16px",
      "--border-radius-lg": "24px",
      "--border-radius-pill": "999px",
      "--accent": "#e84393",
      "--accent-hover": "#f06292",
      "--accent-light": "rgba(232,67,147,0.08)",
      "--accent-gradient": "linear-gradient(135deg, #e84393, #f06292)",
      "--card-shadow": "0 4px 16px rgba(232,67,147,0.06)",
      "--card-shadow-hover": "0 8px 32px rgba(232,67,147,0.12)",
      "--card-border": "1px solid rgba(232,67,147,0.08)",
      "--card-bg": "rgba(255, 255, 255, 0.75)",
      "--sidebar-gradient": "rgba(255, 255, 255, 0.72)",
      "--hero-gradient": "linear-gradient(135deg, rgba(232,67,147,0.06), rgba(232,67,147,0.02))",
      "--btn-radius": "20px",
      "--tag-radius": "12px",
      "--tag-bg-opacity": "0.1",
      "--input-bg": "#fff5f9",
      "--input-border": "1px solid rgba(232,67,147,0.15)",
      "--font-weight-heading": "700",
      "--font-weight-body": "400",
      "--tag-style": "pill",
      "--body-bg": "radial-gradient(circle at 18% 10%, rgba(255, 255, 255, 0.92) 0%, rgba(255, 255, 255, 0.52) 10%, transparent 24%), radial-gradient(circle at 82% 12%, rgba(255, 192, 203, 0.34) 0%, rgba(255, 192, 203, 0.16) 16%, transparent 32%), radial-gradient(circle at 50% 0%, rgba(232, 67, 147, 0.16) 0%, transparent 30%), linear-gradient(180deg, #fff9fc 0%, #ffeaf2 44%, #ffd9e7 100%)",
      "--shell-bg": "radial-gradient(circle at top left, rgba(232, 67, 147, 0.08), transparent 24%), radial-gradient(circle at bottom right, rgba(255, 192, 203, 0.08), transparent 30%)",
      "--topbar-bg": "rgba(255, 255, 255, 0.74)",
      "--hero-bg": "linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(255, 244, 248, 0.92))",
      "--hero-decorator": "rgba(232, 67, 147, 0.1)",
      "--empty-bg": "linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 249, 252, 0.96))",
      "--card-inner-bg": "linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 244, 248, 0.92))",
      "--nav-hover-bg": "rgba(232, 67, 147, 0.08)",
      "--nav-selected-bg": "linear-gradient(135deg, rgba(232, 67, 147, 0.16), rgba(255, 160, 196, 0.18))",
      "--brand-mark-from": "#e84393",
      "--brand-mark-to": "#fd79a8",
      "--brand-mark-shadow": "rgba(232, 67, 147, 0.18)",
      "--avatar-from": "#e84393",
      "--avatar-to": "#fab1a0",
      "--avatar-alt-to": "#f06292",
      "--glass-border": "rgba(232, 67, 147, 0.14)",
      "--hero-decorator-alt": "rgba(240, 98, 146, 0.08)",
      "--card-preview-bg": "rgba(255, 255, 255, 0.64)",
      "--shadow": "0 24px 60px rgba(232, 67, 147, 0.08)",
      "--shadow-soft": "0 12px 32px rgba(232, 67, 147, 0.05)",
      "--surface": "rgba(255, 255, 255, 0.9)",
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
