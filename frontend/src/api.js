import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
});

export const fetchDefenseStatus = async () => {
  const res = await api.get('/defense/status');
  return res.data;
};

export const toggleDefense = async (layer, enabled) => {
  const res = await api.post('/defense/toggle', { layer, enabled });
  return res.data;
};

export const startAttack = async (attack_type) => {
  const res = await api.post('/attack/start', { attack_type, target: 'esp32' });
  return res.data;
};

export const getAttackProgress = async () => {
  const res = await api.get('/attack/progress');
  return res.data;
};

export const fetchAlerts = async () => {
  const res = await api.get('/alerts');
  return res.data.alerts;
};

// Return the WS URL for components to connect to
export const getWsUrl = () => {
  return `ws://localhost:8000/traces/live`;
};
