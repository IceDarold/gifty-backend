"use client";

import { useState } from 'react';
import { Modal } from './Modal';
import { InfoHint } from './InfoHint';
import { NiceSelect } from './NiceSelect';

interface ReleasesPanelProps {
  releases: any[];
  apps: any[];
  onCreate: (payload: Record<string, unknown>) => Promise<any>;
  onValidate: (id: number) => Promise<any>;
  onDelete: (id: number) => Promise<any>;
  isBusy?: boolean;
}

export function ReleasesPanel({ releases, apps, onCreate, onValidate, onDelete, isBusy }: ReleasesPanelProps) {
  const [appId, setAppId] = useState<number | ''>('');
  const [version, setVersion] = useState('');
  const [targetUrl, setTargetUrl] = useState('https://');
  const [selectedReleaseId, setSelectedReleaseId] = useState<number | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  const selectedRelease = releases?.find((item) => item.id === selectedReleaseId) ?? null;
  const appsById = new Map((apps || []).map((a) => [a.id, a]));

  const create = async () => {
    if (!targetUrl.startsWith('https://')) {
      alert('target_url must start with https://');
      return;
    }
    await onCreate({ app_id: Number(appId), version, target_url: targetUrl, status: 'draft', flags: {} });
    setVersion('');
    setTargetUrl('https://');
  };

  if (selectedRelease) {
    return (
      <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
        <div className="mb-3 flex items-center justify-between">
          <button className="text-sm text-cyan-300 hover:text-cyan-200" onClick={() => setSelectedReleaseId(null)}>
            ← Back
          </button>
          <div className="text-xs uppercase tracking-wide text-white/60">Release Card</div>
        </div>
        <div className="rounded-lg border border-white/20 bg-black/20 p-3 text-sm">
          <div>ID: {selectedRelease.id}</div>
          <div>App: {appsById.get(selectedRelease.app_id)?.key ?? selectedRelease.app_id}</div>
          <div>Version: {selectedRelease.version}</div>
          <div>Status: {selectedRelease.status}</div>
          <div>Health: {selectedRelease.health_status}</div>
          <div className="text-xs text-white/70 break-all mt-1">{selectedRelease.target_url}</div>
          <div className="mt-3 flex gap-3">
            <button
              className="rounded-lg bg-cyan-500/20 px-3 py-1.5 text-cyan-300 hover:bg-cyan-500/30"
              onClick={() => onValidate(selectedRelease.id)}
            >
              Validate
            </button>
            <button
              className="rounded-lg bg-red-500/20 px-3 py-1.5 text-red-300 hover:bg-red-500/30"
              onClick={() => onDelete(selectedRelease.id).then(() => setSelectedReleaseId(null))}
            >
              Delete
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold">Releases</h3>
          <button
            className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-white/30 text-xs text-white/80 hover:border-white/60 hover:text-white"
            onClick={() => setIsHelpOpen(true)}
            aria-label="Releases help"
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
        {releases?.map((rel) => (
          <button
            key={rel.id}
            className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
              selectedReleaseId === rel.id
                ? 'border-cyan-400/70 bg-cyan-300/10'
                : 'border-white/10 bg-black/20 hover:border-white/30'
            }`}
            onClick={() => setSelectedReleaseId(rel.id)}
          >
            <div className="font-semibold">#{rel.id} {rel.version}</div>
            <div className="text-xs text-white/70">
              app:{appsById.get(rel.app_id)?.key ?? rel.app_id} [{rel.status}/{rel.health_status}]
            </div>
          </button>
        ))}
      </div>

      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)}>
        <div className="w-full max-w-xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Add New Release</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsCreateOpen(false)}>Close</button>
          </div>
          <p className="mb-3 text-xs text-white/70">
            Добавьте конкретную версию фронта с целевым URL, которую можно валидировать и использовать в правилах.
          </p>
          <div className="grid md:grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                App
                <InfoHint text="Приложение-владелец релиза. Все правила этого релиза обычно логически относятся к выбранному app (например product или landing)." />
              </span>
              <NiceSelect
                value={appId}
                onChange={(v) => setAppId(v === "" ? "" : Number(v))}
                placeholder="Select app"
                options={(apps || []).map((a: any) => ({ value: a.id as number, label: a.key, hint: a.name }))}
              />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Version
                <InfoHint text="Уникальная версия внутри выбранного app. Удобно использовать схему с датой и short commit: v2026-02-24-abc123. Это поле будет видно в правилах и в runtime state." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="v2026-02-24-abc123" value={version} onChange={(e) => setVersion(e.target.value)} />
            </label>
            <label className="block md:col-span-2">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Target URL
                <InfoHint text="Публичный HTTPS URL фронтенда, куда роутер делает rewrite. Домен обязан быть в Allowed Hosts, иначе validate/publish не пройдут. Используйте production alias, а не защищенный preview URL." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="https://product.example.com" value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)} />
            </label>
            <div className="md:col-span-2">
              <button
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold disabled:opacity-60"
                disabled={isBusy || !appId || !version || !targetUrl}
                onClick={() => create().then(() => setIsCreateOpen(false))}
              >
                Create release
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)}>
        <div className="w-full max-w-2xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Releases Guide</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsHelpOpen(false)}>Close</button>
          </div>
          <div className="rounded-xl border border-cyan-300/20 bg-cyan-400/5 p-3 mb-3">
            <div className="font-semibold mb-1">Что это</div>
            <div className="text-white/80">`Release` - конкретная версия фронтенда с URL, на который роутер делает rewrite.</div>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="font-semibold mb-1">Как пользоваться</div>
              <div className="text-white/80 text-xs">1) Нажмите `Add new` и выберите `App`.</div>
              <div className="text-white/80 text-xs">2) Заполните `Version` (уникально в app).</div>
              <div className="text-white/80 text-xs">3) Укажите публичный `https://` target URL.</div>
              <div className="text-white/80 text-xs">4) Откройте карточку релиза и нажмите `Validate`.</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="font-semibold mb-1">Примеры</div>
              <div className="text-white/80 text-xs">`version: v2026-02-24-main`</div>
              <div className="text-white/80 text-xs">`target_url: https://product.giftyai.ru`</div>
              <div className="text-white/80 text-xs">или `https://giftyai-frontend.vercel.app` (без auth-экрана)</div>
            </div>
          </div>
        </div>
      </Modal>

      {!releases?.length && (
        <div className="rounded-lg bg-black/20 px-3 py-2 text-sm text-white/70">
          No releases yet.
        </div>
      )}
    </section>
  );
}
