"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadScheduledItems, type ScheduledItem } from "@/lib/dashboard";

export function useScheduledItems(params: {
  date?: string;
  start_time?: string;
  end_time?: string;
  keyword?: string;
  status?: string;
}) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken
    ? ["scheduled-items", params.date, params.start_time, params.end_time, params.keyword, params.status]
    : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadScheduledItems(params, accessToken),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    },
  );

  return {
    items: data ?? [],
    isLoading,
    error,
    refresh: () => mutate(),
  };
}
