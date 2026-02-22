"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { useLanguage } from "@/contexts/LanguageContext";

interface UsageChartProps {
    data?: any;
}

export function UsageChart({ data }: UsageChartProps) {
    const { t } = useLanguage();

    // Transform object data from API to array format for Recharts
    const chartData = Array.isArray(data) ? data : (data?.dates ? data.dates.map((date: string, i: number) => {
        const parts = date.split(/[-/]/);
        let name = date;
        if (parts.length >= 3) {
            // If YYYY-MM-DD, use MM/DD
            if (parts[0].length === 4) name = `${parts[1]}/${parts[2]}`;
            // If DD-MMM-YYYY or DD-MM-YYYY, use DD/MM
            else name = `${parts[0]}/${parts[1]}`;
        } else if (parts.length === 2) {
            name = parts.join('/');
        }

        return {
            name,
            date,
            dau: Number(data.dau_trend?.[i] || 0),
            completed: Number(data.quiz_starts?.[i] || 0)
        };
    }) : []);

    const hasData = chartData && chartData.length > 0;

    return (
        <div className="px-4 py-2">
            <div className="card space-y-4 overflow-hidden">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="font-bold text-sm">{t('dashboard.user_activity')}</h2>
                        <p className="text-[10px] text-[var(--tg-theme-hint-color)]">{t('dashboard.last_7_days')}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full bg-[#5288c1]"></div>
                            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">DAU</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full bg-[#64b5ef]"></div>
                            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">Quiz</span>
                        </div>
                    </div>
                </div>

                <div className="h-48 w-full">
                    {hasData ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                                <defs>
                                    <linearGradient id="colorDau" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#5288c1" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#5288c1" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--tg-theme-hint-color)" strokeOpacity={0.1} />
                                <XAxis
                                    dataKey="name"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: 'var(--tg-theme-hint-color)', fontSize: 10, fontWeight: 500 }}
                                    dy={10}
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: 'var(--tg-theme-hint-color)', fontSize: 10, fontWeight: 500 }}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: 'var(--tg-theme-section-bg-color)',
                                        border: 'none',
                                        borderRadius: '12px',
                                        boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                                    }}
                                    labelStyle={{ color: 'var(--tg-theme-text-color)', fontWeight: 'bold', marginBottom: '4px' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="dau"
                                    stroke="#5288c1"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorDau)"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="completed"
                                    stroke="#64b5ef"
                                    strokeWidth={2}
                                    strokeDasharray="5 5"
                                    fill="none"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-full text-[var(--tg-theme-hint-color)] text-xs">
                            {t('dashboard.no_activity')}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
