"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

interface UsageChartProps {
    data?: any[];
}

export function UsageChart({ data = [] }: UsageChartProps) {
    const hasData = data && data.length > 0;

    return (
        <div className="px-4 py-2">
            <div className="card space-y-4 overflow-hidden">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="font-bold text-sm">User Activity</h2>
                        <p className="text-[10px] text-[var(--tg-theme-hint-color)]">Last 7 days trends</p>
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

                <div className="h-48 w-full -ml-6">
                    {hasData ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorDau" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#5288c1" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#5288c1" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <XAxis
                                    dataKey="name"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: 'var(--tg-theme-hint-color)', fontSize: 10, fontWeight: 500 }}
                                    dy={10}
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
                            No activity data available
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
