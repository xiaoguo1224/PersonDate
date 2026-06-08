"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadTasks, type TaskItem } from "@/lib/dashboard";

export function useTasks(status?: string) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken ? ["tasks", status] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadTasks(status, accessToken),
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
