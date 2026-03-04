"use client";

import { useMemo, useState } from 'react';
import { InfoHint } from './InfoHint';
import { NiceSelect } from './NiceSelect';

interface RuntimeStatePanelProps {
  runtimeState: any;
  profiles: any[];
  releases: any[];
  onUpdateRuntimeState: (payload: Record<string, unknown>) => Promise<any>;
  onPublish: (payload: Record<string, unknown>) => Promise<any>;
  onRollback: () => Promise<any>;
}

export function RuntimeStatePanel({ runtimeState, profiles, releases, onUpdateRuntimeState, onPublish, onRollback }: RuntimeStatePanelProps) {
  const [activeProfileId, setActiveProfileId] = useState<number | ''>(runtimeState?.active_profile_id || '');
  const [fallbackReleaseId, setFallbackReleaseId] = useState<number | ''>(runtimeState?.fallback_release_id || '');
  const [stickyEnabled, setStickyEnabled] = useState(runtimeState?.sticky_enabled ?? true);
  const [stickyTtl, setStickyTtl] = useState(runtimeState?.sticky_ttl_seconds ?? 1800);
  const [cacheTtl, setCacheTtl] = useState(runtimeState?.cache_ttl_seconds ?? 15);

  const current = useMemo(() => runtimeState || {}, [runtimeState]);
  const profileById = useMemo(() => new Map((profiles || []).map((p: any) => [p.id, p])), [profiles]);
  const releaseById = useMemo(() => new Map((releases || []).map((r: any) => [r.id, r])), [releases]);

  const currentProfile = current.active_profile_id ? profileById.get(current.active_profile_id) : null;
  const currentFallback = current.fallback_release_id ? releaseById.get(current.fallback_release_id) : null;
  const currentStickyEnabled = Boolean(current.sticky_enabled);
  const currentStickyTtl = typeof current.sticky_ttl_seconds === 'number' ? current.sticky_ttl_seconds : null;
  const currentCacheTtl = typeof current.cache_ttl_seconds === 'number' ? current.cache_ttl_seconds : null;

  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <h3 className="text-sm font-bold mb-3">Runtime State / Publish</h3>
      <p className="mb-3 text-xs text-white/70">
        Настройка текущего runtime-поведения роутера: активный профиль, глобальный fallback и параметры sticky/cache.
      </p>
      <div className="mb-4 rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-xs uppercase tracking-wide text-white/60">Current Runtime</div>
          <div className={`rounded-full px-2 py-0.5 text-[11px] ${currentStickyEnabled ? 'bg-emerald-500/15 text-emerald-200' : 'bg-white/10 text-white/70'}`}>
            {currentStickyEnabled ? 'sticky on' : 'sticky off'}
          </div>
        </div>
        <div className="grid gap-2 md:grid-cols-4">
          <div className="rounded-lg border border-white/10 bg-white/5 p-2">
            <div className="text-[11px] uppercase tracking-wide text-white/60">Active Profile</div>
            <div className={`mt-0.5 text-sm ${currentProfile ? 'text-white' : 'text-amber-200'}`}>
              {currentProfile ? `${currentProfile.key}` : 'not set'}
            </div>
            {currentProfile?.name && <div className="text-xs text-white/60">{currentProfile.name}</div>}
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-2">
            <div className="text-[11px] uppercase tracking-wide text-white/60">Fallback Release</div>
            <div className={`mt-0.5 text-sm ${currentFallback ? 'text-white' : 'text-amber-200'}`}>
              {currentFallback ? `#${currentFallback.id} ${currentFallback.version}` : 'not set'}
            </div>
            {currentFallback?.target_url && <div className="text-xs text-white/60 break-all">{currentFallback.target_url}</div>}
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-2">
            <div className="text-[11px] uppercase tracking-wide text-white/60">Sticky TTL</div>
            <div className="mt-0.5 text-sm text-white">{currentStickyTtl ?? 'n/a'} <span className="text-xs text-white/60">sec</span></div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-2">
            <div className="text-[11px] uppercase tracking-wide text-white/60">Cache TTL</div>
            <div className="mt-0.5 text-sm text-white">{currentCacheTtl ?? 'n/a'} <span className="text-xs text-white/60">sec</span></div>
          </div>
        </div>
      </div>
      <div className="grid md:grid-cols-5 gap-2 mb-3">
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
            Active Profile
            <InfoHint text="Профиль правил, который сейчас используется для матчей запросов. Меняется через Publish." />
          </span>
          <NiceSelect
            value={activeProfileId}
            onChange={(v) => setActiveProfileId(v === "" ? "" : Number(v))}
            placeholder="Select profile"
            options={(profiles || []).map((p: any) => ({ value: p.id as number, label: p.key, hint: p.name }))}
          />
        </label>
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
            Fallback Release
            <InfoHint text="Глобальный запасной релиз. Используется, если нет совпавшего правила или целевой релиз недоступен." />
          </span>
          <NiceSelect
            value={fallbackReleaseId}
            onChange={(v) => setFallbackReleaseId(v === "" ? "" : Number(v))}
            placeholder="Select fallback release"
            options={(releases || []).map((r: any) => ({
              value: r.id as number,
              label: `#${r.id} ${r.version}`,
              hint: r.target_url,
            }))}
          />
        </label>
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
            Sticky TTL (sec)
            <InfoHint text="Время жизни cookie закрепления пользователя на release_id. Обычно 1800 секунд (30 минут)." />
          </span>
          <input type="number" className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" value={stickyTtl} onChange={(e) => setStickyTtl(Number(e.target.value))} />
        </label>
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
            Cache TTL (sec)
            <InfoHint text="TTL кэша ответа frontend-config на backend стороне. Меньше значение = быстрее применение изменений, но больше нагрузка." />
          </span>
          <input type="number" className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" value={cacheTtl} onChange={(e) => setCacheTtl(Number(e.target.value))} />
        </label>
        <label className="flex items-end pb-2">
          <span className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={stickyEnabled} onChange={(e) => setStickyEnabled(e.target.checked)} />
            <span className="flex items-center gap-1">
              Sticky Enabled
              <InfoHint text="Если включено, роутер сохраняет release в cookie и временно держит пользователя на этой версии." />
            </span>
          </span>
        </label>
      </div>
      <div className="flex gap-2">
        <button
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold"
          onClick={() => onUpdateRuntimeState({
            active_profile_id: Number(activeProfileId),
            fallback_release_id: Number(fallbackReleaseId),
            sticky_enabled: stickyEnabled,
            sticky_ttl_seconds: stickyTtl,
            cache_ttl_seconds: cacheTtl,
          })}
        >
          Save Runtime
        </button>
        <button
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold"
          onClick={() => {
            if (!activeProfileId || !fallbackReleaseId) {
              alert('Publish requires active_profile_id and fallback_release_id');
              return;
            }
            onPublish({
              active_profile_id: Number(activeProfileId),
              fallback_release_id: Number(fallbackReleaseId),
              sticky_enabled: stickyEnabled,
              sticky_ttl_seconds: stickyTtl,
              cache_ttl_seconds: cacheTtl,
            });
          }}
        >
          Publish
        </button>
        <button className="rounded-lg bg-orange-600 px-3 py-2 text-sm font-semibold" onClick={() => onRollback()}>Rollback</button>
      </div>
    </section>
  );
}
