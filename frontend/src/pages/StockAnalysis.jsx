import { useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Search, Loader2, AlertCircle, RefreshCw, TrendingUp, TrendingDown, Minus, Clock, X } from 'lucide-react';
import useStockAnalysis from '../hooks/useStockAnalysis';
import styles from './StockAnalysis.module.css';

const AGENT_STAGES = ['뉴스', '재무제표', '기술적 분석', '전문가 신호', '리스크'];

const extractAction = (markdown) => {
    if (!markdown) return null;
    const match = markdown.match(/\*\*Action\*\*:\s*(BUY|SELL|HOLD)/i);
    return match ? match[1].toUpperCase() : null;
};

const timeAgo = (timestamp) => {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return '방금 전';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}분 전`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}시간 전`;
    const days = Math.floor(hours / 24);
    return `${days}일 전`;
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

const AnalysisForm = ({ query, setQuery, isLoading, onSubmit, resolved }) => (
    <div className={`card shadow-sm mb-4 ${styles.formCard}`}>
        <div className="card-body">
            <form onSubmit={onSubmit} className="d-flex align-items-end gap-3">
                <div className="flex-grow-1">
                    <label className="form-label fw-semibold">종목코드 / 종목명</label>
                    <input
                        type="text"
                        className="form-control form-control-lg"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="예: AAPL, 테슬라, 삼성전자, 005930"
                        disabled={isLoading}
                    />
                </div>
                <button
                    type="submit"
                    className="btn btn-primary btn-lg"
                    disabled={!query.trim() || isLoading}
                >
                    {isLoading
                        ? <Loader2 size={20} className={styles.spinner} />
                        : <Search size={20} />
                    }
                    <span className="ms-2">분석</span>
                </button>
            </form>
            {resolved && (
                <div className="mt-2">
                    <span className="badge bg-info me-1">{resolved.market}</span>
                    <span className="text-muted small">
                        {resolved.company_name} ({resolved.ticker})
                    </span>
                </div>
            )}
        </div>
    </div>
);

const RecentSearches = ({ history, onSelect, onRemove }) => {
    if (!history.length) return null;

    return (
        <div className={`card shadow-sm mb-4 ${styles.recentSection}`}>
            <div className={styles.recentHeader}>
                <Clock size={16} className="me-1" />
                <span className="fw-semibold">최근 검색</span>
            </div>
            <div className="card-body p-3">
                <div className={styles.recentList}>
                    {history.map((item) => (
                        <div
                            key={item.ticker}
                            className={styles.recentItem}
                            onClick={() => onSelect(item)}
                        >
                            <div className={styles.recentInfo}>
                                <span className={`badge ${item.market === 'KR' ? 'bg-primary' : 'bg-dark'} me-2`}>
                                    {item.market}
                                </span>
                                <span className={styles.recentName}>{item.company_name}</span>
                                <span className={styles.recentTicker}>({item.ticker})</span>
                            </div>
                            <div className={styles.recentMeta}>
                                <span className={styles.recentTime}>{timeAgo(item.timestamp)}</span>
                                <button
                                    className={styles.recentRemove}
                                    onClick={(e) => { e.stopPropagation(); onRemove(item.ticker); }}
                                    title="삭제"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

const ResolvingIndicator = () => (
    <div className={`card shadow-sm ${styles.loadingCard}`}>
        <div className="card-body text-center py-4">
            <Loader2 size={32} className={`text-primary ${styles.spinner}`} />
            <h6 className="mt-3 mb-0">종목을 검색하고 있습니다...</h6>
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
        query, setQuery,
        resolved,
        status, result, error, elapsedSeconds,
        history, removeHistory,
        analyze, reset,
    } = useStockAnalysis();

    const handleSubmit = (e) => {
        e.preventDefault();
        analyze();
    };

    const handleSelectHistory = useCallback((item) => {
        setQuery(item.query);
        // Use setTimeout to let setQuery update before analyze reads it
        setTimeout(() => {
            setQuery(item.query);
        }, 0);
    }, [setQuery]);

    const isLoading = status === 'resolving' || status === 'loading';

    return (
        <div className="container-fluid px-4 py-3">
            <div className={styles.pageHeader}>
                <Search className="me-2" size={24} />
                <h4 className="mb-0">종목 분석</h4>
            </div>

            <AnalysisForm
                query={query}
                setQuery={setQuery}
                isLoading={isLoading}
                onSubmit={handleSubmit}
                resolved={resolved}
            />

            {status === 'idle' && (
                <RecentSearches
                    history={history}
                    onSelect={handleSelectHistory}
                    onRemove={removeHistory}
                />
            )}

            {status === 'resolving' && <ResolvingIndicator />}
            {status === 'loading' && <LoadingIndicator elapsedSeconds={elapsedSeconds} />}
            {status === 'error' && <ErrorAlert error={error} onRetry={analyze} />}
            {status === 'success' && result && <AnalysisResult result={result} onReset={reset} />}
        </div>
    );
};

export default StockAnalysis;
