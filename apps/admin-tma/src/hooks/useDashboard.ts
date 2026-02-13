import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchStats, fetchHealth, fetchScraping, fetchSources, fetchSourceDetails, forceRunSource, fetchTrends, syncSources, connectWeeek, fetchSubscriber, subscribeTopic, unsubscribeTopic, setLanguage } from '@/lib/api';


export function useDashboardData(chatId?: number) {
    const queryClient = useQueryClient();

    const stats = useQuery({
        queryKey: ['stats'],
        queryFn: fetchStats,
        refetchInterval: 60000,
    });

    const health = useQuery({
        queryKey: ['health'],
        queryFn: fetchHealth,
        refetchInterval: 30000,
    });

    const scraping = useQuery({
        queryKey: ['scraping'],
        queryFn: fetchScraping,
        refetchInterval: 60000,
    });

    const sources = useQuery({
        queryKey: ['sources'],
        queryFn: fetchSources,
        refetchInterval: 30000,
    });

    const trends = useQuery({
        queryKey: ['trends', 7],
        queryFn: () => fetchTrends(7),
    });

    const subscriber = useQuery({
        queryKey: ['subscriber', chatId],
        queryFn: () => chatId ? fetchSubscriber(chatId) : null,
        enabled: !!chatId,
    });

    const syncSpidersMutation = useMutation({
        mutationFn: (spiders: string[]) => syncSources(spiders),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sources'] });
        },
    });

    const connectWeeekMutation = useMutation({
        mutationFn: ({ token }: { token: string }) => chatId ? connectWeeek(chatId, token) : Promise.reject('No chatId'),
    });

    const toggleSubscriptionMutation = useMutation({
        mutationFn: ({ topic, active }: { topic: string, active: boolean }) =>
            chatId ? (active ? subscribeTopic(chatId, topic) : unsubscribeTopic(chatId, topic)) : Promise.reject('No chatId'),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriber', chatId] });
        },
    });

    const forceRunMutation = useMutation({
        mutationFn: ({ id, strategy }: { id: number, strategy?: string }) => forceRunSource(id, strategy),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sources'] });
        },
    });

    const setLanguageMutation = useMutation({
        mutationFn: (lang: string) => chatId ? setLanguage(chatId, lang) : Promise.reject('No chatId'),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriber', chatId] });
        },
    });

    return {
        stats,
        health,
        scraping,
        sources,
        trends,
        subscriber,
        syncSpiders: syncSpidersMutation.mutate,
        isSyncing: syncSpidersMutation.isPending,
        forceRun: forceRunMutation.mutate,
        isForceRunning: forceRunMutation.isPending,
        connectWeeek: connectWeeekMutation.mutateAsync,
        isConnectingWeeek: connectWeeekMutation.isPending,
        toggleSubscription: toggleSubscriptionMutation.mutate,
        setLanguage: setLanguageMutation.mutate,
        isLoading: stats.isLoading || health.isLoading || scraping.isLoading || sources.isLoading || subscriber.isLoading,
        isError: stats.isError || health.isError || scraping.isError || sources.isError
    };
}


export function useSourceDetails(id?: number) {
    return useQuery({
        queryKey: ['source', id],
        queryFn: () => id ? fetchSourceDetails(id) : null,
        enabled: !!id,
        refetchInterval: (query) => {
            const data: any = query.state.data;
            return data?.status === 'running' ? 5000 : 30000;
        },
    });
}


