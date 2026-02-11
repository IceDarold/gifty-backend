import React, { useState } from 'react';
import api from './api';
import { Save, X, Info } from 'lucide-react';

const ConfigEditor = ({ source, onSave, onCancel }) => {
    const [formData, setFormData] = useState({
        url: source.url,
        refresh_interval_hours: source.refresh_interval_hours,
        priority: source.priority,
        config: JSON.stringify(source.config || {}, null, 2)
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            let configObj = {};
            try {
                configObj = JSON.parse(formData.config);
            } catch (e) {
                throw new Error('Invalid JSON in Extra Config');
            }

            const payload = {
                url: formData.url,
                refresh_interval_hours: parseInt(formData.refresh_interval_hours),
                priority: parseInt(formData.priority),
                config: configObj
            };

            await api.patch(`/internal/sources/${source.id}`, payload);
            onSave();
        } catch (err) {
            setError(err.message || 'Failed to update config');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-slate-950 z-50 overflow-y-auto animate-in slide-in-from-bottom duration-300">
            <header className="p-4 border-b border-slate-800 flex justify-between items-center sticky top-0 bg-slate-950/80 backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <button onClick={onCancel} className="p-2 hover:bg-slate-900 rounded-xl">
                        <X size={20} />
                    </button>
                    <h2 className="font-bold">Edit Config: {source.site_key}</h2>
                </div>
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-blue-600 px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 disabled:opacity-50"
                >
                    {saving ? 'Saving...' : <><Save size={16} /> Save</>}
                </button>
            </header>

            <div className="p-6 space-y-6">
                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-3 rounded-xl text-xs">
                        {error}
                    </div>
                )}

                <div className="space-y-4">
                    <div>
                        <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 ml-1">Crawler URL</label>
                        <input
                            type="text"
                            className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            value={formData.url}
                            onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 ml-1">Interval (Hrs)</label>
                            <input
                                type="number"
                                className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                value={formData.refresh_interval_hours}
                                onChange={(e) => setFormData({ ...formData, refresh_interval_hours: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 ml-1">Priority (1-100)</label>
                            <input
                                type="number"
                                className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                value={formData.priority}
                                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between items-center mb-1.5 ml-1">
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Extra Config (JSON)</label>
                            <Info size={12} className="text-slate-600" />
                        </div>
                        <textarea
                            rows={10}
                            className="w-full bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs font-mono focus:ring-2 focus:ring-blue-500 outline-none"
                            value={formData.config}
                            onChange={(e) => setFormData({ ...formData, config: e.target.value })}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ConfigEditor;
