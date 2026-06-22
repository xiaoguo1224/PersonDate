import { clearAuthSession, readAuthSession, saveAuthSession } from "@/lib/auth";
import type { ApiEnvelope, AuthSession } from "@/lib/types";

const DEFAULT_API_BASE_URL = "/api";
let refreshInFlight: Promise<string | null> | null = null;

type AuthTokenResponse = {
  access_token: string;
  token_type: "bearer";
  user_id: string;
};

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? DEFAULT_API_BASE_URL;
}

function normalizeApiPath(path: string) {
  if (path === "/api") {
    return "/";
  }
  if (path.startsWith("/api/")) {
    return path.slice(4);
  }
  return path;
}

async function refreshAccessToken() {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    const response = await sendRequest("/auth/refresh", { method: "POST" });

    const payload = (await response.json().catch(() => null)) as ApiEnvelope<AuthTokenResponse> | { detail?: string; message?: string } | null;
    if (!response.ok || !payload || !("data" in payload) || !payload.data?.access_token) {
      return null;
    }

    const storedSession = readAuthSession();
    if (storedSession) {
      const nextSession: AuthSession = {
        ...storedSession,
        accessToken: payload.data.access_token,
        tokenType: payload.data.token_type ?? "bearer",
        userId: payload.data.user_id ?? storedSession.userId,
      };
      saveAuthSession(nextSession);
    }

    return payload.data.access_token;
  })().finally(() => {
    refreshInFlight = null;
  });

  return refreshInFlight;
}

async function sendRequest<T>(path: string, options: RequestInit, accessToken?: string): Promise<Response> {
  const normalizedPath = normalizeApiPath(path);
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  return fetch(`${getApiBaseUrl()}${normalizedPath}`, {
    ...options,
    headers,
    credentials: "include",
  });
}

export async function requestJson<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const normalizedPath = normalizeApiPath(path);
  const response = await sendRequest<T>(normalizedPath, options, accessToken);
  const payload = (await response.json().catch(() => null)) as ApiEnvelope<T> | { detail?: string; message?: string } | null;

  if (!response.ok && accessToken && response.status === 401 && normalizedPath !== "/auth/refresh") {
    const refreshedAccessToken = await refreshAccessToken();
    if (refreshedAccessToken) {
      const retryResponse = await sendRequest<T>(normalizedPath, options, refreshedAccessToken);
      const retryPayload = (await retryResponse.json().catch(() => null)) as
        | ApiEnvelope<T>
        | { detail?: string; message?: string }
        | null;

      if (retryResponse.ok) {
        if (retryPayload && typeof retryPayload === "object" && "data" in retryPayload) {
          return retryPayload.data;
        }
        return retryPayload as T;
      }

      const retryErrorMessage =
        (retryPayload && "detail" in retryPayload && retryPayload.detail) ||
        (retryPayload && "message" in retryPayload && retryPayload.message) ||
        `请求失败：${retryResponse.status}`;
      if (retryResponse.status === 401) {
        clearAuthSession();
      }
      throw new Error(retryErrorMessage ?? "请求失败");
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession();
    }
    const errorMessage =
      (payload && "detail" in payload && payload.detail) ||
      (payload && "message" in payload && payload.message) ||
      `请求失败：${response.status}`;
    throw new Error(errorMessage ?? "请求失败");
  }

  if (payload && typeof payload === "object" && "data" in payload) {
    return payload.data;
  }
  return payload as T;
}
