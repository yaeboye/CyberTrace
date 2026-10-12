import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export const TraceChart = ({ running }) => {
  const [data, setData] = useState([]);

  // Fetch real live ADS1115 ADC trace data from backend
  useEffect(() => {
    const fetchTrace = async () => {
      try {
        const res = await fetch('http://localhost:8000/traces/sample');
        const json = await res.json();
        if (json.samples && json.samples.length > 0) {
          setData(json.samples);
        }
      } catch (e) {
        // Fallback
      }
    };

    fetchTrace();
    const interval = setInterval(fetchTrace, running ? 400 : 1500);
    return () => clearInterval(interval);
  }, [running]);

  return (
    <div className="glass-panel" style={{ height: '350px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h2 className="header-title">Live Power Trace</h2>
          <p className="header-subtitle">ADS1115 ADC Differential Measurement</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`status-indicator ${running ? 'active' : ''}`} />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {running ? 'COLLECTING' : 'IDLE'}
          </span>
        </div>
      </div>
      
      <div style={{ height: '230px', width: '100%' }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="sample" stroke="rgba(255,255,255,0.2)" tick={{fill: '#94a3b8', fontSize: 12}} />
            <YAxis domain={['auto', 'auto']} stroke="rgba(255,255,255,0.2)" tick={{fill: '#94a3b8', fontSize: 12}} />
            <Tooltip 
              contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
              itemStyle={{ color: '#3b82f6' }}
            />
            <Line 
              type="monotone" 
              dataKey="power" 
              stroke="#3b82f6" 
              strokeWidth={2} 
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
