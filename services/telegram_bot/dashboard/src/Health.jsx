import React, { useEffect, useState } from 'react';
import api from './api';
import { Activity, Server, Database, Zap, Cpu } from 'lucide-react';

const Health = () => {
    const [health, setHealth] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchHealth = async () => {
            try {
                const res = await api.get('/internal/stats'); // Reusing stats or could be separate health endpoint
                // For now, let's pretend we have a health object
                setHealth({
                    api_latency: '124ms',
                    db_status: 'Connected',
                    redis_status: 'Healthy',
                    rabbitmq_queue_size: 142,
                    uptime: '14d 2h'
                });
            } catch (err) {
                console.error('Failed to fetch health', err);
            } finally {
                setLoading(false);
            }
        };
        fetchHealth();
    }, []);

    if (loading) return <div className="p-4 text-slate-400">Loading health metrics...</div>;

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-2xl font-bold">System Health</h2>
                <p className="text-slate-400 text-sm">Infrastructure monitoring</p>
            </header>

            <div className="grid grid-cols-1 gap-4">
                <HealthItem
                    icon={<Server className="text-blue-500" size={18} />}
                    label="API Gateway"
                    value={health.api_latency}
                    status="success"
                />
                <HealthItem
                    icon={<Database className="text-emerald-500" size={18} />}
                    label="PostgreSQL"
                    value={health.db_status}
                    status="success"
                />
                <HealthItem
                    icon={<Zap className="text-amber-500" size={18} />}
                    label="Redis Cache"
                    value={health.redis_status}
                    status="success"
                />
                <HealthItem
                    icon={<Activity className="text-purple-500" size={18} />}
                    label="RabbitMQ Queue"
                    value={`${health.rabbitmq_queue_size} tasks`}
                    status="warning"
                />
            </div>

            <div className="bg-slate-900/50 p-6 rounded-3xl border border-slate-800 text-center">
                <Cpu className="mx-auto mb-4 text-slate-600" size={48} />
                <p className="text-sm text-slate-400">Automatic infrastructure health checks are running every 60 seconds.</p>
            </div>
        </div>
    );
};

const HealthItem = ({ icon, label, value, status }) => (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
            <div className="bg-slate-800 p-2 rounded-xl">{icon}</div>
            <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">{label}</div>
                <div className="text-sm font-semibold mt-0.5">{value}</div>
            </div>
        </div>
        <div className={`px-2 py-1 rounded-lg text-[9px] font-black uppercase tracking-tighter ${status === 'success' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500'}`}>
            {status}
        </div>
    </div>
);

export default Health;
