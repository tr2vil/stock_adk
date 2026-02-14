import { useState, useRef, useCallback, useEffect } from 'react';
import { analyzeStock, resolveTicker } from '../services/api';

const HISTORY_KEY = 'stock_analysis_history';
const MAX_HISTORY = 10;

const loadHistory = () => {
    try {
        return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    } catch {
        return [];
    }
};

const saveHistory = (entry) => {
    const history = loadHistory();
    // Remove duplicate (same ticker)
    const filtered = history.filter(h => h.ticker !== entry.ticker);
    const updated = [entry, ...filtered].slice(0, MAX_HISTORY);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
    return updated;
};

const useStockAnalysis = () => {
    const [query, setQuery] = useState('');

    const [status, setStatus] = useState('idle'); // idle | resolving | loading | success | error
    const [resolved, setResolved] = useState(null); // { ticker, market, company_name }
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const [history, setHistory] = useState(loadHistory);

    const timerRef = useRef(null);

    const analyze = useCallback(async () => {
        if (!query.trim()) return;

        setStatus('resolving');
        setResult(null);
        setResolved(null);
        setError(null);
        setElapsedSeconds(0);

        // Step 1: Resolve ticker
        let tickerInfo;
        try {
            tickerInfo = await resolveTicker(query.trim());
            setResolved(tickerInfo);
        } catch (err) {
            setError(
                err.response?.data?.detail || '종목을 찾을 수 없습니다. 종목명 또는 티커를 확인해주세요.'
            );
            setStatus('error');
            return;
        }

        // Save to history
        const updated = saveHistory({
            ticker: tickerInfo.ticker,
            market: tickerInfo.market,
            company_name: tickerInfo.company_name,
            query: query.trim(),
            timestamp: Date.now(),
        });
        setHistory(updated);

        // Step 2: Analyze with resolved ticker + market
        setStatus('loading');
        const startTime = Date.now();
        timerRef.current = setInterval(() => {
            setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
        }, 1000);

        try {
            const data = await analyzeStock(tickerInfo.ticker, tickerInfo.market);
            setResult(data);
            setStatus('success');
        } catch (err) {
            setError(
                err.response?.data?.detail || err.message || '분석 중 오류가 발생했습니다.'
            );
            setStatus('error');
        } finally {
            clearInterval(timerRef.current);
        }
    }, [query]);

    const reset = useCallback(() => {
        setStatus('idle');
        setResult(null);
        setResolved(null);
        setError(null);
        setElapsedSeconds(0);
    }, []);

    const removeHistory = useCallback((ticker) => {
        const updated = loadHistory().filter(h => h.ticker !== ticker);
        localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
        setHistory(updated);
    }, []);

    useEffect(() => () => clearInterval(timerRef.current), []);

    return {
        query, setQuery,
        resolved,
        status, result, error, elapsedSeconds,
        history, removeHistory,
        analyze, reset,
    };
};

export default useStockAnalysis;
