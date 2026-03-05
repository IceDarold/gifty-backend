import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { OpsRuntimeSettingsProvider } from "@/contexts/OpsRuntimeSettingsContext";
import { TMAProvider } from "@/components/TMAProvider";
import { NotificationCenterProvider } from "@/contexts/NotificationCenterContext";
import { RetryRegistryProvider } from "@/contexts/RetryRegistryContext";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, "wrapper"> & { queryClient?: QueryClient },
) {
  const queryClient = options?.queryClient || createTestQueryClient();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <OpsRuntimeSettingsProvider>
            <RetryRegistryProvider>
              <NotificationCenterProvider>
                <TMAProvider>{children}</TMAProvider>
              </NotificationCenterProvider>
            </RetryRegistryProvider>
          </OpsRuntimeSettingsProvider>
        </LanguageProvider>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
