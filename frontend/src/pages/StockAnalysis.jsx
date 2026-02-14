import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Search, Loader2, AlertCircle, RefreshCw, TrendingUp, TrendingDown, Minus, Clock } from 'lucide-react';
import useStockAnalysis from '../hooks/useStockAnalysis';
import styles from './StockAnalysis.module.css';

const AGENT_STAGES = ['뉴스', '재무제표', '기술적 분석', '전문가 신호', '리스크'];

const extractAction = (markdown) => {
    if (!markdown) return null;
    const match = markdown.match(/\*\*Action\*\*:\s*(BUY|SELL|HOLD)/i);
    return match ? match[1].toUpperCase() : null;
};

const ActionBadge = ({ action }) => {
    if (!action) return null;
    const config = {
        BUY: { bg: 'bg-success', Icon: TrendingUp },
        SELL: { bg: 'bg-danger', Icon: TrendingDown },
        HOLD: { bg: 'bg-secondary', Icon: Minus },
    };
    const { bg, Icon } = config[action] || config.HOLD;
    return (
        <span className={`badge fs-6 ${bg}`}>
            <Icon size={16} className="me-1" />
            {action}
        </span>
    );
};

const AnalysisForm = ({ ticker, setTicker, market, setMarket, isLoading, onSubmit }) => (
    <div className={`card shadow-sm mb-4 ${styles.formCard}`}>
        <div className="card-body">
            <form onSubmit={onSubmit} className="d-flex align-items-end gap-3">
                <div className="flex-grow-1">
                    <label className="form-label fw-semibold">종목코드 / 종목명</label>
                    <input
                        type="text"
                        className="form-control form-control-lg"
                        value={ticker}
                        onChange={(e) => setTicker(e.target.value)}
                        placeholder="예: AAPL, 삼성전자, 005930"
                        disabled={isLoading}
                    />
                </div>
                <div style={{ width: '140px' }}>
                    <label className="form-label fw-semibold">시장</label>
                    <select
                        className="form-select form-select-lg"
                        value={market}
                        onChange={(e) => setMarket(e.target.value)}
                        disabled={isLoading}
                    >
                        <option value="US">US (미국)</option>
                        <option value="KR">KR (한국)</option>
                    </select>
                </div>
                <button
                    type="submit"
                    className="btn btn-primary btn-lg"
                    disabled={!ticker.trim() || isLoading}
                >
                    {isLoading
                        ? <Loader2 size={20} className={styles.spinner} />
                        : <Search size={20} />
                    }
                    <span className="ms-2">분석</span>
                </button>
            </form>
        </div>
    </div>
);

const LoadingIndicator = ({ elapsedSeconds }) => (
    <div className={`card shadow-sm ${styles.loadingCard}`}>
        <div className="card-body text-center py-5">
            <Loader2 size={48} className={`text-primary ${styles.spinner}`} />
            <h5 className="mt-3">5개 에이전트가 분석 중입니다...</h5>
            <p className="text-muted">
                <Clock size={16} className="me-1" />
                경과 시간: {elapsedSeconds}초 (보통 30초~2분 소요)
            </p>
            <div className={styles.stages}>
                {AGENT_STAGES.map((name) => (
                    <span key={name} className={`badge ${styles.stageBadge}`}>{name}</span>
                ))}
            </div>
        </div>
    </div>
);

const ErrorAlert = ({ error, onRetry }) => (
    <div className="alert alert-danger d-flex align-items-center">
        <AlertCircle size={20} className="me-2" />
        <span className="flex-grow-1">{error}</span>
        <button className="btn btn-outline-danger btn-sm ms-3" onClick={onRetry}>
            <RefreshCw size={16} className="me-1" /> 재시도
        </button>
    </div>
);

const AnalysisResult = ({ result, onReset }) => {
    const action = extractAction(result.result);
    return (
        <div className={`card shadow-sm ${styles.resultCard}`}>
            <div className={styles.resultHeader}>
                <div className="d-flex align-items-center justify-content-between">
                    <h5 className="mb-0">{result.ticker} ({result.market}) 분석 결과</h5>
                    <div className="d-flex align-items-center gap-2">
                        <ActionBadge action={action} />
                        <span className="text-muted small">
                            {(result.elapsed_ms / 1000).toFixed(1)}초 소요
                        </span>
                    </div>
                </div>
            </div>
            <div className={styles.resultBody}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {result.result}
                </ReactMarkdown>
            </div>
            <div className="card-footer text-end">
                <button className="btn btn-outline-primary" onClick={onReset}>
                    <RefreshCw size={16} className="me-1" /> 새 분석
                </button>
            </div>
        </div>
    );
};

const StockAnalysis = () => {
    const {
        ticker, setTicker,
        market, setMarket,
        status, result, error, elapsedSeconds,
        analyze, reset,
    } = useStockAnalysis();

    const handleSubmit = (e) => {
        e.preventDefault();
        analyze();
    };

    return (
        <div className="container-fluid px-4 py-3">
            <div className={styles.pageHeader}>
                <Search className="me-2" size={24} />
                <h4 className="mb-0">종목 분석</h4>
            </div>

            <AnalysisForm
                ticker={ticker}
                setTicker={setTicker}
                market={market}
                setMarket={setMarket}
                isLoading={status === 'loading'}
                onSubmit={handleSubmit}
            />

            {status === 'loading' && <LoadingIndicator elapsedSeconds={elapsedSeconds} />}
            {status === 'error' && <ErrorAlert error={error} onRetry={analyze} />}
            {status === 'success' && result && <AnalysisResult result={result} onReset={reset} />}
        </div>
    );
};

export default StockAnalysis;
