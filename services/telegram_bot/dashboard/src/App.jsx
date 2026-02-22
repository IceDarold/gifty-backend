import React, { useEffect, useState, useCallback } from 'react';
import { authWithTelegram } from './api';
import api from './api';
import { LayoutDashboard, Bug, Activity, Settings as SettingsIcon, Brain, Package, RefreshCw } from 'lucide-react';
import Dashboard from './Dashboard';
import SpiderList from './SpiderList';
import SpiderDetail from './SpiderDetail';
import Health from './Health';
import Intelligence from './Intelligence';
import Catalog from './Catalog';

const NavButton = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={`flex flex-col items-center gap-1 p-2 transition-all ${active ? 'text-blue-400 scale-110' : 'text-slate-500 hover:text-slate-300'}`}
  >
    {icon}
    <span className="text-[10px] font-bold uppercase tracking-tighter">{label}</span>
  </button>
);

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedSpiderId, setSelectedSpiderId] = useState(null);
  const [auth, setAuth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Catalog Filters State
  const [catalogSearch, setCatalogSearch] = useState('');
  const [catalogPage, setCatalogPage] = useState(0);

  // Cache Storage
  const [cache, setCache] = useState({
    dashboard: null,
    spiders: null,
    catalog: null,
    health: null,
    intelligence: null,
    lastUpdate: {}
  });

  const updateCache = useCallback((key, data) => {
    setCache(prev => ({
      ...prev,
      [key]: data,
      lastUpdate: { ...prev.lastUpdate, [key]: new Date() }
    }));
  }, []);

  const fetchDashboardData = useCallback(async (force = false) => {
    if (!force && cache.dashboard) return;
    try {
      const [monRes, statsRes, workersRes, queueRes, trendsRes] = await Promise.all([
        api.get('/internal/monitoring'),
        api.get('/internal/stats'),
        api.get('/internal/workers'),
        api.get('/internal/queues/stats'),
        api.get('/analytics/trends', { params: { days: 7 } }),
      ]);
      updateCache('dashboard', {
        monitoring: monRes.data,
        stats: statsRes.data,
        workers: workersRes.data,
        queue: queueRes.data,
        trends: trendsRes.data
      });
    } catch (err) { console.error('Dashboard fetch error', err); }
  }, [cache.dashboard, updateCache]);

  const fetchSpiders = useCallback(async (force = false) => {
    if (!force && cache.spiders) return;
    try {
      const res = await api.get('/internal/monitoring');
      updateCache('spiders', res.data);
    } catch (err) { console.error('Spiders fetch error', err); }
  }, [cache.spiders, updateCache]);

  const fetchCatalog = useCallback(async (force = false) => {
    // For catalog we always fetch if search/page changes, 
    // but caching ensures it doesn't blink when switching tabs back to the same search
    try {
      const res = await api.get('/internal/products', {
        params: { limit: 20, offset: catalogPage * 20, search: catalogSearch || undefined }
      });
      updateCache('catalog', res.data);
    } catch (err) { console.error('Catalog fetch error', err); }
  }, [catalogPage, catalogSearch, updateCache]);

  // Auth Effect
  useEffect(() => {
    const login = async () => {
      try {
        const data = await authWithTelegram();
        setAuth(data);
      } catch (err) {
        setError(err.response?.status === 403 ? 'ACCESS_DENIED' : 'SERVER_ERROR');
      } finally {
        setLoading(false);
      }
    };
    login();
  }, []);

  // Data Fetching Effect based on active tab
  useEffect(() => {
    if (!auth) return;
    if (activeTab === 'dashboard') fetchDashboardData();
    if (activeTab === 'spiders') fetchSpiders();
    if (activeTab === 'catalog') fetchCatalog();
  }, [activeTab, auth, fetchDashboardData, fetchSpiders, fetchCatalog, catalogPage, catalogSearch]);

  if (loading) return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-slate-400 font-medium animate-pulse">Authenticating with Telegram...</div>
      </div>
    </div>
  );

  if (error === 'ACCESS_DENIED') return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center p-6 text-center">
      <div className="max-w-xs space-y-4">
        <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mx-auto text-red-500 border border-red-500/20">
          <Bug size={40} />
        </div>
        <h1 className="text-xl font-bold text-red-400">Access Denied</h1>
        <p className="text-sm text-slate-400">You do not have administrative permissions to access this dashboard.</p>
      </div>
    </div>
  );

  const renderContent = () => {
    if (selectedSpiderId && activeTab === 'spiders') {
      return <SpiderDetail sourceId={selectedSpiderId} onBack={() => setSelectedSpiderId(null)} />;
    }

    switch (activeTab) {
      case 'dashboard': return <Dashboard data={cache.dashboard} onRefresh={fetchDashboardData} />;
      case 'spiders': return <SpiderList data={cache.spiders} onSelectSpider={setSelectedSpiderId} onRefresh={fetchSpiders} />;
      case 'health': return <Health />;
      case 'intelligence': return <Intelligence />;
      case 'catalog': return (
        <Catalog
          data={cache.catalog}
          onRefresh={fetchCatalog}
          search={catalogSearch}
          page={catalogPage}
          onSearchChange={(v) => { setCatalogSearch(v); setCatalogPage(0); }}
          onPageChange={setCatalogPage}
        />
      );
      default: return <Dashboard data={cache.dashboard} onRefresh={fetchDashboardData} />;
    }
  };

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col font-sans selection:bg-blue-500/30">
      <main className="flex-1 pb-24 p-4 max-w-lg mx-auto w-full">
        {renderContent()}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 bg-slate-950/80 backdrop-blur-2xl border-t border-slate-800/50 pb-6 pt-2 px-4 z-50">
        <div className="max-w-lg mx-auto flex justify-between items-center">
          <NavButton active={activeTab === 'dashboard'} onClick={() => { setActiveTab('dashboard'); setSelectedSpiderId(null); }} icon={<LayoutDashboard size={22} />} label="Overview" />
          <NavButton active={activeTab === 'spiders'} onClick={() => setActiveTab('spiders')} icon={<Bug size={22} />} label="Spiders" />
          <NavButton active={activeTab === 'catalog'} onClick={() => setActiveTab('catalog')} icon={<Package size={22} />} label="Catalog" />
          <NavButton active={activeTab === 'intelligence'} onClick={() => setActiveTab('intelligence')} icon={<Brain size={22} />} label="AI" />
          <NavButton active={activeTab === 'health'} onClick={() => setActiveTab('health')} icon={<Activity size={22} />} label="System" />
        </div>
      </nav>
    </div>
  );
};

export default App;
