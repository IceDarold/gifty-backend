import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    bulkUpdateOpsSources,
    fetchOpsActiveRuns,
    fetchOpsDiscoveryCategories,
    fetchOpsOverview,
    fetchOpsPipeline,
    fetchOpsRunDetails,
    fetchOpsSites,
    forceRunSource,
    getOpsStreamUrl,
    promoteOpsDiscovery,
    reactivateOpsDiscovery,
    rejectOpsDiscovery,
    runOpsSiteDiscovery,
    retryOpsRun,
} from '@/lib/api';
import { useOpsRuntimeSettings } from '@/contexts/OpsRuntimeSettingsContext';

type OpsEvent = {
    type: string;
    payload: Record<string, any>;
};

const MAX_BACKOFF_MS = 30000;

export function useOperationsData(initialSiteKey?: string) {
    const queryClient = useQueryClient();
    const { getIntervalMs } = useOpsRuntimeSettings();
    const [selectedSiteKey, setSelectedSiteKey] = useState<string | null>(initialSiteKey || null);
    const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
    const [streamState, setStreamState] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
    const [streamError, setStreamError] = useState<string | null>(null);
    const [discoveryStateFilter, setDiscoveryStateFilter] = useState<string>('new,promoted,rejected,inactive');
    const [discoverySearch, setDiscoverySearch] = useState<string>('');
    const retryDelayRef = useRef(1000);
    const reconnectTimerRef = useRef<number | null>(null);
    const selectedSiteRef = useRef<string | null>(null);
    const selectedRunRef = useRef<number | null>(null);

    useEffect(() => {
        selectedSiteRef.current = selectedSiteKey;
    }, [selectedSiteKey]);

    useEffect(() => {
        selectedRunRef.current = selectedRunId;
    }, [selectedRunId]);

    const pollMs = (key: string, fallback: number) => {
        if (streamState === 'connected') return 300000;
        return getIntervalMs(key, fallback);
    };

    const overview = useQuery({
        queryKey: ['ops-overview'],
        queryFn: fetchOpsOverview,
        refetchInterval: (query) => (query.state.error ? false : pollMs('ops.overview_ms', 30000)),
    });

    const sites = useQuery({
        queryKey: ['ops-sites'],
        queryFn: fetchOpsSites,
        refetchInterval: (query) => (query.state.error ? false : pollMs('ops.sites_ms', 30000)),
    });

    useEffect(() => {
        if (!selectedSiteKey && sites.data?.items?.length) {
            setSelectedSiteKey(sites.data.items[0].site_key);
        }
    }, [selectedSiteKey, sites.data]);

    const pipeline = useQuery({
        queryKey: ['ops-pipeline', selectedSiteKey],
        queryFn: () => fetchOpsPipeline(selectedSiteKey as string),
        enabled: !!selectedSiteKey,
        refetchInterval: (query) => (query.state.error ? false : pollMs('ops.pipeline_ms', 30000)),
    });

    const activeRuns = useQuery({
        queryKey: ['ops-runs-active'],
        queryFn: () => fetchOpsActiveRuns(200),
        refetchInterval: (query) => (query.state.error ? false : pollMs('ops.active_runs_ms', 30000)),
    });

    const runDetails = useQuery({
        queryKey: ['ops-run-details', selectedRunId],
        queryFn: () => fetchOpsRunDetails(selectedRunId as number),
        enabled: !!selectedRunId,
        refetchInterval: (q) => {
            if (q.state.error) return false;
            const status = (q.state.data as any)?.item?.run_status;
            return status === 'running' || status === 'queued' ? pollMs('ops.run_details_ms', 15000) : false;
        },
    });

    const discovery = useQuery({
        queryKey: ['ops-discovery', selectedSiteKey, discoveryStateFilter, discoverySearch],
        queryFn: () =>
            fetchOpsDiscoveryCategories({
                site_key: selectedSiteKey || undefined,
                state: discoveryStateFilter,
                q: discoverySearch || undefined,
                limit: 200,
                offset: 0,
            }),
        enabled: !!selectedSiteKey,
        refetchInterval: (query) => (query.state.error ? false : pollMs('ops.discovery_ms', 30000)),
    });

    const patchFromEvent = (event: OpsEvent) => {
        if (event.type === 'queue.updated') {
            queryClient.setQueryData(['ops-overview'], (prev: any) => {
                if (!prev) return prev;
                return { ...prev, queue: event.payload };
            });
            return;
        }

        if (event.type === 'worker.heartbeat') {
            queryClient.setQueryData(['ops-overview'], (prev: any) => {
                if (!prev) return prev;
                const workers = Array.isArray(prev?.workers?.items) ? [...prev.workers.items] : [];
                const idx = workers.findIndex((w: any) => `${w.hostname}:${w.pid}` === event.payload.worker_id);
                if (idx >= 0) {
                    workers[idx] = {
                        ...workers[idx],
                        status: event.payload.status,
                        concurrent_tasks: event.payload.concurrency,
                        ram_usage_pct: event.payload.ram_pct,
                        active_tasks: event.payload.active_tasks || workers[idx]?.active_tasks || [],
                    };
                } else {
                    workers.push({
                        hostname: String(event.payload.worker_id || '').split(':')[0],
                        pid: Number(String(event.payload.worker_id || '').split(':')[1] || 0),
                        status: event.payload.status,
                        concurrent_tasks: event.payload.concurrency,
                        ram_usage_pct: event.payload.ram_pct,
                        active_tasks: event.payload.active_tasks || [],
                    });
                }
                return { ...prev, workers: { online: workers.length, items: workers } };
            });
            return;
        }

        if (event.type === 'run.status_changed') {
            const runId = event.payload.run_id;
            queryClient.setQueryData(['ops-runs-active'], (prev: any) => {
                if (!prev?.items) return prev;
                const items = [...prev.items];
                const idx = items.findIndex((r: any) => r.run_id === runId);
                if (idx >= 0) {
                    items[idx] = { ...items[idx], status: event.payload.to, updated_at: event.payload.ts };
                } else if (event.payload.to === 'queued' || event.payload.to === 'running') {
                    items.unshift({
                        run_id: runId,
                        source_id: event.payload.source_id,
                        site_key: event.payload.site_key,
                        status: event.payload.to,
                        created_at: event.payload.ts,
                        updated_at: event.payload.ts,
                    });
                }
                return { ...prev, items: items.filter((r: any) => ['queued', 'running'].includes(r.status)) };
            });

            if (selectedSiteRef.current && event.payload.site_key === selectedSiteRef.current) {
                queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteRef.current] });
            }
            if (selectedRunRef.current === runId) {
                queryClient.setQueryData(['ops-run-details', runId], (prev: any) => {
                    if (!prev?.item) return prev;
                    return {
                        ...prev,
                        item: {
                            ...prev.item,
                            run_status: event.payload.to,
                            updated_at: event.payload.ts,
                            timeline: [...(prev.item.timeline || []), { status: event.payload.to, at: event.payload.ts }],
                        },
                    };
                });
            }
            return;
        }

        if (event.type === 'run.log_chunk') {
            const runId = event.payload.run_id;
            queryClient.setQueryData(['ops-run-details', runId], (prev: any) => {
                if (!prev?.item) return prev;
                const oldLogs = prev.item.logs || '';
                const chunk = event.payload.chunk || '';
                if (!chunk || oldLogs.endsWith(chunk)) return prev;
                const nextLogs = `${oldLogs}${oldLogs ? '\n' : ''}${chunk}`.slice(-120000);
                return {
                    ...prev,
                    item: {
                        ...prev.item,
                        logs: nextLogs,
                        logs_meta: {
                            chars: nextLogs.length,
                            lines: nextLogs ? nextLogs.split(/\r?\n/).length : 0,
                        },
                    },
                };
            });
            return;
        }

        if (event.type === 'discovery.updated') {
            queryClient.setQueryData(['ops-sites'], (prev: any) => {
                if (!prev?.items) return prev;
                return {
                    ...prev,
                    items: prev.items.map((site: any) =>
                        site.site_key === event.payload.site_key
                            ? {
                                ...site,
                                counters: {
                                    ...site.counters,
                                    discovered_new: event.payload.new_count,
                                    discovered_promoted: event.payload.promoted_count,
                                },
                            }
                            : site,
                    ),
                };
            });

            if (selectedSiteRef.current === event.payload.site_key) {
                queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteRef.current] });
                queryClient.invalidateQueries({ queryKey: ['ops-discovery', selectedSiteRef.current] });
            }
            return;
        }

        if (event.type === 'ops.settings.updated') {
            queryClient.invalidateQueries({ queryKey: ['ops-runtime-settings'] });
            return;
        }

        if (event.type === 'ops.snapshot.updated') {
            const block = String(event.payload.block || '');
            if (block === 'overview') {
                queryClient.invalidateQueries({ queryKey: ['ops-overview'] });
            } else if (block === 'scheduler_stats') {
                queryClient.invalidateQueries({ queryKey: ['ops-scheduler-stats'] });
            } else if (block === 'items_trend') {
                queryClient.invalidateQueries({ queryKey: ['ops-items-trend'] });
            } else if (block === 'tasks_trend') {
                queryClient.invalidateQueries({ queryKey: ['ops-tasks-trend'] });
            }
        }
    };

    useEffect(() => {
        let source: EventSource | null = null;
        let closed = false;

        const cleanupTimer = () => {
            if (reconnectTimerRef.current) {
                window.clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
        };

        const connect = () => {
            cleanupTimer();
            setStreamState('connecting');

            try {
                source = new EventSource(getOpsStreamUrl());
            } catch (e) {
                setStreamState('disconnected');
                setStreamError(e instanceof Error ? e.message : 'Failed to initialize event stream');
                return;
            }

            source.onopen = () => {
                retryDelayRef.current = 1000;
                setStreamState('connected');
                setStreamError(null);
            };

            const handleEvent = (type: string) => (evt: MessageEvent) => {
                try {
                    const payload = evt.data ? JSON.parse(evt.data) : {};
                    patchFromEvent({ type, payload });
                } catch {
                    // Ignore malformed SSE event payloads.
                }
            };

            source.addEventListener('queue.updated', handleEvent('queue.updated'));
            source.addEventListener('run.status_changed', handleEvent('run.status_changed'));
            source.addEventListener('run.log_chunk', handleEvent('run.log_chunk'));
            source.addEventListener('worker.heartbeat', handleEvent('worker.heartbeat'));
            source.addEventListener('discovery.updated', handleEvent('discovery.updated'));
            source.addEventListener('ops.settings.updated', handleEvent('ops.settings.updated'));
            source.addEventListener('ops.snapshot.updated', handleEvent('ops.snapshot.updated'));

            source.onerror = () => {
                if (closed) return;
                source?.close();
                source = null;
                setStreamState('disconnected');
                setStreamError('Live stream disconnected. Reconnecting...');

                const delay = retryDelayRef.current;
                retryDelayRef.current = Math.min(MAX_BACKOFF_MS, Math.floor(delay * 1.7));

                reconnectTimerRef.current = window.setTimeout(() => {
                    if (!closed) {
                        if (selectedSiteRef.current) {
                            queryClient.invalidateQueries({ queryKey: ['ops-overview'] });
                            queryClient.invalidateQueries({ queryKey: ['ops-sites'] });
                            queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteRef.current] });
                        }
                        connect();
                    }
                }, delay);
            };
        };

        connect();

        return () => {
            closed = true;
            cleanupTimer();
            source?.close();
        };
    }, [queryClient]);

    const promoteMutation = useMutation({
        mutationFn: (ids: number[]) => promoteOpsDiscovery(ids),
        onSuccess: () => {
            if (selectedSiteKey) {
                queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
                queryClient.invalidateQueries({ queryKey: ['ops-discovery', selectedSiteKey] });
            }
            queryClient.invalidateQueries({ queryKey: ['ops-sites'] });
            queryClient.invalidateQueries({ queryKey: ['ops-overview'] });
        },
    });

    const rejectMutation = useMutation({
        mutationFn: (ids: number[]) => rejectOpsDiscovery(ids),
        onSuccess: () => {
            if (selectedSiteKey) {
                queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
                queryClient.invalidateQueries({ queryKey: ['ops-discovery', selectedSiteKey] });
            }
            queryClient.invalidateQueries({ queryKey: ['ops-sites'] });
        },
    });

    const reactivateMutation = useMutation({
        mutationFn: (ids: number[]) => reactivateOpsDiscovery(ids),
        onSuccess: () => {
            if (selectedSiteKey) {
                queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
                queryClient.invalidateQueries({ queryKey: ['ops-discovery', selectedSiteKey] });
            }
            queryClient.invalidateQueries({ queryKey: ['ops-sites'] });
        },
    });

    const bulkUpdateMutation = useMutation({
        mutationFn: (payload: { source_ids: number[]; priority?: number; refresh_interval_hours?: number; is_active?: boolean }) =>
            bulkUpdateOpsSources(payload),
        onSuccess: () => {
            if (selectedSiteKey) {
                queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
            }
            queryClient.invalidateQueries({ queryKey: ['ops-sites'] });
        },
    });

    const retryRunMutation = useMutation({
        mutationFn: (runId: number) => retryOpsRun(runId),
        onSuccess: () => {
            if (selectedSiteKey) queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
            queryClient.invalidateQueries({ queryKey: ['ops-runs-active'] });
            queryClient.invalidateQueries({ queryKey: ['ops-overview'] });
        },
    });

    const runNowMutation = useMutation({
        mutationFn: ({ sourceId, strategy }: { sourceId: number; strategy?: string }) => forceRunSource(sourceId, strategy || 'deep'),
        onSuccess: () => {
            if (selectedSiteKey) queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
            queryClient.invalidateQueries({ queryKey: ['ops-runs-active'] });
        },
    });

    const runSiteDiscoveryMutation = useMutation({
        mutationFn: (siteKey: string) => runOpsSiteDiscovery(siteKey),
        onSuccess: () => {
            if (selectedSiteKey) queryClient.invalidateQueries({ queryKey: ['ops-pipeline', selectedSiteKey] });
            queryClient.invalidateQueries({ queryKey: ['ops-runs-active'] });
            queryClient.invalidateQueries({ queryKey: ['ops-sites'] });
            queryClient.invalidateQueries({ queryKey: ['ops-overview'] });
        },
    });

    const anyPendingAction = useMemo(
        () =>
            promoteMutation.isPending ||
            rejectMutation.isPending ||
            reactivateMutation.isPending ||
            bulkUpdateMutation.isPending ||
            retryRunMutation.isPending ||
            runNowMutation.isPending ||
            runSiteDiscoveryMutation.isPending,
        [
            promoteMutation.isPending,
            rejectMutation.isPending,
            reactivateMutation.isPending,
            bulkUpdateMutation.isPending,
            retryRunMutation.isPending,
            runNowMutation.isPending,
            runSiteDiscoveryMutation.isPending,
        ],
    );

    return {
        selectedSiteKey,
        setSelectedSiteKey,
        selectedRunId,
        setSelectedRunId,
        streamState,
        streamError,
        discoveryStateFilter,
        setDiscoveryStateFilter,
        discoverySearch,
        setDiscoverySearch,
        overview,
        sites,
        pipeline,
        activeRuns,
        runDetails,
        discovery,
        promoteCategories: promoteMutation.mutateAsync,
        rejectCategories: rejectMutation.mutateAsync,
        reactivateCategories: reactivateMutation.mutateAsync,
        bulkUpdateSources: bulkUpdateMutation.mutateAsync,
        retryRun: retryRunMutation.mutateAsync,
        runSourceNow: runNowMutation.mutateAsync,
        runSiteDiscovery: runSiteDiscoveryMutation.mutateAsync,
        anyPendingAction,
    };
}
