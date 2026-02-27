"use client";

import { useMemo, useState } from 'react';
import { Modal } from './Modal';
import { InfoHint } from './InfoHint';
import { NiceSelect } from './NiceSelect';

interface ProfilesRulesPanelProps {
  profiles: any[];
  rules: any[];
  releases: any[];
  onCreateProfile: (payload: { key: string; name: string; is_active?: boolean }) => Promise<any>;
  onCreateRule: (payload: Record<string, unknown>) => Promise<any>;
  onDeleteRule: (id: number) => Promise<any>;
}

export function ProfilesRulesPanel({ profiles, rules, releases, onCreateProfile, onCreateRule, onDeleteRule }: ProfilesRulesPanelProps) {
  const [profileKey, setProfileKey] = useState('');
  const [profileName, setProfileName] = useState('');
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [modalPriority, setModalPriority] = useState(100);
  const [modalHostPattern, setModalHostPattern] = useState('*');
  const [modalPathPattern, setModalPathPattern] = useState('/*');
  const [modalQueryConditions, setModalQueryConditions] = useState('{}');
  const [modalTargetReleaseId, setModalTargetReleaseId] = useState<number | ''>('');
  const [isRuleCreateOpen, setIsRuleCreateOpen] = useState(false);
  const [isProfileCreateOpen, setIsProfileCreateOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  const notReadyTargets = useMemo(() => {
    const statusById = new Map((releases || []).map((r: any) => [r.id, r.status]));
    return (rules || []).filter((r: any) => !['ready', 'active'].includes(statusById.get(r.target_release_id)));
  }, [rules, releases]);
  const selectedProfile = profiles?.find((item) => item.id === selectedProfileId) ?? null;
  const profileById = new Map((profiles || []).map((p: any) => [p.id, p]));
  const selectedProfileRules = selectedProfile
    ? (rules || []).filter((rule: any) => rule.profile_id === selectedProfile.id)
    : [];

  const createRuleForSelectedProfile = async () => {
    if (!selectedProfile) return;

    let parsed: Record<string, string>;
    try {
      const obj = JSON.parse(modalQueryConditions || '{}');
      if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
        alert('query_conditions must be a JSON object');
        return;
      }
      parsed = Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, String(v)]));
    } catch {
      alert('query_conditions must be valid JSON object');
      return;
    }

    if (!modalTargetReleaseId) {
      alert('Select release');
      return;
    }

    await onCreateRule({
      profile_id: selectedProfile.id,
      priority: modalPriority,
      host_pattern: modalHostPattern,
      path_pattern: modalPathPattern,
      query_conditions: parsed,
      target_release_id: Number(modalTargetReleaseId),
      flags_override: {},
      is_active: true,
    });

    setModalPriority(100);
    setModalHostPattern('*');
    setModalPathPattern('/*');
    setModalQueryConditions('{}');
    setModalTargetReleaseId('');
    setIsRuleCreateOpen(false);
  };

  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold">Profiles & Rules</h3>
          <button
            className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-white/30 text-xs text-white/80 hover:border-white/60 hover:text-white"
            onClick={() => setIsHelpOpen(true)}
            aria-label="Profiles and rules help"
          >
            ?
          </button>
        </div>
        <button
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold"
          onClick={() => setIsProfileCreateOpen(true)}
        >
          Add new
        </button>
      </div>

      <div className="grid gap-2 md:grid-cols-2 mb-3">
        {profiles?.map((profile: any) => (
          <button
            key={profile.id}
            className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
              selectedProfileId === profile.id
                ? 'border-cyan-400/70 bg-cyan-300/10'
                : 'border-white/10 bg-black/20 hover:border-white/30'
            }`}
            onClick={() => {
              setSelectedProfileId(profile.id);
              setModalPriority(100);
              setModalHostPattern('*');
              setModalPathPattern('/*');
              setModalQueryConditions('{}');
              setModalTargetReleaseId('');
            }}
          >
            <div className="font-semibold">#{profile.id} {profile.key}</div>
            <div className="text-xs text-white/70">{profile.name}</div>
          </button>
        ))}
      </div>

      {notReadyTargets.length > 0 && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-300/10 px-3 py-2 text-xs mb-3">
          Warning: some rules target releases that are not `ready|active`.
        </div>
      )}

      <div className="space-y-2">
        {rules?.map((rule) => (
          <div key={rule.id} className="rounded-lg bg-black/20 px-3 py-2 text-sm flex items-center justify-between gap-2">
            <span>#{rule.id} profile:{profileById.get(rule.profile_id)?.key ?? rule.profile_id} p={rule.priority} {rule.host_pattern}{rule.path_pattern} → release:{rule.target_release_id}</span>
            <button className="text-red-300 hover:text-red-200" onClick={() => onDeleteRule(rule.id)}>Delete</button>
          </div>
        ))}
      </div>

      <Modal isOpen={isProfileCreateOpen} onClose={() => setIsProfileCreateOpen(false)}>
        <div className="w-full max-w-xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Add New Profile</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsProfileCreateOpen(false)}>Close</button>
          </div>
          <p className="mb-3 text-xs text-white/70">
            Профиль - это набор правил, который можно активировать целиком через Publish.
          </p>
          <div className="grid md:grid-cols-2 gap-2">
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Profile Key
                <InfoHint text="Уникальный технический ключ профиля. Примеры: main, campaign, maintenance." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="main" value={profileKey} onChange={(e) => setProfileKey(e.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Profile Name
                <InfoHint text="Отображаемое имя профиля в админке. Примеры: Main, Black Friday Campaign, Maintenance." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" placeholder="Main" value={profileName} onChange={(e) => setProfileName(e.target.value)} />
            </label>
            <div className="md:col-span-2">
              <button
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold"
                onClick={() => onCreateProfile({ key: profileKey, name: profileName, is_active: true }).then(() => { setProfileKey(''); setProfileName(''); setIsProfileCreateOpen(false); })}
              >
                Create profile
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)}>
        <div className="w-full max-w-2xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Profiles & Rules Guide</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsHelpOpen(false)}>Close</button>
          </div>
          <div className="rounded-xl border border-cyan-300/20 bg-cyan-400/5 p-3 mb-3">
            <div className="font-semibold mb-1">Что это</div>
            <div className="text-white/80">`Profile` - набор правил маршрутизации. Активируется один профиль целиком в Runtime State.</div>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="font-semibold mb-1">Как пользоваться</div>
              <div className="text-white/80 text-xs">1) Создайте профиль через `Add new`.</div>
              <div className="text-white/80 text-xs">2) Откройте карточку профиля.</div>
              <div className="text-white/80 text-xs">3) В разделе `Rules` нажмите `Add new` и добавьте правила.</div>
              <div className="text-white/80 text-xs">4) Выберите этот профиль в Runtime State и нажмите `Publish`.</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="font-semibold mb-1">Примеры</div>
              <div className="text-white/80 text-xs">main: * + /* → product v55</div>
              <div className="text-white/80 text-xs">campaign: /products* + utm_campaign=blackfriday → promo v99</div>
              <div className="text-white/80 text-xs">maintenance: * + /* → maintenance v12</div>
            </div>
          </div>
        </div>
      </Modal>

      <Modal isOpen={!!selectedProfile} onClose={() => setSelectedProfileId(null)}>
        {selectedProfile && (
          <div className="w-full max-w-3xl text-sm">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-white/60">Profile Card</div>
              <button className="text-white/70 hover:text-white" onClick={() => setSelectedProfileId(null)}>Close</button>
            </div>
            <div className="rounded-lg border border-white/20 bg-black/20 p-3 text-sm">
              <div>ID: {selectedProfile.id}</div>
              <div>Key: {selectedProfile.key}</div>
              <div>Name: {selectedProfile.name}</div>
              <div>Status: {selectedProfile.is_active ? 'active' : 'inactive'}</div>

              <div className="mt-4 border-t border-white/10 pt-4">
                <div className="mb-2 flex items-center justify-between">
                  <div className="text-xs uppercase tracking-wide text-white/60">Rules</div>
                  <button
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold"
                    onClick={() => setIsRuleCreateOpen(true)}
                  >
                    Add new
                  </button>
                </div>
                <div className="space-y-2 max-h-64 overflow-auto pr-1">
                  {selectedProfileRules.length === 0 && (
                    <div className="rounded-lg bg-black/20 px-3 py-2 text-white/70">No rules in this profile.</div>
                  )}
                  {selectedProfileRules.map((rule: any) => (
                    <div key={rule.id} className="rounded-lg bg-black/20 px-3 py-2 text-sm flex items-center justify-between gap-2">
                      <span>#{rule.id} p={rule.priority} {rule.host_pattern}{rule.path_pattern} → release:{rule.target_release_id}</span>
                      <button className="text-red-300 hover:text-red-200" onClick={() => onDeleteRule(rule.id)}>Delete</button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={isRuleCreateOpen} onClose={() => setIsRuleCreateOpen(false)}>
        <div className="w-full max-w-2xl text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs uppercase tracking-wide text-white/60">Add New Rule</div>
            <button className="text-white/70 hover:text-white" onClick={() => setIsRuleCreateOpen(false)}>Close</button>
          </div>
          <p className="mb-3 text-xs text-white/70">
            Создайте правило маршрутизации для этого профиля. Матчинг идет по приоритету (больше = раньше), затем по `host`, `path` и `query`.
          </p>
          <div className="grid md:grid-cols-5 gap-2 mb-2">
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Priority
                <InfoHint text="Чем больше число, тем раньше проверяется правило. Рекомендуется: 300+ для кампаний, 200 для специфичных путей, 100 для базовых маршрутов, 10 для общего fallback." />
              </span>
              <input type="number" className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" value={modalPriority} onChange={(e) => setModalPriority(Number(e.target.value))} />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Host Pattern
                <InfoHint text="Маска хоста (glob). Примеры: giftyai.ru, *.giftyai.ru, *.vercel.app, *. Если хотите правило для всех доменов, используйте *." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" value={modalHostPattern} onChange={(e) => setModalHostPattern(e.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Path Pattern
                <InfoHint text="Маска пути (glob). Примеры: /* (все), /product*, /investors, /products/*. Для точечного правила делайте максимально узкую маску." />
              </span>
              <input className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm" value={modalPathPattern} onChange={(e) => setModalPathPattern(e.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
                Target Release
                <InfoHint text="Релиз, который будет выбран, если rule совпал. Убедитесь, что релиз валиден и имеет рабочий Target URL; иначе трафик уйдет в fallback." />
              </span>
              <NiceSelect
                value={modalTargetReleaseId}
                onChange={(v) => setModalTargetReleaseId(v === "" ? "" : Number(v))}
                placeholder="Select release"
                options={(releases || []).map((r: any) => ({
                  value: r.id as number,
                  label: `#${r.id} ${r.version}`,
                  hint: r.target_url,
                }))}
              />
            </label>
            <div className="flex items-end">
              <button className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold" onClick={createRuleForSelectedProfile} disabled={!selectedProfile}>
                Create rule
              </button>
            </div>
          </div>
          <label className="block">
            <span className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-white/60">
              Query Conditions (JSON)
              <InfoHint text='Точное совпадение query-параметров. Пример: {"utm_campaign":"blackfriday","utm_source":"telegram"}. Если оставить {}, правило не фильтрует по query.' />
            </span>
            <textarea className="w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-xs" rows={2} value={modalQueryConditions} onChange={(e) => setModalQueryConditions(e.target.value)} />
          </label>
        </div>
      </Modal>
    </section>
  );
}
