"use client";

import { useState } from 'react';

interface AllowedHostsPanelProps {
  hosts: any[];
  onCreate: (payload: { host: string; is_active?: boolean }) => Promise<any>;
  onDelete: (id: number) => Promise<any>;
}

export function AllowedHostsPanel({ hosts, onCreate, onDelete }: AllowedHostsPanelProps) {
  const [host, setHost] = useState('');

  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <h3 className="text-sm font-bold mb-3">Allowed Hosts</h3>
      <div className="flex gap-2 mb-3">
        <input
          className="rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm flex-1"
          placeholder="example.vercel.app"
          value={host}
          onChange={(e) => setHost(e.target.value.toLowerCase())}
        />
        <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold" onClick={() => onCreate({ host, is_active: true }).then(() => setHost(''))}>Add</button>
      </div>
      <div className="space-y-2">
        {hosts?.map((item) => (
          <div key={item.id} className="rounded-lg bg-black/20 px-3 py-2 text-sm flex items-center justify-between">
            <span>{item.host} ({item.is_active ? 'active' : 'disabled'})</span>
            <button className="text-red-300 hover:text-red-200" onClick={() => onDelete(item.id)}>Delete</button>
          </div>
        ))}
      </div>
    </section>
  );
}
