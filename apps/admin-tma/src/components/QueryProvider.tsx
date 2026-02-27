"use client";

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export function QueryProvider({ children }: { children: React.ReactNode }) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        // At most 2 total attempts: initial + 1 retry.
                        retry: 1,
                        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 4000),
                        refetchOnWindowFocus: false,
                    },
                    mutations: {
                        retry: 1,
                        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 4000),
                    },
                },
            }),
    );

    return (
        <QueryClientProvider client={queryClient}>
            {children}
        </QueryClientProvider>
    );
}
