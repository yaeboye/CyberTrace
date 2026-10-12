import React from 'react';

const ATTACKS = [
  { type: 'cpa', label: 'CPA', hint: 'power / key recovery' },
  { type: 'timing', label: 'Timing', hint: 'response latency' },
  { type: 'replay', label: 'Replay', hint: 'command resend' },
];

const ResultTable = ({ result }) => {
  const entries = Object.entries(result).filter(([k]) => k !== 'note');
  return (
    <>
      <dl className="kv">
        {entries.map(([k, v]) => {
          let cls = '';
          if (k === 'match') cls = v ? 'ok-text' : 'bad-text';
          return (
            <React.Fragment key={k}>
              <dt>{k}</dt>
              <dd className={cls}>{String(v)}</dd>
            </React.Fragment>
          );
        })}
      </dl>
      {result.note && (
        <p style={{ marginTop: 10, fontSize: '0.72rem', color: 'var(--text-faint)', lineHeight: 1.5 }}>
          {result.note}
        </p>
      )}
    </>
  );
};

export const AttackPanel = ({ onAttack, attackState }) => {
  const { running, type, progress, result } = attackState;
  const hasResult = result && Object.keys(result).length > 0;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Attacks</h2>
        <span className="conn">
          <span className={`dot ${running ? 'run' : ''}`} />
          {running ? `running ${type}` : 'idle'}
        </span>
      </div>
      <div className="panel-body">
        <div className="btn-row">
          {ATTACKS.map((a) => (
            <button key={a.type} className="btn" disabled={running} onClick={() => onAttack(a.type)}>
              {a.label}
              <span style={{ color: 'var(--text-faint)', fontSize: '0.7rem' }}>{a.hint}</span>
            </button>
          ))}
        </div>

        {running && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                {type} · {progress.toFixed(0)}%
              </span>
            </div>
            <div className="bar"><span style={{ width: `${progress}%` }} /></div>
          </div>
        )}

        {!running && hasResult && (
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--line)' }}>
            <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em',
                          color: 'var(--text-faint)', marginBottom: 10 }}>
              Result{result.hardware === false ? ' (simulated)' : result.hardware ? ' (hardware)' : ''}
            </div>
            <ResultTable result={result} />
          </div>
        )}
      </div>
    </div>
  );
};
