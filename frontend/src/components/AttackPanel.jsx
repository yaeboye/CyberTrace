import React from 'react';
import { Activity, Clock, ShieldAlert } from 'lucide-react';

export const AttackPanel = ({ onAttack, attackState }) => {
  const { running, type, progress, result } = attackState;

  return (
    <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <h2 className="header-title">Attack Vectors</h2>
      <p className="header-subtitle">Simulate real-world side-channel attacks</p>

      <div style={{ display: 'flex', gap: '12px', marginTop: '20px', flexWrap: 'wrap' }}>
        <button 
          className="btn btn-primary" 
          disabled={running}
          onClick={() => onAttack('cpa')}
        >
          <Activity size={16} /> Run CPA Attack
        </button>
        <button 
          className="btn btn-primary"
          disabled={running}
          onClick={() => onAttack('timing')}
        >
          <Clock size={16} /> Run Timing Attack
        </button>
        <button 
          className="btn btn-primary"
          disabled={running}
          onClick={() => onAttack('replay')}
        >
          <ShieldAlert size={16} /> Run Replay Attack
        </button>
      </div>

      {running && (
        <div style={{ marginTop: '30px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Executing {type.toUpperCase()}...</span>
            <span style={{ fontSize: '0.875rem', color: 'var(--accent-blue)' }}>{progress.toFixed(1)}%</span>
          </div>
          <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{ 
              height: '100%', 
              width: `${progress}%`, 
              background: 'linear-gradient(90deg, var(--accent-blue), var(--accent-purple))',
              transition: 'width 0.3s ease'
            }} />
          </div>
        </div>
      )}

      {!running && result && result.recovered_key && (
        <div style={{ marginTop: '30px', padding: '16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--accent-green)', borderRadius: '8px' }}>
          <h3 style={{ color: 'var(--accent-green)', fontSize: '0.9rem', marginBottom: '8px' }}>Attack Result</h3>
          <p style={{ fontFamily: 'monospace', fontSize: '1.1rem' }}>Recovered Key: {result.recovered_key}</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>Match: {result.match ? 'SUCCESS' : 'FAILED'}</p>
        </div>
      )}
      {!running && result && result.recovered && (
        <div style={{ marginTop: '30px', padding: '16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--accent-green)', borderRadius: '8px' }}>
          <h3 style={{ color: 'var(--accent-green)', fontSize: '0.9rem', marginBottom: '8px' }}>Attack Result</h3>
          <p style={{ fontFamily: 'monospace', fontSize: '1.1rem' }}>Recovered Secret: {result.recovered}</p>
        </div>
      )}
    </div>
  );
};
