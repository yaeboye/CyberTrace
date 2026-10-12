import React, { useEffect, useRef, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '../api';

export const TraceChart = ({ running }) => {
  const [data, setData] = useState([]);
  const [hardware, setHardware] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    const fetchTrace = async () => {
      try {
        const res = await api.get('/traces/sample');
        if (res.data.samples?.length) {
          setData(res.data.samples);
          setHardware(res.data.hardware);
        }
      } catch (e) { /* backend offline; keep last frame */ }
    };
    fetchTrace();
    timer.current = setInterval(fetchTrace, running ? 400 : 1500);
    return () => clearInterval(timer.current);
  }, [running]);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Power trace · ADS1115</h2>
        <span className="conn">
          <span className={`dot ${running ? 'run' : hardware ? 'on' : ''}`} />
          {hardware === null ? 'no data' : hardware ? 'live ADC' : 'simulated'}
        </span>
      </div>
      <div className="panel-body">
        <div style={{ height: 220, width: '100%' }}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#242931" vertical={false} />
              <XAxis dataKey="sample" stroke="#3a4049" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis domain={['auto', 'auto']} stroke="#3a4049" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#1a1d21', border: '1px solid #2b3038', borderRadius: 4, fontSize: 12 }}
                labelStyle={{ color: '#9aa1a9' }}
                itemStyle={{ color: '#4aa3c7' }}
              />
              <Line type="monotone" dataKey="power" stroke="#4aa3c7" strokeWidth={1.5}
                    dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
