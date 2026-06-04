"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { clearAuthSession, decodeTokenRole, decodeTokenUserId, readAuthSession, saveAuthSession } from "@/lib/auth";
import type { AuthSession } from "@/lib/types";

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
    setLoading(false);
  }, []);

  useEffect(() => {
    syncSession();
    const onStorage = () => syncSession();
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
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
    clearAuthSession();
    setSession(null);
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
