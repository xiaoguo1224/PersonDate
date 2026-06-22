import type { AuthSession, UserRole } from "@/lib/types";

const STORAGE_KEY = "schedule-agent.auth";
const AUTH_UNAUTHORIZED_EVENT = "schedule-agent:auth-unauthorized";

function decodeBase64Url(segment: string): string {
  const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  if (typeof window !== "undefined") {
    return window.atob(padded);
  }
  return Buffer.from(padded, "base64").toString("utf8");
}

export function readAuthSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function saveAuthSession(session: AuthSession) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event("storage"));
}

export function clearAuthSession() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event("storage"));
}

export function notifyAuthUnauthorized() {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
}

export function onAuthUnauthorized(handler: () => void) {
  if (typeof window === "undefined") {
    return () => {};
  }
  const listener = () => handler();
  window.addEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
  return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
}

export function decodeTokenRole(token: string): UserRole {
  try {
    const payloadPart = token.split(".")[1];
    if (!payloadPart) {
      return "member";
    }
    const payload = JSON.parse(decodeBase64Url(payloadPart)) as {
      role?: UserRole;
      user_role?: UserRole;
    };
    return payload.role ?? payload.user_role ?? "member";
  } catch {
    return "member";
  }
}

export function decodeTokenUserId(token: string): string | undefined {
  try {
    const payloadPart = token.split(".")[1];
    if (!payloadPart) {
      return undefined;
    }
    const payload = JSON.parse(decodeBase64Url(payloadPart)) as { sub?: string };
    return payload.sub;
  } catch {
    return undefined;
  }
}
