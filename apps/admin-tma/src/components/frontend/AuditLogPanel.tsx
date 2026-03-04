"use client";

interface AuditLogPanelProps {
  items: any[];
}

export function AuditLogPanel({ items }: AuditLogPanelProps) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <h3 className="text-sm font-bold mb-3">Audit Log</h3>
      <div className="space-y-2 max-h-80 overflow-auto pr-1">
        {items?.map((row) => (
          <div key={row.id} className="rounded-lg bg-black/20 px-3 py-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span>#{row.id} {row.action} {row.entity_type}:{row.entity_id ?? '-'}</span>
              <span className="text-white/60">actor: {row.actor_id ?? 'system'}</span>
            </div>
            <div className="text-white/60">{row.created_at}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
