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

const themeConfigs: Record<ThemeName, {
  algorithm: typeof theme.defaultAlgorithm | typeof theme.darkAlgorithm;
  token: Record<string, unknown>;
  cssVars: Record<string, string>;
}> = {
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
      "--text-primary": "#1a1a2e",
      "--text-secondary": "#64748b",
      "--text-tertiary": "#94a3b8",
      "--border-color": "rgba(148, 163, 184, 0.15)",
      "--accent": "#1677ff",
      "--accent-light": "#e6f4ff",
      "--shadow": "rgba(0, 0, 0, 0.06)",
    },
  },
  "black-gold": {
    algorithm: theme.darkAlgorithm,
    token: {
      colorPrimary: "#d4a853",
      borderRadius: 6,
      colorBgContainer: "#1a1a1a",
      colorBgElevated: "#222222",
      colorBgLayout: "#0d0d0d",
    },
    cssVars: {
      "--bg-primary": "#0d0d0d",
      "--bg-secondary": "#1a1a1a",
      "--bg-card": "#1a1a1a",
      "--text-primary": "#f0e6d3",
      "--text-secondary": "#a09080",
      "--text-tertiary": "#706050",
      "--border-color": "rgba(212, 168, 83, 0.15)",
      "--accent": "#d4a853",
      "--accent-light": "rgba(212, 168, 83, 0.1)",
      "--shadow": "rgba(0, 0, 0, 0.3)",
    },
  },
  "pink": {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: "#e84393",
      borderRadius: 12,
      colorBgContainer: "#fff5f9",
      colorBgElevated: "#ffffff",
      colorBgLayout: "#fef6fb",
    },
    cssVars: {
      "--bg-primary": "#fef6fb",
      "--bg-secondary": "#fce4ec",
      "--bg-card": "#ffffff",
      "--text-primary": "#4a1a2e",
      "--text-secondary": "#8a5a6e",
      "--text-tertiary": "#b08a9e",
      "--border-color": "rgba(232, 67, 147, 0.12)",
      "--accent": "#e84393",
      "--accent-light": "rgba(232, 67, 147, 0.08)",
      "--shadow": "rgba(232, 67, 147, 0.08)",
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
