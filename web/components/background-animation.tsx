"use client";

import { useCallback, useEffect, useState } from "react";
import { useTheme, type ThemeName } from "./theme-provider";
import { BubbleEffect, StarfieldEffect, PetalEffect } from "./theme-effects";
import blueWhiteWallpaper from "./theme-assets/blue-white-wallpaper.png";
import blackGoldWallpaper from "./theme-assets/black-gold-wallpaper.png";
import pinkSakuraWallpaper from "./theme-assets/pink-sakura-wallpaper.png";

const BACKDROP_MAP: Record<
  ThemeName,
  {
    image: string;
    overlay: string;
  }
> = {
  "blue-white": {
    image: `url('${blueWhiteWallpaper.src}')`,
    overlay:
      "linear-gradient(180deg, rgba(255,255,255,0.18), rgba(223, 239, 255, 0.24), rgba(198, 225, 247, 0.12))",
  },
  "black-gold": {
    image: `url('${blackGoldWallpaper.src}')`,
    overlay:
      "linear-gradient(180deg, rgba(1,2,5,0.18), rgba(3,5,10,0.34), rgba(5,7,12,0.22))",
  },
  pink: {
    image: `url('${pinkSakuraWallpaper.src}')`,
    overlay:
      "linear-gradient(180deg, rgba(255,248,250,0.14), rgba(255,235,241,0.18), rgba(255,223,232,0.08))",
  },
};

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
  const currentBackdrop = BACKDROP_MAP[currentTheme];
  const prevBackdrop = prevTheme ? BACKDROP_MAP[prevTheme] : null;

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
      <div
        key={`backdrop-${currentTheme}`}
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `${currentBackdrop.overlay}, ${currentBackdrop.image}`,
          backgroundSize: "cover, cover",
          backgroundPosition: "center, center",
          backgroundRepeat: "no-repeat, no-repeat",
          opacity: prevTheme ? 0 : 1,
          animation: prevTheme ? "themeBackdropFadeIn 420ms ease both" : undefined,
          transform: "translateZ(0)",
        }}
      />
      {prevBackdrop && (
        <div
          key={`backdrop-${prevTheme}`}
          onAnimationEnd={() => setPrevTheme(null)}
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `${prevBackdrop.overlay}, ${prevBackdrop.image}`,
            backgroundSize: "cover, cover",
            backgroundPosition: "center, center",
            backgroundRepeat: "no-repeat, no-repeat",
            opacity: 1,
            animation: "themeBackdropFadeOut 420ms ease forwards",
            transform: "translateZ(0)",
          }}
        />
      )}
      {PrevEffect && (
        <PrevEffect visible={false} onFadeOutComplete={handlePrevFadeOut} />
      )}
      <CurrentEffect visible={true} />
    </div>
  );
}
