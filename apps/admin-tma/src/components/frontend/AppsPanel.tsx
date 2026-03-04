"use client";

import { useState } from 'react';
import { Modal } from './Modal';
import { InfoHint } from './InfoHint';

interface AppsPanelProps {
  apps: any[];
  releases: any[];
  onCreate: (payload: { key: string; name: string; is_active?: boolean }) => Promise<any>;
  onDelete: (id: number) => Promise<any>;
  onCreateRelease: (payload: Record<string, unknown>) => Promise<any>;
  onValidateRelease: (id: number) => Promise<any>;
  onDeleteRelease: (id: number) => Promise<any>;
  isBusy?: boolean;
  isReleaseBusy?: boolean;
}

export function AppsPanel({
  apps,
  releases,
  onCreate,
  onDelete,
  onCreateRelease,
  onValidateRelease,
  onDeleteRelease,
  isBusy,
  isReleaseBusy,
}: AppsPanelProps) {
  const [releaseValidateUi, setReleaseValidateUi] = useState<Record<number, { status: 'idle' | 'loading' | 'success' | 'error'; message?: string }>>({});
  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isReleaseCreateOpen, setIsReleaseCreateOpen] = useState(false);
  const [releaseVersion, setReleaseVersion] = useState('');
  const [releaseTargetUrl, setReleaseTargetUrl] = useState('https://');
  const [selectedReleaseId, setSelectedReleaseId] = useState<number | null>(null);

  const selectedApp = apps?.find((item) => item.id === selectedAppId) ?? null;
  const appReleases = selectedApp
    ? (releases || []).filter((item) => item.app_id === selectedApp.id)
    : [];
  const selectedRelease = selectedReleaseId ? (releases || []).find((r: any) => r.id === selectedReleaseId) ?? null : null;
  const selectedReleaseValidateUi = selectedRelease ? releaseValidateUi[selectedRelease.id] : undefined;

  const extractBackendError = (err: unknown) => {
    const anyErr = err as any;
    const status = anyErr?.response?.status;
    const detail = anyErr?.response?.data?.detail;
    const message = anyErr?.message;
    const fallback = detail || message || 'Unknown error';
    return status ? `HTTP ${status}: ${fallback}` : String(fallback);
  };

  const validateReleaseUi = async (releaseId: number) => {
    setReleaseValidateUi((prev) => ({ ...prev, [releaseId]: { status: 'loading' } }));
    try {
      const result = await onValidateRelease(releaseId);
      const ok = Boolean(result?.ok);
      if (ok) {
        const statusCode = typeof result?.status_code === 'number' ? result.status_code : undefined;
        setReleaseValidateUi((prev) => ({
          ...prev,
          [releaseId]: { status: 'success', message: statusCode ? `OK (status ${statusCode})` : 'OK' },
        }));
      } else {
        const reason = result?.reason ? String(result.reason) : 'Validation failed';
        const statusCode = typeof result?.status_code === 'number' ? ` (status ${result.status_code})` : '';
        setReleaseValidateUi((prev) => ({
          ...prev,
          [releaseId]: { status: 'error', message: `${reason}${statusCode}`.trim() },
        }));
      }
    } catch (err) {
      setReleaseValidateUi((prev) => ({
        ...prev,
        [releaseId]: { status: 'error', message: extractBackendError(err) },
      }));
    }
  };

  const createReleaseForSelectedApp = async () => {
    if (!selectedApp) return;
    if (!releaseTargetUrl.startsWith('https://')) {
      alert('target_url must start with https://');
      return;
    }
    await onCreateRelease({
      app_id: selectedApp.id,
      version: releaseVersion,
      target_url: releaseTargetUrl,
      status: 'draft',
      flags: {},
    });
    setReleaseVersion('');
    setReleaseTargetUrl('https://');
    setIsReleaseCreateOpen(false);
  };

  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold">Apps</h3>
          <button
            className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-white/30 text-xs text-white/80 hover:border-white/60 hover:text-white"
            onClick={() => setIsHelpOpen(true)}
            aria-label="Apps help"
          >
            ?
          </button>
        </div>
        <button
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold disabled:opacity-60"
          disabled={isBusy}
          onClick={() => setIsCreateOpen(true)}
        >
          Add new
        </button>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {apps?.map((app) => (
          <button
            key={app.id}
            className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
              selectedAppId === app.id
                ? 'border-cyan-400/70 bg-cyan-300/10'
                : 'border-white/10 bg-black/20 hover:border-white/30'
            }`}
            onClick={() => setSelectedAppId(app.id)}
          >
            <div className="font-semibold">#{app.id} {app.key}</div>
            <div className="text-xs text-white/70">{app.name}</div>
          </button>
        ))}
      </div>

      {!apps?.length && (
        <div className="rounded-lg bg-black/20 px-3 py-2 text-sm text-white/70">
          No apps yet.
        </div>
      )}

      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)}>
        <div className="w-full max-w-lg text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Add New App</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsCreateOpen(false)}>Close</button>
          </div>
          <p className="mb-3 text-xs text-white/70">
            Создайте логическое приложение, к которому будут привязываться релизы и правила маршрутизации.
          </p>
          <div className="space-y-2">
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                App Key
                <InfoHint text="Технический уникальный идентификатор приложения. Должен быть стабильным, в lowercase, без пробелов и спецсимволов. Примеры: product, landing, campaign_blackfriday." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="product" value={key} onChange={(e) => setKey(e.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                App Name
                <InfoHint text="Человекочитаемое имя для интерфейса админки. Можно менять без влияния на маршрутизацию. Примеры: Main Product, Investor Landing, Black Friday Promo." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="Main Product" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <button
              className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold disabled:opacity-60"
              disabled={isBusy || !key || !name}
              onClick={() =>
                onCreate({ key, name, is_active: true }).then(() => {
                  setKey('');
                  setName('');
                  setIsCreateOpen(false);
                })
              }
            >
              Create app
            </button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)}>
        <div className="w-full max-w-2xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Apps Guide</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsHelpOpen(false)}>Close</button>
          </div>
          <div className="rounded-xl border border-cyan-300/20 bg-cyan-400/5 p-3 mb-3">
            <div className="font-semibold mb-1">Что это</div>
            <div className="text-white/80">`App` - логическая группа фронтендов. Внутри одного app вы храните его релизы и используете их в правилах.</div>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="font-semibold mb-1">Как пользоваться</div>
              <div className="text-white/80 text-xs">1) Нажмите `Add new`.</div>
              <div className="text-white/80 text-xs">2) Укажите стабильный `key` (slug).</div>
              <div className="text-white/80 text-xs">3) Откройте карточку app и управляйте релизами внутри нее.</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="font-semibold mb-1">Примеры</div>
              <div className="text-white/80 text-xs">`key: product`, `name: Main Product`</div>
              <div className="text-white/80 text-xs">`key: landing`, `name: Marketing Landing`</div>
              <div className="text-white/80 text-xs">`key: investors`, `name: Investor Page`</div>
            </div>
          </div>
        </div>
      </Modal>

      <Modal isOpen={!!selectedApp} onClose={() => setSelectedAppId(null)}>
        {selectedApp && (
          <div className="w-full max-w-3xl text-sm">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-white/60">App Card</div>
              <button className="text-white/70 hover:text-white" onClick={() => setSelectedAppId(null)}>Close</button>
            </div>
            <div className="rounded-lg border border-white/20 bg-black/20 p-3 text-sm">
              <div>ID: {selectedApp.id}</div>
              <div>Key: {selectedApp.key}</div>
              <div>Name: {selectedApp.name}</div>
              <div>Status: {selectedApp.is_active ? 'active' : 'inactive'}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold"
                  onClick={() => setIsReleaseCreateOpen(true)}
                >
                  Add release
                </button>
                <button
                  className="rounded-lg bg-red-500/20 px-3 py-1.5 text-red-300 hover:bg-red-500/30"
                  onClick={() => onDelete(selectedApp.id).then(() => setSelectedAppId(null))}
                >
                  Delete app
                </button>
              </div>

              <div className="mt-4 border-t border-white/10 pt-4">
                <div className="mb-2 text-xs uppercase tracking-wide text-white/60">Releases in this app</div>
                <div className="space-y-2 max-h-80 overflow-auto pr-1">
                  {appReleases.length === 0 && (
                    <div className="rounded-lg bg-black/20 px-3 py-2 text-white/70">No releases in this app.</div>
                  )}
                  {appReleases.map((rel: any) => (
                    <button
                      key={rel.id}
                      type="button"
                      className="w-full rounded-lg bg-black/20 px-3 py-2 text-left hover:bg-white/5"
                      onClick={() => setSelectedReleaseId(rel.id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold">#{rel.id} {rel.version}</div>
                        <div className="text-xs text-white/60">{rel.status}/{rel.health_status}</div>
                      </div>
                      <div className="mt-1 text-xs text-white/60 break-all">{rel.target_url}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={isReleaseCreateOpen} onClose={() => setIsReleaseCreateOpen(false)}>
        <div className="w-full max-w-xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Add New Release</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsReleaseCreateOpen(false)}>Close</button>
          </div>
          <p className="mb-3 text-xs text-white/70">
            Добавление релиза для приложения: <span className="font-semibold">{selectedApp?.key ?? 'n/a'}</span>.
          </p>
          <div className="grid md:grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Version
                <InfoHint text="Уникальная версия внутри текущего app. Пример: v2026-02-24-main." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="v2026-02-24-main" value={releaseVersion} onChange={(e) => setReleaseVersion(e.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Target URL
                <InfoHint text="Публичный HTTPS URL фронта. Домен должен быть в Allowed Hosts." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="https://product.giftyai.ru" value={releaseTargetUrl} onChange={(e) => setReleaseTargetUrl(e.target.value)} />
            </label>
            <div className="md:col-span-2">
              <button
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold disabled:opacity-60"
                disabled={isReleaseBusy || !selectedApp || !releaseVersion || !releaseTargetUrl}
                onClick={createReleaseForSelectedApp}
              >
                Create release
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal isOpen={!!selectedRelease} onClose={() => setSelectedReleaseId(null)}>
        {selectedRelease && (
          <div className="w-full max-w-2xl text-sm">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-white/60">Release Card</div>
              <button className="text-white/70 hover:text-white" onClick={() => setSelectedReleaseId(null)}>Close</button>
            </div>
            <div className="rounded-lg border border-white/20 bg-black/20 p-3 text-sm">
              <div>ID: {selectedRelease.id}</div>
              <div>App ID: {selectedRelease.app_id}</div>
              <div>Version: {selectedRelease.version}</div>
              <div>Status: {selectedRelease.status}</div>
              <div>Health: {selectedRelease.health_status}</div>
              <div className="mt-1 text-xs text-white/70 break-all">{selectedRelease.target_url}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className={[
                    'rounded-lg px-3 py-1.5 text-sm font-semibold',
                    selectedReleaseValidateUi?.status === 'success'
                      ? 'bg-emerald-600 text-white'
                      : selectedReleaseValidateUi?.status === 'error'
                        ? 'bg-red-600 text-white'
                        : 'bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30',
                  ].join(' ')}
                  onClick={() => validateReleaseUi(selectedRelease.id)}
                  disabled={isReleaseBusy || selectedReleaseValidateUi?.status === 'loading'}
                >
                  <span className="inline-flex items-center gap-2">
                    {selectedReleaseValidateUi?.status === 'loading' && (
                      <span className="inline-block h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                    )}
                    {selectedReleaseValidateUi?.status === 'loading' ? 'Validating…' : 'Validate'}
                  </span>
                </button>
                <button
                  className="rounded-lg bg-red-500/20 px-3 py-1.5 text-red-300 hover:bg-red-500/30"
                  onClick={() => onDeleteRelease(selectedRelease.id).then(() => setSelectedReleaseId(null))}
                  disabled={isReleaseBusy}
                >
                  Delete release
                </button>
              </div>

              {selectedReleaseValidateUi?.status === 'error' && (
                <div className="mt-3 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                  Validation error: {selectedReleaseValidateUi.message ?? 'Unknown error'}
                </div>
              )}
              {selectedReleaseValidateUi?.status === 'success' && (
                <div className="mt-3 rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
                  Validation passed{selectedReleaseValidateUi.message ? `: ${selectedReleaseValidateUi.message}` : ''}.
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </section>
  );
}
