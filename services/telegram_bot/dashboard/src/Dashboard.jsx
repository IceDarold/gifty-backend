import React, { useEffect, useState } from 'react';
import api from './api';
import { Users, Package, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

const Dashboard = () => {
  const [monitoring, setMonitoring] = useState([]);
  const [stats, setStats] = useState({});
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [monRes, statsRes, workersRes] = await Promise.all([
          api.get('/internal/monitoring'),
          api.get('/internal/stats'),
          api.get('/internal/workers'),
        ]);
        setMonitoring(monRes.data);
        setStats(statsRes.data);
        setWorkers(workersRes.data);
      } catch (err) {
        console.error('Failed to fetch dashboard data', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000); // 30s refresh
    return () => clearInterval(interval);
  }, []);

  const activeCount = monitoring.filter(m => m.status !== 'broken').length;
  const brokenCount = monitoring.filter(m => m.status === 'broken').length;

  if (loading) return <div className="p-4 text-slate-400">Loading metrics...</div>;

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold">Scraping Overview</h2>
        <p className="text-slate-400 text-sm">Real-time status of your spiders</p>
      </header>

      {/* Quick Stats Grid */}
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
          icon={<AlertTriangle className="text-amber-500" size={20} />}
          label="Broken"
          value={brokenCount}
        />
        <StatCard
          icon={<Users className="text-purple-500" size={20} />}
          label="Workers"
          value={workers.length}
        />
      </div>

      {/* Workers List */}
      <section className="bg-slate-900/50 rounded-2xl border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex justify-between items-center">
          <h3 className="font-semibold flex items-center gap-2">
            <Clock size={18} className="text-slate-400" />
            Active Workers
          </h3>
          <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-white">{workers.length}</span>
        </div>
        <div className="divide-y divide-slate-800">
          {workers.length === 0 ? (
            <div className="p-4 text-slate-500 text-center text-sm italic">No active workers found</div>
          ) : (
            workers.map(w => (
              <div key={w.hostname} className="p-4 flex justify-between items-center">
                <div>
                  <div className="text-sm font-medium">{w.hostname}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    CPU: {w.cpu_usage}% • RAM: {w.memory_usage}%
                  </div>
                </div>
                <div className="text-xs font-mono bg-blue-500/10 text-blue-400 px-2 py-1 rounded border border-blue-500/20">
                  {w.tasks_count} tasks
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};

const StatCard = ({ icon, label, value }) => (
  <div className="bg-slate-900 p-4 rounded-2xl border border-slate-800">
    <div className="flex items-center gap-2 mb-2 text-slate-400">
      {icon}
      <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
    </div>
    <div className="text-2xl font-bold">{value}</div>
  </div>
);

export default Dashboard;
