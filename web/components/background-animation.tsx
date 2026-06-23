"use client";

import { useCallback, useEffect, useState } from "react";
import { useTheme, type ThemeName } from "./theme-provider";
import { BubbleEffect, StarfieldEffect, PetalEffect } from "./theme-effects";
import blueWhiteWallpaper from "./theme-assets/blue-white-wallpaper.png";
import blackGoldWallpaper from "./theme-assets/black-gold-wallpaper.png";
import pinkSakuraWallpaper from "./theme-assets/pink-sakura-wallpaper.png";

type MotionPreferences = {
  reduceMotion: boolean;
  isCompact: boolean;
};

const DEFAULT_MOTION: MotionPreferences = {
  reduceMotion: true,
  isCompact: true,
};

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
  const [motion, setMotion] = useState<MotionPreferences>(DEFAULT_MOTION);

  useEffect(() => {
    if (themeName !== currentTheme) {
      if (!motion.reduceMotion && !motion.isCompact) {
        setPrevTheme(currentTheme);
        setCurrentTheme(themeName);
        return;
      }

      setPrevTheme(null);
      setCurrentTheme(themeName);
    }
  }, [themeName, currentTheme, motion.isCompact, motion.reduceMotion]);

  useEffect(() => {
    if (!motion.reduceMotion && !motion.isCompact) {
      return;
    }

    if (prevTheme) {
      setPrevTheme(null);
    }
  }, [motion.isCompact, motion.reduceMotion, prevTheme]);

  useEffect(() => {
    const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const compactQuery = window.matchMedia("(max-width: 767px)");

    const update = () => {
      setMotion({
        reduceMotion: reduceQuery.matches,
        isCompact: compactQuery.matches,
      });
    };

    update();

    const bind = (query: MediaQueryList) => {
      if (query.addEventListener) {
        query.addEventListener("change", update);
        return () => query.removeEventListener("change", update);
      }

      query.addListener(update);
      return () => query.removeListener(update);
    };

    const unbindReduce = bind(reduceQuery);
    const unbindCompact = bind(compactQuery);

    return () => {
      unbindReduce();
      unbindCompact();
    };
  }, []);

  const handlePrevFadeOut = useCallback(() => {
    setPrevTheme(null);
  }, []);

  const CurrentEffect = EFFECT_MAP[currentTheme];
  const PrevEffect = prevTheme ? EFFECT_MAP[prevTheme] : null;
  const currentBackdrop = BACKDROP_MAP[currentTheme];
  const prevBackdrop = prevTheme ? BACKDROP_MAP[prevTheme] : null;
  const shouldAnimate = !motion.reduceMotion && !motion.isCompact;

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
          opacity: shouldAnimate && prevTheme ? 0 : 1,
          animation: shouldAnimate
            ? prevTheme
              ? "themeBackdropFadeIn 420ms ease both, themeBackdropDrift 28s ease-in-out infinite alternate"
              : "themeBackdropDrift 28s ease-in-out infinite alternate"
            : "none",
          transform: "translateZ(0)",
        }}
      />
      {shouldAnimate && prevBackdrop && (
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
            animation: "themeBackdropFadeOut 420ms ease forwards, themeBackdropDrift 28s ease-in-out infinite alternate",
            transform: "translateZ(0)",
          }}
        />
      )}
      {shouldAnimate && PrevEffect && (
        <PrevEffect visible={false} onFadeOutComplete={handlePrevFadeOut} />
      )}
      {shouldAnimate ? <CurrentEffect visible={true} /> : null}
    </div>
  );
}
