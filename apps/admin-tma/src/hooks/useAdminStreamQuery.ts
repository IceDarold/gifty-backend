"use client";

import { useMemo, useEffect, useState } from "react";
import { useAdminChannel, useAdminRequest } from "@/contexts/AdminStreamContext";

export type StreamQuery<T> = {
  data?: T;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<void>;
};

export function useAdminChannelQuery<T = any>(channel: string): StreamQuery<T> {
  const { data, connected } = useAdminChannel<T>(channel);
  return useMemo(
    () => ({
      data,
      isLoading: !connected && data === undefined,
      isError: false,
      error: null,
      refetch: async () => {},
    }),
    [connected, data],
  );
}

export function useAdminChannelData<T = any>(channel: string): T | undefined {
  return useAdminChannel<T>(channel).data;
}

export function useAdminRequestQuery<T = any>(
  channel: string,
  params: Record<string, any>,
  deps: any[] = [],
): StreamQuery<T> {
  const request = useAdminRequest();
  const [state, setState] = useState<{
    data?: T;
    isLoading: boolean;
    error: unknown;
  }>({ data: undefined, isLoading: true, error: null });

  useEffect(() => {
    let mounted = true;
    if (!channel) {
      setState({ data: undefined, isLoading: false, error: null });
      return () => {
        mounted = false;
      };
    }
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    request(channel, params)
      .then((res) => {
        if (!mounted) return;
        setState({ data: res as T, isLoading: false, error: null });
      })
      .catch((err) => {
        if (!mounted) return;
        setState({ data: undefined, isLoading: false, error: err });
      });
    return () => {
      mounted = false;
    };
  }, [channel, JSON.stringify(params), ...deps]);

  return {
    data: state.data,
    isLoading: state.isLoading,
    isError: !!state.error,
    error: state.error,
    refetch: async () => {
      if (!channel) {
        setState({ data: undefined, isLoading: false, error: null });
        return;
      }
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const res = await request(channel, params);
        setState({ data: res as T, isLoading: false, error: null });
      } catch (err) {
        setState({ data: undefined, isLoading: false, error: err });
      }
    },
  };
}
