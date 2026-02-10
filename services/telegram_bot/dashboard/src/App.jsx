import React, { useEffect, useState } from 'react';
import { authWithTelegram } from './api';
import { LayoutDashboard, Bug, Activity, Settings as SettingsIcon } from 'lucide-react';
import Dashboard from './Dashboard';
import SpiderList from './SpiderList';
import SpiderDetail from './SpiderDetail';
import Health from './Health';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedSpiderId, setSelectedSpiderId] = useState(null);

  useEffect(() => {
    const WebApp = window.Telegram?.WebApp;
    if (WebApp) {
      WebApp.ready();
      WebApp.expand();
    }

    const login = async () => {
      try {
        const data = await authWithTelegram();
        setUser(data.user);
      } catch (err) {
        console.error('Auth failed', err);
        setError('Unauthorized access');
      } finally {
        setLoading(false);
      }
    };

    login();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950 text-white">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-blue-500 border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-white p-6 text-center">
        <div className="w-16 h-16 bg-red-500/20 text-red-500 rounded-full flex items-center justify-center mb-6">
          <AlertTriangle size={32} />
        </div>
        <h2 className="text-xl font-bold mb-2">Access Denied</h2>
        <p className="text-slate-400 text-sm mb-6">This dashboard is only available to authorized administrators from the Telegram bot.</p>
        <button
          onClick={() => window.location.reload()}
          className="bg-slate-800 px-6 py-2 rounded-xl text-sm font-medium"
        >
          Retry Login
        </button>
      </div>
    );
  }

  const renderContent = () => {
    if (selectedSpiderId && activeTab === 'spiders') {
      return <SpiderDetail sourceId={selectedSpiderId} onBack={() => setSelectedSpiderId(null)} />;
    }

    switch (activeTab) {
      case 'dashboard': return <Dashboard />;
      case 'spiders': return <SpiderList onSelectSpider={(id) => setSelectedSpiderId(id)} />;
      case 'health': return <Health />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans pb-24 selection:bg-blue-500/30">
      {/* Header */}
      <header className="px-5 py-4 border-b border-slate-800/50 flex justify-between items-center sticky top-0 bg-slate-950/80 backdrop-blur-xl z-20">
        <div className="flex items-center gap-2.5">
          <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-2 rounded-xl shadow-lg shadow-blue-500/20">
            <Activity size={18} strokeWidth={2.5} />
          </div>
          <span className="font-bold text-lg tracking-tight">Gifty Panel</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-lg bg-slate-800/50 text-slate-400 border border-slate-700/50">
            {user?.role}
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="px-5 pt-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
        {renderContent()}
      </main>

      {/* Bottom Navigation */}
      <div className="fixed bottom-6 left-5 right-5 z-30">
        <nav className="bg-slate-900/90 backdrop-blur-2xl border border-white/5 rounded-3xl p-1.5 shadow-2xl flex justify-between items-center ring-1 ring-white/5">
          <NavButton
            active={activeTab === 'dashboard'}
            onClick={() => setActiveTab('dashboard')}
            icon={<LayoutDashboard size={20} />}
            label="Overview"
          />
          <NavButton
            active={activeTab === 'spiders'}
            onClick={() => setActiveTab('spiders')}
            icon={<Bug size={20} />}
            label="Spiders"
          />
          <NavButton
            active={activeTab === 'health'}
            onClick={() => setActiveTab('health')}
            icon={<Activity size={20} />}
            label="Health"
          />
          <NavButton
            active={activeTab === 'settings'}
            onClick={() => setActiveTab('settings')}
            icon={<SettingsIcon size={20} />}
            label="Settings"
          />
        </nav>
      </div>
    </div>
  );
}

const NavButton = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={`flex-1 flex flex-col items-center justify-center py-2.5 rounded-2xl transition-all duration-300 ${active
      ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/25 translate-y-[-2px]'
      : 'text-slate-500 hover:text-slate-300'
      }`}
  >
    {icon}
    <span className={`text-[9px] mt-1 font-bold uppercase tracking-tighter ${active ? 'opacity-100' : 'opacity-60'}`}>
      {label}
    </span>
  </button>
);

const AlertTriangle = ({ size }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
);

export default App;
