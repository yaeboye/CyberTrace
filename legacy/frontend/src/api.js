import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const api = axios.create({ baseURL: API_BASE });

export const fetchDefenseStatus = async () => (await api.get('/defense/status')).data;

export const toggleDefense = async (layer, enabled) =>
  (await api.post('/defense/toggle', { layer, enabled })).data;

export const startAttack = async (attack_type) =>
  (await api.post('/attack/start', { attack_type })).data;

export const getAttackProgress = async () => (await api.get('/attack/progress')).data;

export const fetchAlerts = async () => (await api.get('/alerts')).data.alerts;

export const fetchKeyHistory = async () => (await api.get('/key/history')).data.history;

export const rotateKey = async (reason = 'manual') =>
  (await api.post('/key/rotate', { reason })).data;

export const checkHealth = async () => (await api.get('/health')).data;
