import { useState, useEffect, useCallback, useRef } from 'react';
import {
    Search, Plus, Trash2, Loader2, RefreshCw,
    Activity, Play, Square, TrendingUp, TrendingDown,
    CheckCircle, AlertCircle, MinusCircle, BarChart2,
} from 'lucide-react';
import {
    getWatchlist, putWatchlist,
    getWatcherStatus, startWatcher, stopWatcher,
    checkScreener, getPortfolioStrategyFit, getSignalStates,
    getTradingBudget, setTradingBudget,
} from '../services/api';

// ── 유틸 ─────────────────────────────────────────────────────────────────────

const usd = (n, digits = 2) => {
    if (n == null) return '-';
    return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
};
const fmtCap = (v) => {
    if (v == null) return '-';
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    return `$${(v / 1e6).toFixed(0)}M`;
};
const fmtFloat = (v) => {
    if (v == null) return '-';
    if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M주`;
    return `${v.toLocaleString()}주`;
};
const pct = (v) => v == null ? '-' : `${(v * 100).toFixed(1)}%`;

const FIT_BADGE = {
    fit: <span className="badge bg-success">✅ 적합</span>,
    border: <span className="badge bg-warning text-dark">🟡 경계</span>,
    reject: <span className="badge bg-danger">❌ 부적합</span>,
};

const STATE_LABEL = {
    IDLE: { text: '대기', color: 'secondary' },
    M1_QUEUED_RSI_LOW: { text: 'RSI 50 돌파 대기', color: 'info' },
    M1_QUEUED_RSI_HIGH: { text: '눌림목 대기', color: 'info' },
    M1_OPEN_FIRST: { text: '보유 (1차 목표 대기)', color: 'primary' },
    M1_OPEN_SECOND: { text: '잔량 보유', color: 'primary' },
    M2_DIVERGENCE: { text: '다이버전스 감지', color: 'warning' },
    M2_COOLDOWN: { text: '조정 중 (재진입 대기)', color: 'warning' },
    M2_OPEN: { text: '보유 (전량 청산 대기)', color: 'primary' },
};

// ── 가격 워처 패널 ────────────────────────────────────────────────────────────

const WatcherBar = () => {
    const [status, setStatus] = useState(null);
    const [busy, setBusy] = useState(false);

    const refresh = useCallback(async () => {
        try { setStatus(await getWatcherStatus()); } catch { /* noop */ }
    }, []);

    useEffect(() => {
        refresh();
        const t = setInterval(refresh, 15000);
        return () => clearInterval(t);
    }, [refresh]);

    const toggle = async () => {
        setBusy(true);
        try {
            if (status?.running) await stopWatcher();
            else await startWatcher();
            await refresh();
        } finally { setBusy(false); }
    };

    const running = status?.running;

    return (
        <div className="card shadow-sm mb-3">
            <div className="card-body d-flex flex-wrap align-items-center gap-2 py-2">
                <Activity size={16} className={running ? 'text-success' : 'text-muted'} />
                <span className="fw-semibold small">워처</span>
                <span className={`badge ${running ? 'bg-success' : 'bg-secondary'}`}>
                    {running ? '동작 중 (5분 폴링)' : '중지됨'}
                </span>
                {status?.markets && (
                    <span className={`badge ${status.markets.US ? 'bg-info' : 'bg-light text-dark'}`}>
                        US {status.markets.US ? '🟢 개장' : '🔴 폐장'}
                    </span>
                )}
                {status && (
                    <span className={`badge ${status.dry_run ? 'bg-warning text-dark' : 'bg-danger'}`}>
                        {status.dry_run ? 'DRY_RUN' : '실거래'}
                    </span>
                )}
                {status?.next_run && (
                    <span className="text-muted small">다음 {new Date(status.next_run).toLocaleTimeString()}</span>
                )}
                <button
                    className={`btn btn-sm ms-auto ${running ? 'btn-outline-danger' : 'btn-success'}`}
                    onClick={toggle} disabled={busy}
                >
                    {busy ? <Loader2 size={13} className="me-1" /> : running ? <Square size={13} className="me-1" /> : <Play size={13} className="me-1" />}
                    {running ? '중지' : '시작'}
                </button>
            </div>
            {status?.last_tick?.status && (
                <div className="card-footer py-1 small text-muted">
                    최근 tick: {status.last_tick.status}
                    {status.last_tick.evaluated != null && ` · ${status.last_tick.evaluated}종목 평가`}
                    {status.last_tick.fills != null && ` · ${status.last_tick.fills}건 발주`}
                </div>
            )}
        </div>
    );
};

// ── 탭 1: 종목 스캐너 ─────────────────────────────────────────────────────────

const ScannerTab = ({ onAddToWatchlist }) => {
    const [input, setInput] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [budget, setBudget] = useState(null);
    const [addModal, setAddModal] = useState(null);  // { symbol, company_name, current_price }
    const [modalBudget, setModalBudget] = useState('');
    const [err, setErr] = useState('');

    useEffect(() => {
        getTradingBudget().then(setBudget).catch(() => {});
    }, []);

    const scan = async () => {
        const symbols = input.split(/[\s,]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
        if (!symbols.length) return;
        setLoading(true);
        setErr('');
        try {
            const data = await checkScreener(symbols);
            setResults(data.results || []);
        } catch (e) {
            setErr(e.response?.data?.detail || '스캔 실패');
        } finally {
            setLoading(false);
        }
    };

    const openAddModal = (r) => {
        setAddModal(r);
        setModalBudget('');
    };

    const confirmAdd = async () => {
        if (!addModal) return;
        const budgetVal = parseFloat(modalBudget);
        if (!budgetVal || budgetVal <= 0) return;
        await onAddToWatchlist({ symbol: addModal.symbol, market: 'US', name: addModal.company_name || addModal.symbol, budget_usd: budgetVal });
        setAddModal(null);
        const b = await getTradingBudget();
        setBudget(b);
    };

    const available = budget ? Math.max(0, budget.total_budget_usd - budget.allocated_usd) : null;
    const modalQty = addModal && parseFloat(modalBudget) > 0 && addModal.current_price
        ? Math.floor(parseFloat(modalBudget) / addModal.current_price)
        : 0;

    return (
        <div>
            {/* 예산 현황 */}
            {budget && (
                <div className="alert alert-light border d-flex gap-3 align-items-center mb-3 py-2">
                    <BarChart2 size={16} className="text-primary" />
                    <span className="small">
                        총 예산 <strong>{usd(budget.total_budget_usd)}</strong>
                        &nbsp;·&nbsp;배분됨 <strong className="text-danger">{usd(budget.allocated_usd)}</strong>
                        &nbsp;·&nbsp;잔여 <strong className="text-success">{usd(available)}</strong>
                    </span>
                </div>
            )}

            {/* 검색 입력 */}
            <div className="card shadow-sm mb-3">
                <div className="card-body">
                    <label className="form-label small fw-semibold mb-1">
                        티커 입력 <span className="text-muted fw-normal">(쉼표 또는 공백으로 구분, 최대 20개)</span>
                    </label>
                    <div className="d-flex gap-2">
                        <input
                            className="form-control"
                            placeholder="예: CRWD, BOOT, AAON, SMCI"
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && scan()}
                        />
                        <button className="btn btn-primary px-4" onClick={scan} disabled={loading}>
                            {loading ? <Loader2 size={15} className="me-1" /> : <Search size={15} className="me-1" />}
                            {loading ? '조회 중...' : '검사'}
                        </button>
                    </div>
                    {err && <div className="text-danger small mt-1">{err}</div>}
                    <div className="text-muted small mt-2">
                        유니버스 기준: 시가총액 $300M~$2B · Float 100M주 이하 · 상대거래량 1.5x↑ · 시가갭 +4%↑
                    </div>
                </div>
            </div>

            {/* 결과 테이블 */}
            {results.length > 0 && (
                <div className="card shadow-sm">
                    <div className="table-responsive">
                        <table className="table table-hover table-sm mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th>종목</th>
                                    <th>현재가</th>
                                    <th>시가총액</th>
                                    <th>Float</th>
                                    <th>상대거래량</th>
                                    <th>갭</th>
                                    <th>판정</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.map(r => (
                                    <tr key={r.symbol}>
                                        <td>
                                            <span className="fw-bold">{r.symbol}</span>
                                            {r.company_name && <div className="text-muted" style={{ fontSize: 11 }}>{r.company_name}</div>}
                                        </td>
                                        <td>{usd(r.current_price)}</td>
                                        <td>{fmtCap(r.market_cap)}</td>
                                        <td>{fmtFloat(r.float_shares)}</td>
                                        <td>{r.rel_volume != null ? `${r.rel_volume.toFixed(1)}x` : '-'}</td>
                                        <td>{r.gap_pct != null ? `${(r.gap_pct * 100).toFixed(1)}%` : '-'}</td>
                                        <td>
                                            {FIT_BADGE[r.fit] || FIT_BADGE.reject}
                                            {(r.reasons?.length > 0 || r.border_reasons?.length > 0) && (
                                                <div className="text-muted" style={{ fontSize: 10 }}>
                                                    {[...(r.reasons || []), ...(r.border_reasons || [])].join(' / ')}
                                                </div>
                                            )}
                                        </td>
                                        <td>
                                            {r.fit !== 'reject' && (
                                                <button className="btn btn-sm btn-outline-primary" onClick={() => openAddModal(r)}>
                                                    <Plus size={13} className="me-1" />추가
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* 종목 추가 모달 */}
            {addModal && (
                <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.4)' }}>
                    <div className="modal-dialog modal-dialog-centered">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h6 className="modal-title">
                                    <Plus size={16} className="me-1" />
                                    {addModal.symbol} 워치리스트 추가
                                </h6>
                                <button className="btn-close" onClick={() => setAddModal(null)} />
                            </div>
                            <div className="modal-body">
                                <div className="d-flex justify-content-between mb-3 text-sm">
                                    <span className="text-muted">총 예산</span>
                                    <strong>{usd(budget?.total_budget_usd)}</strong>
                                </div>
                                <div className="d-flex justify-content-between mb-3">
                                    <span className="text-muted">이미 배분된 금액</span>
                                    <strong className="text-danger">{usd(budget?.allocated_usd)}</strong>
                                </div>
                                <div className="d-flex justify-content-between mb-3">
                                    <span className="text-muted">배분 가능 잔여</span>
                                    <strong className="text-success">{usd(available)}</strong>
                                </div>
                                <hr />
                                <label className="form-label fw-semibold">이 종목 배분 금액 (USD)</label>
                                <div className="input-group">
                                    <span className="input-group-text">$</span>
                                    <input
                                        type="number"
                                        className="form-control"
                                        min="1"
                                        max={available || 99999}
                                        placeholder="예: 500"
                                        value={modalBudget}
                                        onChange={e => setModalBudget(e.target.value)}
                                        autoFocus
                                    />
                                </div>
                                {addModal.current_price && modalBudget > 0 && (
                                    <div className="text-muted small mt-2">
                                        현재가 {usd(addModal.current_price)} 기준 매수 수량: <strong>{modalQty}주</strong>
                                        {addModal.stop_loss && (
                                            <span className="ms-2">· 손절 예상 ~{usd(addModal.stop_loss)}</span>
                                        )}
                                    </div>
                                )}
                                {parseFloat(modalBudget) > (available || 0) && (
                                    <div className="text-danger small mt-1">⚠ 배분 가능 금액 초과</div>
                                )}
                            </div>
                            <div className="modal-footer">
                                <button className="btn btn-secondary" onClick={() => setAddModal(null)}>취소</button>
                                <button
                                    className="btn btn-primary"
                                    onClick={confirmAdd}
                                    disabled={!modalBudget || parseFloat(modalBudget) <= 0 || parseFloat(modalBudget) > (available || 0)}
                                >
                                    <Plus size={14} className="me-1" />추가
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// ── 탭 2: 보유종목 적합성 ─────────────────────────────────────────────────────

const FitTab = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);

    const load = async () => {
        setLoading(true);
        try { setData(await getPortfolioStrategyFit()); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const { fit = 0, border = 0, reject = 0 } = data?.summary || {};
    const total = fit + border + reject;

    return (
        <div>
            <div className="d-flex align-items-center mb-3 gap-2">
                <span className="text-muted small">Toss 보유종목 기준, yfinance 데이터 조회</span>
                <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={load} disabled={loading}>
                    {loading ? <Loader2 size={13} /> : <RefreshCw size={13} />}
                </button>
            </div>

            {loading && <div className="text-center py-5"><Loader2 size={32} className="text-primary" /></div>}

            {!loading && data && (
                <>
                    {/* 요약 */}
                    <div className="row g-2 mb-3">
                        <div className="col-4">
                            <div className="card text-center py-2 border-success">
                                <div className="fs-4 fw-bold text-success">{fit}</div>
                                <div className="small text-muted">✅ 적합</div>
                            </div>
                        </div>
                        <div className="col-4">
                            <div className="card text-center py-2 border-warning">
                                <div className="fs-4 fw-bold text-warning">{border}</div>
                                <div className="small text-muted">🟡 경계</div>
                            </div>
                        </div>
                        <div className="col-4">
                            <div className="card text-center py-2 border-danger">
                                <div className="fs-4 fw-bold text-danger">{reject}</div>
                                <div className="small text-muted">❌ 부적합</div>
                            </div>
                        </div>
                    </div>

                    {/* 종목 테이블 */}
                    {data.holdings?.length > 0 ? (
                        <div className="card shadow-sm">
                            <div className="table-responsive">
                                <table className="table table-sm table-hover mb-0">
                                    <thead className="table-light">
                                        <tr>
                                            <th>종목</th>
                                            <th>보유금액</th>
                                            <th>시가총액</th>
                                            <th>Float</th>
                                            <th>판정</th>
                                            <th>사유</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.holdings.map(r => (
                                            <tr key={r.symbol}>
                                                <td>
                                                    <strong>{r.symbol}</strong>
                                                    {r.company_name && <div className="text-muted" style={{ fontSize: 11 }}>{r.company_name}</div>}
                                                </td>
                                                <td>{r.holding_value ? usd(r.holding_value) : '-'}</td>
                                                <td>{fmtCap(r.market_cap)}</td>
                                                <td>{fmtFloat(r.float_shares)}</td>
                                                <td>{FIT_BADGE[r.fit] || FIT_BADGE.reject}</td>
                                                <td className="text-muted small">
                                                    {[...(r.reasons || []), ...(r.border_reasons || [])].join(' / ') || '-'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="alert alert-info">보유종목 없음 또는 Toss API 미연결</div>
                    )}

                    {fit === 0 && total > 0 && (
                        <div className="alert alert-warning mt-3 mb-0">
                            💡 현재 보유종목은 MACD+RSI 소형주 전략 대상이 아닙니다.
                            <strong> 스캐너 탭</strong>에서 소형주를 직접 입력해 추가하세요.
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

// ── 탭 3: 신호 모니터 ─────────────────────────────────────────────────────────

const SignalMonitor = ({ watchlist, onRemove }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try { setData(await getSignalStates()); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => {
        load();
        const t = setInterval(load, 30000);
        return () => clearInterval(t);
    }, [load]);

    if (loading && !data) return <div className="text-center py-5"><Loader2 size={32} className="text-primary" /></div>;

    const signals = data?.signals || [];
    const strat = data?.strategy || {};

    return (
        <div>
            {/* 전략 파라미터 요약 */}
            {data && (
                <div className="alert alert-light border-0 bg-light small mb-3 d-flex flex-wrap gap-3">
                    <span>전략 <strong>v{data.strategy_version}</strong></span>
                    <span>MACD {strat.macd?.fast}/{strat.macd?.slow}/{strat.macd?.signal}</span>
                    <span>RSI 매수 {strat.rsi?.buy_low}~{strat.rsi?.buy_high}</span>
                    <span>HMA({strat.hma_filter?.period}) {strat.hma_filter?.timeframe} 필터</span>
                    <button className="btn btn-sm btn-link p-0 ms-auto" onClick={load} disabled={loading}>
                        <RefreshCw size={13} />
                    </button>
                </div>
            )}

            {signals.length === 0 && (
                <div className="alert alert-info">
                    워치리스트가 비어 있습니다. 스캐너 탭에서 종목을 추가하세요.
                </div>
            )}

            {signals.map(s => {
                const st = STATE_LABEL[s.signal_state] || { text: s.signal_state, color: 'secondary' };
                const hasPosition = ['M1_OPEN_FIRST', 'M1_OPEN_SECOND', 'M2_OPEN'].includes(s.signal_state);
                const progress = hasPosition && s.entry_price && s.target1
                    ? Math.min(100, Math.max(0, ((s.entry_price - s.stop_loss) / (s.target1 - s.stop_loss)) * 100))
                    : null;

                return (
                    <div key={s.symbol} className="card shadow-sm mb-2">
                        <div className="card-body py-2">
                            <div className="d-flex align-items-center gap-2 mb-1">
                                <span className="fw-bold">{s.symbol}</span>
                                <span className="text-muted small">{s.name !== s.symbol ? s.name : ''}</span>
                                <span className={`badge bg-${st.color} ms-1`}>{st.text}</span>
                                {s.budget_usd > 0 && (
                                    <span className="badge bg-light text-dark border ms-1">예산 {usd(s.budget_usd)}</span>
                                )}
                                <button
                                    className="btn btn-sm btn-link text-danger p-0 ms-auto"
                                    onClick={() => onRemove(s.symbol)}
                                    title="워치리스트에서 제거"
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>

                            {hasPosition && (
                                <div className="small mb-1">
                                    <span className="text-muted me-2">
                                        진입 {usd(s.entry_price)} &nbsp;│&nbsp; SL {usd(s.stop_loss)} &nbsp;│&nbsp;
                                        {s.signal_state === 'M1_OPEN_SECOND' ? '잔량 목표' : '목표'} {usd(s.target1)}
                                    </span>
                                    {s.signal_state === 'M1_OPEN_FIRST' && progress != null && (
                                        <div className="progress mt-1" style={{ height: 4 }}>
                                            <div
                                                className="progress-bar bg-success"
                                                style={{ width: `${progress}%` }}
                                                title={`목표까지 ${Math.round(progress)}%`}
                                            />
                                        </div>
                                    )}
                                    {s.signal_state === 'M1_OPEN_SECOND' && (
                                        <span className="badge bg-success-subtle text-success border border-success ms-1">1차 익절 완료</span>
                                    )}
                                </div>
                            )}

                            {s.prev_rsi != null && (
                                <div className="text-muted" style={{ fontSize: 11 }}>
                                    RSI {s.prev_rsi?.toFixed(1)}
                                    {s.signal_state === 'M1_QUEUED_RSI_LOW' && ' → 50 상향 돌파 대기'}
                                    {s.signal_state === 'M1_QUEUED_RSI_HIGH' && ` → ${strat.rsi?.pullback_zone_high} 이하 눌림 후 반등 대기`}
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

// ── 메인 Strategy 페이지 ──────────────────────────────────────────────────────

const Strategy = () => {
    const [tab, setTab] = useState('scanner');
    const [watchlist, setWatchlist] = useState([]);

    const reloadWatchlist = useCallback(async () => {
        const d = await getWatchlist();
        setWatchlist(d.watchlist || []);
    }, []);

    useEffect(() => { reloadWatchlist(); }, [reloadWatchlist]);

    const addToWatchlist = async (item) => {
        const existing = watchlist.find(w => w.symbol === item.symbol);
        if (existing) {
            // 예산 업데이트
            const updated = watchlist.map(w => w.symbol === item.symbol ? { ...w, budget_usd: item.budget_usd } : w);
            await putWatchlist(updated);
        } else {
            await putWatchlist([...watchlist, item]);
        }
        await reloadWatchlist();
    };

    const removeFromWatchlist = async (symbol) => {
        await putWatchlist(watchlist.filter(w => w.symbol !== symbol));
        await reloadWatchlist();
    };

    return (
        <div className="container-fluid px-4 py-3">
            <div className="d-flex align-items-center mb-3">
                <TrendingUp className="me-2" size={22} />
                <h5 className="mb-0">MACD+RSI 모멘텀 전략</h5>
                <span className="badge bg-light text-dark border ms-2 small">US 소형주 자동매매</span>
            </div>

            {/* 워처 상태 바 */}
            <WatcherBar />

            {/* 탭 */}
            <ul className="nav nav-tabs mb-3">
                {[
                    { key: 'scanner', label: '🔍 종목 스캐너' },
                    { key: 'fit', label: '📋 보유종목 적합성' },
                    { key: 'monitor', label: `📡 신호 모니터 ${watchlist.length > 0 ? `(${watchlist.length})` : ''}` },
                ].map(t => (
                    <li className="nav-item" key={t.key}>
                        <button
                            className={`nav-link ${tab === t.key ? 'active' : ''}`}
                            onClick={() => setTab(t.key)}
                        >
                            {t.label}
                        </button>
                    </li>
                ))}
            </ul>

            {tab === 'scanner' && <ScannerTab onAddToWatchlist={addToWatchlist} />}
            {tab === 'fit' && <FitTab />}
            {tab === 'monitor' && <SignalMonitor watchlist={watchlist} onRemove={removeFromWatchlist} />}
        </div>
    );
};

export default Strategy;
