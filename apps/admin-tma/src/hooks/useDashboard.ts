import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchStats, fetchHealth, fetchScraping, fetchSources, fetchTrends, syncSources, connectWeeek, fetchSubscriber, subscribeTopic, unsubscribeTopic, setLanguage } from '@/lib/api';

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
        connectWeeek: connectWeeekMutation.mutateAsync,
        isConnectingWeeek: connectWeeekMutation.isPending,
        toggleSubscription: toggleSubscriptionMutation.mutate,
        setLanguage: setLanguageMutation.mutate,
        isLoading: stats.isLoading || health.isLoading || scraping.isLoading || sources.isLoading || subscriber.isLoading,
        isError: stats.isError || health.isError || scraping.isError || sources.isError
    };
}
