"use client";

import { AppsPanel } from './AppsPanel';
import { ProfilesRulesPanel } from './ProfilesRulesPanel';
import { RuntimeStatePanel } from './RuntimeStatePanel';
import { AllowedHostsPanel } from './AllowedHostsPanel';
import { AuditLogPanel } from './AuditLogPanel';
import { useFrontendRoutingData } from '@/hooks/useFrontendRouting';
import { useApiErrorToast } from '@/hooks/useApiErrorToast';

export function FrontendRoutingView() {
  const {
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
    createApp,
    deleteApp,
    createRelease,
    validateRelease,
    deleteRelease,
    createProfile,
    createRule,
    deleteRule,
    updateRuntimeState,
    publish,
    rollback,
    createAllowedHost,
    deleteAllowedHost,
  } = useFrontendRoutingData();

  useApiErrorToast({
    id: "frontend-control-api",
    title: "Frontend Control API временно недоступен",
    errors: [apps.error, releases.error, profiles.error, rules.error, runtimeState.error, allowedHosts.error, auditLog.error],
    enabled: true,
    ttlMs: 10000,
  });

  return (
    <div className="space-y-4 px-4 pb-8">
      <AppsPanel
        apps={appsData}
        releases={releasesData}
        onCreate={(payload) => createApp.mutateAsync(payload)}
        onDelete={(id) => deleteApp.mutateAsync(id)}
        onCreateRelease={(payload) => createRelease.mutateAsync(payload)}
        onValidateRelease={(id) => validateRelease.mutateAsync(id)}
        onDeleteRelease={(id) => deleteRelease.mutateAsync(id)}
        isBusy={createApp.isPending || deleteApp.isPending}
        isReleaseBusy={createRelease.isPending || validateRelease.isPending || deleteRelease.isPending}
      />

      <ProfilesRulesPanel
        profiles={profilesData}
        rules={rulesData}
        releases={releasesData}
        onCreateProfile={(payload) => createProfile.mutateAsync(payload)}
        onCreateRule={(payload) => createRule.mutateAsync(payload)}
        onDeleteRule={(id) => deleteRule.mutateAsync(id)}
      />

      <RuntimeStatePanel
        runtimeState={runtimeState.data}
        profiles={profilesData}
        releases={releasesData}
        onUpdateRuntimeState={(payload) => updateRuntimeState.mutateAsync(payload)}
        onPublish={(payload) => publish.mutateAsync(payload)}
        onRollback={() => rollback.mutateAsync({})}
      />

      <AllowedHostsPanel
        hosts={allowedHostsData}
        onCreate={(payload) => createAllowedHost.mutateAsync(payload)}
        onDelete={(id) => deleteAllowedHost.mutateAsync(id)}
      />

      <AuditLogPanel items={auditLogData} />
    </div>
  );
}
