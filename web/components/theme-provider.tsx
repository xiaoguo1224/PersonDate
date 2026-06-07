"use client";

import { ConfigProvider, theme } from "antd";
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
      "--card-bg": "#ffffff",
      "--sidebar-gradient": "linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,249,252,0.98))",
      "--hero-gradient": "linear-gradient(135deg, rgba(22,119,255,0.06), rgba(22,119,255,0.02))",
      "--btn-radius": "8px",
      "--tag-radius": "6px",
      "--tag-bg-opacity": "0.08",
      "--input-bg": "#f7f9fc",
      "--input-border": "1px solid rgba(148,163,184,0.18)",
      "--font-weight-heading": "700",
      "--font-weight-body": "400",
      "--tag-style": "flat",
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
      "--card-bg": "linear-gradient(145deg, rgba(26,26,26,0.95), rgba(20,20,20,0.98))",
      "--sidebar-gradient": "linear-gradient(180deg, #111111, #0d0d0d)",
      "--hero-gradient": "linear-gradient(135deg, rgba(212,168,83,0.08), rgba(212,168,83,0.02))",
      "--btn-radius": "4px",
      "--tag-radius": "3px",
      "--tag-bg-opacity": "0.12",
      "--input-bg": "#1a1a1a",
      "--input-border": "1px solid rgba(212,168,83,0.15)",
      "--font-weight-heading": "600",
      "--font-weight-body": "400",
      "--tag-style": "flat",
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
      "--card-bg": "#ffffff",
      "--sidebar-gradient": "linear-gradient(180deg, rgba(255,255,255,0.95), rgba(254,246,251,0.98))",
      "--hero-gradient": "linear-gradient(135deg, rgba(232,67,147,0.06), rgba(232,67,147,0.02))",
      "--btn-radius": "20px",
      "--tag-radius": "12px",
      "--tag-bg-opacity": "0.1",
      "--input-bg": "#fff5f9",
      "--input-border": "1px solid rgba(232,67,147,0.15)",
      "--font-weight-heading": "700",
      "--font-weight-body": "400",
      "--tag-style": "pill",
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
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}
