import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { createChart } from 'lightweight-charts';
import { Briefcase, Loader2, AlertCircle, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { getHoldings, getCandles, analyzeStock } from '../services/api';

const fmt = (n, currency = 'KRW') => {
    const v = Number(n);
    if (Number.isNaN(v)) return '-';
    return currency === 'USD'
        ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
        : `₩${Math.round(v).toLocaleString()}`;
};

const pct = (rate) => {
    const v = Number(rate) * 100;
    if (Number.isNaN(v)) return '-';
    return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
};

// 캔들차트 (lightweight-charts)
const CandleChart = ({ candles }) => {
    const containerRef = useRef(null);

    useEffect(() => {
        if (!containerRef.current || !candles.length) return;
        const chart = createChart(containerRef.current, {
            height: 320,
            layout: { background: { color: '#ffffff' }, textColor: '#333' },
            grid: { vertLines: { color: '#f0f0f0' }, horzLines: { color: '#f0f0f0' } },
            timeScale: { timeVisible: false, borderColor: '#ddd' },
            rightPriceScale: { borderColor: '#ddd' },
        });
        const series = chart.addCandlestickSeries({
            upColor: '#e03131', downColor: '#1971c2',       // 한국식: 상승 빨강 / 하락 파랑
            borderUpColor: '#e03131', borderDownColor: '#1971c2',
            wickUpColor: '#e03131', wickDownColor: '#1971c2',
        });
        // Toss는 최신순 → 시간 오름차순으로 정렬, 날짜 문자열(YYYY-MM-DD)로 변환
        const data = candles
            .map((c) => ({
                time: c.timestamp.slice(0, 10),
                open: parseFloat(c.openPrice),
                high: parseFloat(c.highPrice),
                low: parseFloat(c.lowPrice),
                close: parseFloat(c.closePrice),
            }))
            .sort((a, b) => (a.time < b.time ? -1 : 1));
        series.setData(data);
        chart.timeScale().fitContent();

        const onResize = () => chart.applyOptions({ width: containerRef.current.clientWidth });
        onResize();
        window.addEventListener('resize', onResize);
        return () => { window.removeEventListener('resize', onResize); chart.remove(); };
    }, [candles]);

    return <div ref={containerRef} style={{ width: '100%' }} />;
};

const Portfolio = () => {
    const [holdings, setHoldings] = useState(null);   // {items, marketValue, profitLoss, ...}
    const [loadErr, setLoadErr] = useState(null);
    const [selected, setSelected] = useState(null);   // holding item
    const [candles, setCandles] = useState([]);
    const [chartLoading, setChartLoading] = useState(false);
    const [report, setReport] = useState(null);
    const [reportStatus, setReportStatus] = useState('idle'); // idle|loading|error
    const [reportErr, setReportErr] = useState(null);

    const loadHoldings = useCallback(() => {
        setLoadErr(null);
        getHoldings()
            .then(setHoldings)
            .catch((e) => setLoadErr(e.response?.data?.detail || '보유종목 조회 실패'));
    }, []);

    useEffect(() => { loadHoldings(); }, [loadHoldings]);

    const selectItem = useCallback((item) => {
        setSelected(item);
        setReport(null);
        setReportStatus('idle');
        setChartLoading(true);
        setCandles([]);
        getCandles(item.symbol, 90)
            .then((d) => setCandles(d.candles || []))
            .catch(() => setCandles([]))
            .finally(() => setChartLoading(false));
    }, []);

    const runReport = useCallback(() => {
        if (!selected) return;
        setReportStatus('loading');
        setReportErr(null);
        analyzeStock(selected.symbol, selected.marketCountry || 'KR')
            .then((d) => { setReport(d.result); setReportStatus('idle'); })
            .catch((e) => { setReportErr(e.response?.data?.detail || '분석 실패'); setReportStatus('error'); });
    }, [selected]);

    const items = holdings?.items || [];
    const totalRate = holdings?.profitLoss?.rate;
    const totalKrw = holdings?.marketValue?.amount?.krw;

    return (
        <div className="container-fluid px-4 py-3">
            <div className="d-flex align-items-center mb-3">
                <Briefcase className="me-2" size={24} />
                <h4 className="mb-0">포트폴리오 (토스 보유종목)</h4>
                <button className="btn btn-outline-secondary btn-sm ms-auto" onClick={loadHoldings}>
                    <RefreshCw size={16} className="me-1" /> 새로고침
                </button>
            </div>

            {loadErr && (
                <div className="alert alert-danger d-flex align-items-center">
                    <AlertCircle size={20} className="me-2" />
                    <span className="flex-grow-1">{loadErr}</span>
                    <button className="btn btn-outline-danger btn-sm" onClick={loadHoldings}>재시도</button>
                </div>
            )}

            {!holdings && !loadErr && (
                <div className="text-center py-5"><Loader2 size={36} className="text-primary" /></div>
            )}

            {holdings && (
                <>
                    {/* 요약 */}
                    <div className="card shadow-sm mb-3">
                        <div className="card-body d-flex flex-wrap gap-4">
                            <div>
                                <div className="text-muted small">총 평가금액</div>
                                <div className="fs-5 fw-bold">{fmt(totalKrw)}</div>
                            </div>
                            <div>
                                <div className="text-muted small">총 손익률</div>
                                <div className={`fs-5 fw-bold ${Number(totalRate) >= 0 ? 'text-danger' : 'text-primary'}`}>
                                    {pct(totalRate)}
                                </div>
                            </div>
                            <div>
                                <div className="text-muted small">보유 종목수</div>
                                <div className="fs-5 fw-bold">{items.length}</div>
                            </div>
                        </div>
                    </div>

                    <div className="row g-3">
                        {/* 보유종목 리스트 */}
                        <div className="col-lg-5">
                            <div className="card shadow-sm">
                                <div className="table-responsive" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                                    <table className="table table-hover mb-0 align-middle">
                                        <thead className="table-light sticky-top">
                                            <tr>
                                                <th>종목</th>
                                                <th className="text-end">수량</th>
                                                <th className="text-end">현재가</th>
                                                <th className="text-end">수익률</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {items.map((it) => {
                                                const r = Number(it.profitLoss?.rate);
                                                const active = selected?.symbol === it.symbol;
                                                return (
                                                    <tr
                                                        key={it.symbol}
                                                        onClick={() => selectItem(it)}
                                                        style={{ cursor: 'pointer' }}
                                                        className={active ? 'table-active' : ''}
                                                    >
                                                        <td>
                                                            <div className="fw-semibold">{it.name}</div>
                                                            <div className="text-muted small">{it.symbol} · {it.marketCountry}</div>
                                                        </td>
                                                        <td className="text-end">{Number(it.quantity).toLocaleString()}</td>
                                                        <td className="text-end">{fmt(it.lastPrice, it.currency)}</td>
                                                        <td className={`text-end fw-semibold ${r >= 0 ? 'text-danger' : 'text-primary'}`}>
                                                            {r >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />} {pct(it.profitLoss?.rate)}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        {/* 선택 종목 상세: 차트 + 리포트 */}
                        <div className="col-lg-7">
                            {!selected && (
                                <div className="card shadow-sm">
                                    <div className="card-body text-center text-muted py-5">
                                        왼쪽에서 종목을 선택하면 차트와 분석 리포트를 볼 수 있습니다.
                                    </div>
                                </div>
                            )}
                            {selected && (
                                <div className="card shadow-sm">
                                    <div className="card-header d-flex align-items-center justify-content-between">
                                        <div>
                                            <span className="fw-bold">{selected.name}</span>
                                            <span className="text-muted small ms-2">{selected.symbol}</span>
                                        </div>
                                        <div className="small text-muted">
                                            평단 {fmt(selected.averagePurchasePrice, selected.currency)} · 현재 {fmt(selected.lastPrice, selected.currency)}
                                        </div>
                                    </div>
                                    <div className="card-body">
                                        {chartLoading
                                            ? <div className="text-center py-5"><Loader2 size={32} className="text-primary" /></div>
                                            : candles.length
                                                ? <CandleChart candles={candles} />
                                                : <div className="text-muted text-center py-4">차트 데이터가 없습니다.</div>}

                                        <hr />
                                        <div className="d-flex align-items-center mb-2">
                                            <h6 className="mb-0">분석 리포트</h6>
                                            <button
                                                className="btn btn-primary btn-sm ms-auto"
                                                onClick={runReport}
                                                disabled={reportStatus === 'loading'}
                                            >
                                                {reportStatus === 'loading'
                                                    ? <><Loader2 size={16} className="me-1" /> 분석 중... (~1-2분)</>
                                                    : <><RefreshCw size={16} className="me-1" /> 분석 실행</>}
                                            </button>
                                        </div>
                                        {reportStatus === 'error' && (
                                            <div className="alert alert-danger py-2">{reportErr}</div>
                                        )}
                                        {report && (
                                            <div className="border rounded p-3 bg-light" style={{ maxHeight: '40vh', overflowY: 'auto' }}>
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default Portfolio;
