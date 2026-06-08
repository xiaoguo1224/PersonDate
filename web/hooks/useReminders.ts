"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadReminders, type ReminderItem } from "@/lib/dashboard";

export function useReminders(status?: string) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken ? ["reminders", status] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadReminders(status, accessToken),
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
