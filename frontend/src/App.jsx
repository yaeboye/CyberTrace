import React, { useEffect, useState } from 'react';
import { DefensePanel } from './components/DefensePanel';
import { AttackPanel } from './components/AttackPanel';
import { TraceChart } from './components/TraceChart';
import {
  fetchDefenseStatus, toggleDefense, startAttack,
  getAttackProgress, fetchAlerts, fetchKeyHistory, checkHealth,
} from './api';

function App() {
  const [defenses, setDefenses] = useState({});
  const [attackState, setAttackState] = useState({ running: false, type: '', progress: 0, result: null });
  const [alerts, setAlerts] = useState([]);
  const [keyHistory, setKeyHistory] = useState([]);
  const [online, setOnline] = useState(null);

  useEffect(() => {
    fetchDefenseStatus().then(setDefenses).catch(() => {});
    const interval = setInterval(async () => {
      try {
        setAttackState(await getAttackProgress());
        setAlerts(await fetchAlerts());
        setKeyHistory(await fetchKeyHistory());
        await checkHealth();
        setOnline(true);
      } catch (e) {
        setOnline(false);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async (layer, enabled) => {
    setDefenses((p) => ({ ...p, [layer]: enabled }));
    try { await toggleDefense(layer, enabled); }
    catch { setDefenses((p) => ({ ...p, [layer]: !enabled })); }
  };

  const handleAttack = async (type) => {
    try {
      await startAttack(type);
      setAttackState({ running: true, type, progress: 0, result: null });
    } catch (e) { /* surfaced via connection indicator */ }
  };

  return (
    <div className="app">
      <div className="topbar">
        <h1>CyberTrace</h1>
        <span className="sub">esp32-s3 side-channel testbed</span>
        <span className="spacer" />
        <span className="conn">
          <span className={`dot ${online ? 'on' : online === false ? '' : ''}`}
                style={online === false ? { background: 'var(--bad)' } : undefined} />
          {online === null ? 'connecting' : online ? 'api online' : 'api offline'}
        </span>
      </div>

      <div className="grid">
        <div className="col">
          <DefensePanel defenses={defenses} onToggle={handleToggle} />

          <div className="panel">
            <div className="panel-head"><h2>Alerts</h2></div>
            <div className="panel-body">
              {alerts.length === 0 ? (
                <p className="empty">No anomalous activity.</p>
              ) : (
                alerts.slice(0, 6).map((a, i) => (
                  <div className="alert" key={i}>
                    <div className="t">{(a.type || 'event').toUpperCase()}</div>
                    <div className="d">
                      {a.detail || (a.value != null
                        ? `value ${Number(a.value).toFixed(2)} vs threshold ${Number(a.threshold ?? 0).toFixed(2)}`
                        : 'flagged')}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="col">
          <TraceChart running={attackState.running} />
          <AttackPanel onAttack={handleAttack} attackState={attackState} />

          <div className="panel">
            <div className="panel-head"><h2>Key rotations</h2></div>
            <div className="panel-body">
              {keyHistory.length === 0 ? (
                <p className="empty">No rotations yet.</p>
              ) : (
                <dl className="kv">
                  {keyHistory.slice(0, 6).map((k, i) => (
                    <React.Fragment key={i}>
                      <dt>{k.new_key}</dt>
                      <dd style={{ color: 'var(--text-dim)' }}>{k.reason} · {k.created_at}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
