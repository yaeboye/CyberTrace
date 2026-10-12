import React from 'react';

const DefenseToggle = ({ name, description, checked, onChange }) => {
  return (
    <div className="toggle-row">
      <div className="toggle-info">
        <span className="toggle-name">{name}</span>
        <span className="toggle-desc">{description}</span>
      </div>
      <label className="switch">
        <input type="checkbox" checked={checked} onChange={onChange} />
        <span className="slider"></span>
      </label>
    </div>
  );
};

export const DefensePanel = ({ defenses, onToggle }) => {
  return (
    <div className="glass-panel">
      <h2 className="header-title">Defense Matrix</h2>
      <p className="header-subtitle" style={{marginBottom: '20px'}}>Active Hardware Defenses</p>
      
      <div className="defenses-list">
        <DefenseToggle 
          name="Masking (L1)" 
          description="Randomizes power traces to thwart CPA"
          checked={defenses.masking || false}
          onChange={(e) => onToggle('masking', e.target.checked)}
        />
        <DefenseToggle 
          name="Constant-Time (L1)" 
          description="Eliminates timing side-channels in crypto ops"
          checked={defenses.constant_time || false}
          onChange={(e) => onToggle('constant_time', e.target.checked)}
        />
        <DefenseToggle 
          name="Noise Injection (L2)" 
          description="Support ESP32 obfuscates EM emissions"
          checked={defenses.noise_injection || false}
          onChange={(e) => onToggle('noise_injection', e.target.checked)}
        />
        <DefenseToggle 
          name="Probing Detection (L4)" 
          description="ML Isolation Forest detects anomalous traffic"
          checked={defenses.probing_detection || false}
          onChange={(e) => onToggle('probing_detection', e.target.checked)}
        />
        <DefenseToggle 
          name="Dynamic Key Refresh" 
          description="Rotates session keys upon probing detection"
          checked={defenses.key_refresh || false}
          onChange={(e) => onToggle('key_refresh', e.target.checked)}
        />
      </div>
    </div>
  );
};
