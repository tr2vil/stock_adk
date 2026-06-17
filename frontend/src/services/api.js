import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 180000,
});

export const analyzeStock = (ticker, market) =>
    api.post('/api/analyze', { ticker, market }).then(res => res.data);

export const resolveTicker = (query) =>
    api.post('/api/resolve-ticker', { query }).then(res => res.data);

export const healthCheck = () =>
    api.get('/api/health').then(res => res.data);

// 포트폴리오 (토스 보유종목 / 캔들차트)
export const getHoldings = () =>
    api.get('/api/holdings').then(res => res.data);

export const getCandles = (symbol, count = 90, interval = '1d') =>
    api.get(`/api/candles/${symbol}`, { params: { count, interval } }).then(res => res.data);

// 스윙 밴드 전략 (Phase 1)
export const getWatchlist = () =>
    api.get('/api/watchlist').then(res => res.data);

export const putWatchlist = (watchlist) =>
    api.put('/api/watchlist', { watchlist }).then(res => res.data);

export const getStrategyConfig = (symbol) =>
    api.get('/api/strategy/config', { params: symbol ? { symbol } : {} }).then(res => res.data);

export const putStrategyConfig = (scope, config) =>
    api.put('/api/strategy/config', { scope, config }).then(res => res.data);

export const getStrategyPlans = () =>
    api.get('/api/strategy/plans').then(res => res.data);

export const strategyAnalyze = (symbol, market, name) =>
    api.post('/api/strategy/analyze', { symbol, market, name }).then(res => res.data);

export const strategyApprove = (symbol, target_price, buy_anchor) =>
    api.post('/api/strategy/approve', { symbol, target_price, buy_anchor }).then(res => res.data);

export const strategyDeactivate = (symbol) =>
    api.delete(`/api/strategy/plans/${symbol}`).then(res => res.data);

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
