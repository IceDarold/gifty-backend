import React, { useState } from 'react';
import { Users, Package, AlertTriangle, CheckCircle, Clock, Layers, RefreshCw, TrendingUp, Zap } from 'lucide-react';
import TrendsChart from './TrendsChart';

const Dashboard = ({ data, onRefresh }) => {
  const [refreshing, setRefreshing] = useState(false);

  if (!data) return (
    <div className="flex flex-col items-center justify-center py-20 animate-pulse">
      <Zap className="text-slate-800 mb-4" size={48} />
      <div className="text-slate-600 font-bold uppercase tracking-widest text-xs">Synchronizing Engine...</div>
    </div>
  );

  const { monitoring, stats, workers, queue, trends } = data;

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh(true);
    setRefreshing(false);
  };

  const activeCount = Array.isArray(monitoring) ? monitoring.filter(m => m.status !== 'broken').length : 0;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-black bg-gradient-to-r from-white to-slate-500 bg-clip-text text-transparent">System Overview</h2>
          <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mt-1">Gifty AI Admin Intelligence</p>
        </div>
        <button
          onClick={handleRefresh}
          className={`p-3 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl text-slate-400 hover:text-white transition-all active:scale-90 shadow-2xl ${refreshing ? 'animate-spin' : ''}`}
        >
          <RefreshCw size={20} />
        </button>
      </header>

      {/* Analytics Trends */}
      {trends && (
        <section className="space-y-3">
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] px-1 flex items-center gap-2">
            <TrendingUp size={12} /> User Activity
          </h3>
          <div className="grid grid-cols-1 gap-4">
            <TrendsChart
              label="Daily Active Users"
              dates={trends.dates}
              data={trends.dau_trend}
              color="#6366f1"
            />
            <div className="grid grid-cols-2 gap-4">
              <TrendsChart
                label="Quiz Starts"
                dates={trends.dates}
                data={trends.quiz_starts}
                color="#10b981"
              />
              <div className="bg-slate-900/40 rounded-2xl border border-white/5 p-4 flex flex-col justify-center">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Conversion</div>
                <div className="text-2xl font-black">
                  {stats.quiz_completion_rate || 0}%
                </div>
                <div className="text-[10px] text-slate-600 font-bold mt-1">Quiz to Result</div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Quick Stats Grid */}
      <section className="space-y-3">
        <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] px-1">
          Scraping & Scale
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <StatCard
            icon={<CheckCircle className="text-emerald-500" size={20} />}
            label="Active Spiders"
            value={activeCount}
          />
          <StatCard
            icon={<Package className="text-blue-500" size={20} />}
            label="Items (24h)"
            value={stats.scraped_24h || 0}
          />
          <StatCard
            icon={<Layers className="text-amber-500" size={20} />}
            label="Queued Tasks"
            value={queue?.messages_ready || 0}
            detail={queue?.messages_unacknowledged ? `${queue.messages_unacknowledged} in work` : null}
          />
          <StatCard
            icon={<Users className="text-purple-500" size={20} />}
            label="Workers"
            value={workers.length}
          />
        </div>
      </section>

      {/* Workers List */}
      <section className="bg-slate-900/30 backdrop-blur-md rounded-3xl border border-white/5 overflow-hidden">
        <div className="p-4 border-b border-white/5 flex justify-between items-center">
          <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 text-slate-400">
            <Clock size={16} />
            Live Infrastructure
          </h3>
          <span className="text-[10px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full">{workers.length} ACTIVE</span>
        </div>
        <div className="divide-y divide-white/5">
          {workers.length === 0 ? (
            <div className="p-8 text-slate-600 text-center text-xs font-bold uppercase tracking-tighter italic">No active nodes detected</div>
          ) : (
            workers.map(w => (
              <div key={w.hostname} className="p-4 flex justify-between items-center hover:bg-white/5 transition-colors">
                <div>
                  <div className="text-sm font-bold text-slate-200">{w.hostname}</div>
                  <div className="flex gap-3 mt-1.5">
                    <div className="flex items-center gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                      <span className="text-[10px] font-bold text-slate-500">CPU {w.cpu_usage_pct || 0}%</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                      <span className="text-[10px] font-bold text-slate-500">RAM {w.ram_usage_pct || 0}%</span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div className="text-[10px] font-black bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 px-2 py-0.5 rounded-md">
                    ONLINE
                  </div>
                  <div className="text-[9px] font-mono text-slate-600">{w.concurrent_tasks || 0} CONCURRENT</div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};

const StatCard = ({ icon, label, value, detail }) => (
  <div className="bg-slate-900 p-4 rounded-2xl border border-slate-800">
    <div className="flex items-center gap-2 mb-2 text-slate-400">
      {icon}
      <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
    </div>
    <div className="flex items-baseline gap-2">
      <div className="text-2xl font-bold">{value}</div>
      {detail && <div className="text-[10px] text-slate-500 font-medium">{detail}</div>}
    </div>
  </div>
);

export default Dashboard;
