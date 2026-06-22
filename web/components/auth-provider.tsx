"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { clearAuthSession, decodeTokenRole, decodeTokenUserId, onAuthUnauthorized, readAuthSession, saveAuthSession } from "@/lib/auth";
import { requestJson } from "@/lib/api";
import type { AuthMeResponse, AuthSession } from "@/lib/types";

type AuthContextValue = {
  session: AuthSession | null;
  loading: boolean;
  login: (session: AuthSession) => void;
  logout: () => void;
  refresh: () => void;
  setSession: (session: AuthSession | null) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  const syncSession = useCallback(() => {
    setSession(readAuthSession());
  }, []);

  useEffect(() => {
    let cancelled = false;

    const bootstrapSession = async () => {
      const storedSession = readAuthSession();
      if (!storedSession) {
        try {
          const refreshed = await requestJson<{ access_token: string; token_type: "bearer"; user_id: string }>(
            "/auth/refresh",
            { method: "POST" },
          );
          if (cancelled) {
            return;
          }

          const me = await requestJson<AuthMeResponse>("/auth/me", {}, refreshed.access_token);
          if (cancelled) {
            return;
          }

          const normalizedSession: AuthSession = {
            accessToken: refreshed.access_token,
            tokenType: refreshed.token_type,
            userId: refreshed.user_id,
            role: me.role,
            username: me.username,
            displayName: me.display_name,
            email: me.email,
          };
          saveAuthSession(normalizedSession);
          setSession(normalizedSession);
        } catch {
          if (!cancelled) {
            clearAuthSession();
            setSession(null);
          }
        } finally {
          if (!cancelled) {
            setLoading(false);
          }
        }
        return;
      }

      try {
        const me = await requestJson<AuthMeResponse>("/auth/me", {}, storedSession.accessToken);
        if (cancelled) {
          return;
        }

        const normalizedSession: AuthSession = {
          ...storedSession,
          role: me.role,
          username: me.username,
          displayName: me.display_name,
          email: me.email,
        };
        saveAuthSession(normalizedSession);
        setSession(normalizedSession);
      } catch {
        if (!cancelled) {
          clearAuthSession();
          setSession(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void bootstrapSession();

    const onStorage = () => syncSession();
    window.addEventListener("storage", onStorage);
    const removeUnauthorizedListener = onAuthUnauthorized(() => {
      clearAuthSession();
      setSession(null);
      setLoading(false);
    });

    return () => {
      cancelled = true;
      window.removeEventListener("storage", onStorage);
      removeUnauthorizedListener();
    };
  }, [syncSession]);

  const login = useCallback((nextSession: AuthSession) => {
    const accessToken = nextSession.accessToken;
    const role = nextSession.role ?? decodeTokenRole(accessToken);
    const userId = nextSession.userId ?? decodeTokenUserId(accessToken);
    const normalizedSession: AuthSession = {
      ...nextSession,
      role,
      userId,
      tokenType: nextSession.tokenType ?? "bearer",
    };
    saveAuthSession(normalizedSession);
    setSession(normalizedSession);
  }, []);

  const logout = useCallback(() => {
    void (async () => {
      try {
        await requestJson<Record<string, never>>("/auth/logout", { method: "POST" });
      } catch {
        // 退出时即便后端失败，也清理前端态，避免卡在假登录状态。
      } finally {
        clearAuthSession();
        setSession(null);
      }
    })();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      loading,
      login,
      logout,
      refresh: syncSession,
      setSession,
    }),
    [login, loading, logout, session, syncSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth 必须在 AuthProvider 内使用");
  }
  return context;
}

export function useRole() {
  return useAuth().session?.role ?? "member";
}

export function useAccessToken() {
  return useAuth().session?.accessToken;
}
