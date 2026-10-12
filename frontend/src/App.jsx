import React, { useEffect, useState } from 'react';
import { DefensePanel } from './components/DefensePanel';
import { AttackPanel } from './components/AttackPanel';
import { TraceChart } from './components/TraceChart';
import { Shield, Zap, AlertTriangle } from 'lucide-react';
import { fetchDefenseStatus, toggleDefense, startAttack, getAttackProgress, fetchAlerts } from './api';

function App() {
  const [defenses, setDefenses] = useState({});
  const [attackState, setAttackState] = useState({ running: false, type: '', progress: 0, result: null });
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    // Load initial defense status
    fetchDefenseStatus().then(setDefenses).catch(console.error);
    
    // Poll attack progress & alerts
    const interval = setInterval(async () => {
      try {
        const prog = await getAttackProgress();
        setAttackState(prog);
        
        const al = await fetchAlerts();
        setAlerts(al);
      } catch (e) {
        // Ignore API errors while loading
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleDefense = async (layer, enabled) => {
    // Optimistic UI update
    setDefenses(prev => ({ ...prev, [layer]: enabled }));
    try {
      await toggleDefense(layer, enabled);
    } catch (e) {
      // Revert on error
      setDefenses(prev => ({ ...prev, [layer]: !enabled }));
    }
  };

  const handleRunAttack = async (type) => {
    try {
      await startAttack(type);
      setAttackState({ running: true, type, progress: 0, result: null });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))', padding: '10px', borderRadius: '12px' }}>
            <Zap color="white" size={24} />
          </div>
          <div>
            <h1 className="header-title" style={{ fontSize: '1.75rem', margin: 0 }}>CyberTrace</h1>
            <p className="header-subtitle">Embedded CPS Security Framework</p>
          </div>
        </div>

        <DefensePanel defenses={defenses} onToggle={handleToggleDefense} />

        <div className="glass-panel" style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <AlertTriangle color="var(--accent-red)" size={20} />
            <h2 className="header-title" style={{ fontSize: '1.2rem', margin: 0 }}>Security Alerts</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {alerts.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', fontStyle: 'italic' }}>No anomalous activity detected.</p>
            ) : (
              alerts.slice(0, 5).map((a, i) => (
                <div key={i} className="alert-item">
                  <div style={{ fontWeight: 600, color: 'var(--accent-red)' }}>{a.type.toUpperCase()} DETECTED</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '2px' }}>{a.detail || `Value ${a.value.toFixed(2)} exceeded threshold`}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="main-content">
        <TraceChart running={attackState.running} />
        <AttackPanel onAttack={handleRunAttack} attackState={attackState} />
      </div>
    </div>
  );
}

export default App;
