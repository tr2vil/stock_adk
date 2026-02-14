import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 180000,
});

export const analyzeStock = (ticker, market) =>
    api.post('/api/analyze', { ticker, market }).then(res => res.data);

export const healthCheck = () =>
    api.get('/api/health').then(res => res.data);

// ── Prompt Management ──

export const getPrompts = () =>
    api.get('/api/prompts').then(res => res.data);

export const getPrompt = (agentName) =>
    api.get(`/api/prompts/${agentName}`).then(res => res.data);

export const updatePrompt = (agentName, prompt) =>
    api.put(`/api/prompts/${agentName}`, { prompt }).then(res => res.data);

// ── Weights / Thresholds ──

export const getWeights = () =>
    api.get('/api/weights').then(res => res.data);

export const updateWeights = (weights) =>
    api.put('/api/weights', { weights }).then(res => res.data);

export const updateThresholds = (thresholds) =>
    api.put('/api/thresholds', { thresholds }).then(res => res.data);

export default api;
