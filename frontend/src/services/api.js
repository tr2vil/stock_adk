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

export default api;
