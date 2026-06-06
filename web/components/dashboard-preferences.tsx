"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { requestJson } from "@/lib/api";
import type { UserSettingsResponse } from "@/lib/types";

type DashboardPreferencesValue = {
  timezone: string;
  loading: boolean;
};

const DashboardPreferencesContext = createContext<DashboardPreferencesValue | null>(null);

export function DashboardPreferencesProvider({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;
  const [timezone, setTimezone] = useState("Asia/Shanghai");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    if (!accessToken) {
      setTimezone("Asia/Shanghai");
      setLoading(false);
      return () => {
        alive = false;
      };
    }

    setLoading(true);
    requestJson<UserSettingsResponse>("/api/me/settings", {}, accessToken)
      .then((result) => {
        if (alive) {
          setTimezone(result.default_timezone || "Asia/Shanghai");
        }
      })
      .catch(() => {
        if (alive) {
          setTimezone("Asia/Shanghai");
        }
      })
      .finally(() => {
        if (alive) {
          setLoading(false);
        }
      });

    return () => {
      alive = false;
    };
  }, [accessToken]);

  const value = useMemo(
    () => ({
      timezone,
      loading,
    }),
    [loading, timezone],
  );

  return <DashboardPreferencesContext.Provider value={value}>{children}</DashboardPreferencesContext.Provider>;
}

export function useDashboardTimezone() {
  const context = useContext(DashboardPreferencesContext);
  if (!context) {
    return {
      timezone: "Asia/Shanghai",
      loading: true,
    };
  }
  return context;
}
