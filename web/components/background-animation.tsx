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
