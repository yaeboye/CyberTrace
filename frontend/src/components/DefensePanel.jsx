import React from 'react';

const DEFENSES = [
  { key: 'masking', label: 'Masking', desc: 'randomizes intermediate values vs CPA' },
  { key: 'constant_time', label: 'Constant-time compare', desc: 'flat auth timing vs timing attack' },
  { key: 'nonce', label: 'Nonce + counter', desc: 'rejects replayed commands' },
  { key: 'noise_injection', label: 'Noise injection', desc: 'support ESP32 adds rail noise' },
  { key: 'probing_detection', label: 'Probing detection', desc: 'isolation-forest traffic monitor' },
  { key: 'key_refresh', label: 'Key refresh', desc: 'rotates key on probing alert' },
];

const Toggle = ({ checked, onChange }) => (
  <label className="switch">
    <input type="checkbox" checked={checked} onChange={onChange} />
    <span className="slider" />
  </label>
);

export const DefensePanel = ({ defenses, onToggle }) => (
  <div className="panel">
    <div className="panel-head"><h2>Defenses</h2></div>
    <div className="panel-body" style={{ paddingTop: 2, paddingBottom: 2 }}>
      {DEFENSES.map((d) => (
        <div className="row" key={d.key}>
          <div>
            <div className="label">{d.label}</div>
            <div className="desc">{d.desc}</div>
          </div>
          <Toggle
            checked={!!defenses[d.key]}
            onChange={(e) => onToggle(d.key, e.target.checked)}
          />
        </div>
      ))}
    </div>
  </div>
);
