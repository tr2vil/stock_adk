import { useState, useRef, useCallback, useEffect } from 'react';
import { analyzeStock } from '../services/api';

const useStockAnalysis = () => {
    const [ticker, setTicker] = useState('');
    const [market, setMarket] = useState('US');

    const [status, setStatus] = useState('idle'); // idle | loading | success | error
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    const timerRef = useRef(null);

    const analyze = useCallback(async () => {
        if (!ticker.trim()) return;

        setStatus('loading');
        setResult(null);
        setError(null);
        setElapsedSeconds(0);

        const startTime = Date.now();
        timerRef.current = setInterval(() => {
            setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
        }, 1000);

        try {
            const data = await analyzeStock(ticker.trim(), market);
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
    }, [ticker, market]);

    const reset = useCallback(() => {
        setStatus('idle');
        setResult(null);
        setError(null);
        setElapsedSeconds(0);
    }, []);

    useEffect(() => () => clearInterval(timerRef.current), []);

    return {
        ticker, setTicker,
        market, setMarket,
        status, result, error, elapsedSeconds,
        analyze, reset,
    };
};

export default useStockAnalysis;
