import type { ApiEnvelope } from "@/lib/types";

const DEFAULT_API_BASE_URL = "/api";

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? DEFAULT_API_BASE_URL;
}

export async function requestJson<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  const payload = (await response.json().catch(() => null)) as
    | ApiEnvelope<T>
    | { detail?: string; message?: string }
    | null;

  if (!response.ok) {
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
