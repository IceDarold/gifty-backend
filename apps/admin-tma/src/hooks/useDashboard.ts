import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteSourceProducts, forceRunSource, updateSource, syncSources, connectWeeek, subscribeTopic, unsubscribeTopic, setLanguage, sendTestNotification, runAllSpiders, runSingleSpider, activateDiscoveredCategories, updateMerchant } from '@/lib/api';
import { useAdminChannelQuery, useAdminChannelData, useAdminRequestQuery } from '@/hooks/useAdminStreamQuery';

export function useDashboardData(chatId?: number) {
  const queryClient = useQueryClient();
  const stats = useAdminChannelQuery<any>('dashboard.stats');
  const health = useAdminChannelQuery<any>('dashboard.health');
  const scraping = useAdminChannelQuery<any>('dashboard.scraping');
  const sources = useAdminChannelQuery<any>('dashboard.sources');
  const discoveredCategories = useAdminChannelQuery<any>('dashboard.discovered_categories');
  const trends = useAdminChannelQuery<any>('dashboard.trends');
  const workers = useAdminChannelQuery<any>('dashboard.workers');
  const queue = useAdminChannelQuery<any>('dashboard.queue');
  const live = {
    connected: true,
    items: {
      'global.kpi': useAdminChannelData('dashboard.stats'),
      'global.trends': useAdminChannelData('dashboard.trends'),
      'global.funnel': useAdminChannelData('dashboard.scraping'),
      'llm.summary': useAdminChannelData('llm.stats'),
      'ops.overview': useAdminChannelData('ops.overview'),
    },
  };
  const subscriber = useAdminRequestQuery<any>(
    chatId ? `settings.subscriber:${chatId}` : "",
    {},
    [chatId],
  );
  const merchants = useAdminChannelQuery<any>('settings.merchants');
  const updateMerchantMutation = useMutation({
    mutationFn: ({ siteKey, payload }: { siteKey: string; payload: { name?: string; base_url?: string } }) =>
      updateMerchant(siteKey, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['merchants'] });
      queryClient.invalidateQueries({ queryKey: ['catalog-products'] });
    },
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
  const updateSourceMutation = useMutation({
    mutationFn: ({ id, updates }: { id: number, updates: Record<string, any> }) => updateSource(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      queryClient.invalidateQueries({ queryKey: ['source'] });
    },
  });
  const sendTestNotificationMutation = useMutation({
    mutationFn: (topic: string) => sendTestNotification(topic)
  });
  const runAllSpidersMutation = useMutation({
    mutationFn: () => runAllSpiders(),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sources'] }), 3000);
    },
  });
  const runSingleSpiderMutation = useMutation({
    mutationFn: (id: number) => runSingleSpider(id),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sources'] }), 3000);
    },
  });
  const setLanguageMutation = useMutation({
    mutationFn: (lang: string) => chatId ? setLanguage(chatId, lang) : Promise.reject('No chatId'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriber', chatId] });
    },
  });
  const deleteSourceMutation = useMutation({
    mutationFn: (id: number) => deleteSourceProducts(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
    },
  });
  const activateCategoriesMutation = useMutation({
    mutationFn: (ids: number[]) => activateDiscoveredCategories(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      queryClient.invalidateQueries({ queryKey: ['discovered-categories'] });
    },
  });
  return {
    stats,
    health,
    scraping,
    sources,
    discoveredCategories,
    trends,
    liveAnalytics: live,
    workers,
    queue,
    subscriber,
    merchants,
    updateMerchant: (siteKey: string, payload: { name?: string; base_url?: string }) =>
      updateMerchantMutation.mutateAsync({ siteKey, payload }),
    isUpdatingMerchant: updateMerchantMutation.isPending,
    syncSpiders: syncSpidersMutation.mutate,
    isSyncing: syncSpidersMutation.isPending,
    forceRun: forceRunMutation.mutate,
    isForceRunning: forceRunMutation.isPending,
    toggleSourceActive: ({ id, active }: { id: number, active: boolean }) => updateSourceMutation.mutate({ id, updates: { is_active: active } }),
    updateSource: ({ id, updates }: { id: number, updates: Record<string, any> }) => updateSourceMutation.mutateAsync({ id, updates }),
    isUpdatingSource: updateSourceMutation.isPending,
    connectWeeek: connectWeeekMutation.mutateAsync,
    isConnectingWeeek: connectWeeekMutation.isPending,
    toggleSubscription: toggleSubscriptionMutation.mutate,
    setLanguage: setLanguageMutation.mutate,
    sendTestNotification: sendTestNotificationMutation.mutate,
    isSendingTest: sendTestNotificationMutation.isPending,
    runAll: runAllSpidersMutation.mutate,
    isRunningAll: runAllSpidersMutation.isPending,
    runOne: runSingleSpiderMutation.mutate,
    isRunningOne: runSingleSpiderMutation.isPending,
    deleteData: deleteSourceMutation.mutate,
    isDeleting: deleteSourceMutation.isPending,
    activateDiscoveredCategories: activateCategoriesMutation.mutateAsync,
    isActivatingDiscoveredCategories: activateCategoriesMutation.isPending,
    isLoading: stats.isLoading || health.isLoading || scraping.isLoading || sources.isLoading || subscriber.isLoading,
    isError: stats.isError || health.isError || scraping.isError || sources.isError
  };
}

export function useSourceDetails(id?: number) {
  const channel = id ? `dashboard.source_detail:${id}` : "";
  return useAdminRequestQuery<any>(channel, {}, [id]);
}
export function useSourceProducts(id?: number, limit = 50, offset = 0) {
  const channel = id ? `dashboard.source_products:${id}` : "";
  return useAdminRequestQuery<any>(
    channel,
    { limit, offset },
    [id, limit, offset],
  );
}
export function useCatalogProducts(limit = 20, offset = 0, search?: string, merchant?: string) {
  return useAdminRequestQuery<any>(
    "catalog.products",
    { limit, offset, search: search || "", merchant: merchant || "" },
    [limit, offset, search, merchant],
  );
}
export function useQueueTasks(limit = 50) {
  return useAdminChannelQuery<any>('dashboard.queue');
}
export function useQueueHistory(limit = 100) {
  return useAdminChannelQuery<any>('dashboard.queue');
}
export function useQueueRunDetails(runId?: number | null) {
  const channel = runId ? `ops.run_detail:${runId}` : '';
  return useAdminChannelQuery<any>(channel);
}
