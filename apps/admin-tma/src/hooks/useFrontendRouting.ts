import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createFrontendAllowedHost,
  createFrontendApp,
  createFrontendProfile,
  createFrontendRelease,
  createFrontendRule,
  deleteFrontendAllowedHost,
  deleteFrontendApp,
  deleteFrontendRelease,
  deleteFrontendRule,
  publishFrontendConfig,
  rollbackFrontendConfig,
  updateFrontendAllowedHost,
  updateFrontendApp,
  updateFrontendProfile,
  updateFrontendRelease,
  updateFrontendRule,
  updateFrontendRuntimeState,
  validateFrontendRelease,
} from '@/lib/api';
import { useAdminChannelQuery } from '@/hooks/useAdminStreamQuery';

const invalidateAll = (qc: ReturnType<typeof useQueryClient>) => {
  qc.invalidateQueries({ queryKey: ['frontend-apps'] });
  qc.invalidateQueries({ queryKey: ['frontend-releases'] });
  qc.invalidateQueries({ queryKey: ['frontend-profiles'] });
  qc.invalidateQueries({ queryKey: ['frontend-rules'] });
  qc.invalidateQueries({ queryKey: ['frontend-runtime-state'] });
  qc.invalidateQueries({ queryKey: ['frontend-allowed-hosts'] });
  qc.invalidateQueries({ queryKey: ['frontend-audit-log'] });
};

export function useFrontendRoutingData() {
  const qc = useQueryClient();

  const apps = useAdminChannelQuery<any>('frontend.apps');
  const releases = useAdminChannelQuery<any>('frontend.releases');
  const profiles = useAdminChannelQuery<any>('frontend.profiles');
  const rules = useAdminChannelQuery<any>('frontend.rules');
  const runtimeState = useAdminChannelQuery<any>('frontend.runtime_state');
  const allowedHosts = useAdminChannelQuery<any>('frontend.allowed_hosts');
  const auditLog = useAdminChannelQuery<any>('frontend.audit_log');

  // Backend returns {status, items} while UI expects arrays.
  const appsData = (apps.data as any)?.items ?? apps.data ?? [];
  const releasesData = (releases.data as any)?.items ?? releases.data ?? [];
  const profilesData = (profiles.data as any)?.items ?? profiles.data ?? [];
  const rulesData = (rules.data as any)?.items ?? rules.data ?? [];
  const allowedHostsData = (allowedHosts.data as any)?.items ?? allowedHosts.data ?? [];
  const auditLogData = (auditLog.data as any)?.items ?? auditLog.data ?? [];

  return {
    apps,
    releases,
    profiles,
    rules,
    runtimeState,
    allowedHosts,
    auditLog,

    appsData,
    releasesData,
    profilesData,
    rulesData,
    allowedHostsData,
    auditLogData,

    createApp: useMutation({
      mutationFn: createFrontendApp,
      onSuccess: () => invalidateAll(qc),
    }),
    updateApp: useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) => updateFrontendApp(id, payload),
      onSuccess: () => invalidateAll(qc),
    }),
    deleteApp: useMutation({
      mutationFn: (id: number) => deleteFrontendApp(id),
      onSuccess: () => invalidateAll(qc),
    }),

    createRelease: useMutation({
      mutationFn: createFrontendRelease,
      onSuccess: () => invalidateAll(qc),
    }),
    updateRelease: useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) => updateFrontendRelease(id, payload),
      onSuccess: () => invalidateAll(qc),
    }),
    deleteRelease: useMutation({
      mutationFn: (id: number) => deleteFrontendRelease(id),
      onSuccess: () => invalidateAll(qc),
    }),
    validateRelease: useMutation({
      mutationFn: (id: number) => validateFrontendRelease(id),
      onSuccess: () => invalidateAll(qc),
    }),

    createProfile: useMutation({
      mutationFn: createFrontendProfile,
      onSuccess: () => invalidateAll(qc),
    }),
    updateProfile: useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) => updateFrontendProfile(id, payload),
      onSuccess: () => invalidateAll(qc),
    }),

    createRule: useMutation({
      mutationFn: createFrontendRule,
      onSuccess: () => invalidateAll(qc),
    }),
    updateRule: useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) => updateFrontendRule(id, payload),
      onSuccess: () => invalidateAll(qc),
    }),
    deleteRule: useMutation({
      mutationFn: (id: number) => deleteFrontendRule(id),
      onSuccess: () => invalidateAll(qc),
    }),

    updateRuntimeState: useMutation({
      mutationFn: updateFrontendRuntimeState,
      onSuccess: () => invalidateAll(qc),
    }),

    createAllowedHost: useMutation({
      mutationFn: createFrontendAllowedHost,
      onSuccess: () => invalidateAll(qc),
    }),
    updateAllowedHost: useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) => updateFrontendAllowedHost(id, payload),
      onSuccess: () => invalidateAll(qc),
    }),
    deleteAllowedHost: useMutation({
      mutationFn: (id: number) => deleteFrontendAllowedHost(id),
      onSuccess: () => invalidateAll(qc),
    }),

    publish: useMutation({
      mutationFn: publishFrontendConfig,
      onSuccess: () => invalidateAll(qc),
    }),
    rollback: useMutation({
      mutationFn: rollbackFrontendConfig,
      onSuccess: () => invalidateAll(qc),
    }),
  };
}
