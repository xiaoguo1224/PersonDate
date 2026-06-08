"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadConflicts, type ConflictItem } from "@/lib/dashboard";

export function useConflicts(status?: string) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken ? ["conflicts", status] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadConflicts(status, accessToken),
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
