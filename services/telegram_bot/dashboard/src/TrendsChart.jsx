import React from 'react';

const TrendsChart = ({ dates, data, label, color = "#3b82f6" }) => {
    if (!data || data.length === 0) return null;

    const max = Math.max(...data, 1);
    const width = 300;
    const height = 100;
    const padding = 10;

    // Scale points to SVG space
    const points = data.map((val, i) => {
        const x = padding + (i * (width - 2 * padding) / (data.length - 1 || 1));
        const y = height - padding - (val * (height - 2 * padding) / max);
        return `${x},${y}`;
    }).join(' ');

    return (
        <div className="bg-slate-950/40 rounded-2xl border border-white/5 p-4">
            <div className="flex justify-between items-center mb-4">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{label}</span>
                <span className="text-sm font-black text-white">{data[data.length - 1]}</span>
            </div>
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-16 overflow-visible">
                {/* Gradient Definition */}
                <defs>
                    <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.3" />
                        <stop offset="100%" stopColor={color} stopOpacity="0" />
                    </linearGradient>
                </defs>

                {/* Area under the line */}
                <path
                    d={`M ${padding} ${height - padding} L ${points} L ${width - padding} ${height - padding} Z`}
                    fill={`url(#grad-${label})`}
                />

                {/* Line */}
                <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={points}
                    className="drop-shadow-[0_0_8px_rgba(59,130,246,0.3)]"
                />

                {/* Dots at start/end */}
                <circle cx={padding} cy={points.split(' ')[0].split(',')[1]} r="3" fill={color} />
                <circle cx={width - padding} cy={points.split(' ').pop().split(',')[1]} r="4" fill="#fff" stroke={color} strokeWidth="2" />
            </svg>
            <div className="flex justify-between mt-2 text-[8px] font-bold text-slate-600 uppercase">
                <span>{dates[0]}</span>
                <span>{dates[dates.length - 1]}</span>
            </div>
        </div>
    );
};

export default TrendsChart;
