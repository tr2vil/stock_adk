import { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Target, Plus, Trash2, Loader2, RefreshCw, CheckCircle, Settings as Cog } from 'lucide-react';
import {
    getWatchlist, putWatchlist, getStrategyPlans,
    getStrategyConfig, putStrategyConfig,
    strategyAnalyze, strategyApprove, strategyDeactivate,
} from '../services/api';

const won = (n) => (n == null ? '-' : `₩${Math.round(Number(n)).toLocaleString()}`);

// ── 밴드 설정 에디터 (scope: _default 또는 종목코드) ──
const BandConfigEditor = ({ scope, label }) => {
    const [config, setConfig] = useState(null);
    const [msg, setMsg] = useState('');

    useEffect(() => {
        getStrategyConfig(scope === '_default' ? undefined : scope)
            .then((d) => setConfig(d.config));
    }, [scope]);

    const updateLadder = (key, idx, field, value) => {
        setConfig((c) => {
            const ladder = c[key].map((row, i) => i === idx ? { ...row, [field]: parseFloat(value) } : row);
            return { ...c, [key]: ladder };
        });
    };

    const save = async () => {
        setMsg('');
        try {
            await putStrategyConfig(scope, config);
            setMsg('저장됨');
            setTimeout(() => setMsg(''), 2000);
        } catch {
            setMsg('저장 실패');
        }
    };

    if (!config) return <div className="text-muted small">설정 로딩...</div>;

    const Ladder = ({ title, key_, sign }) => (
        <div className="mb-2">
            <div className="small fw-semibold mb-1">{title}</div>
            {config[key_].map((row, i) => (
                <div className="d-flex gap-2 align-items-center mb-1" key={i}>
                    <span className="text-muted small" style={{ width: 28 }}>{i + 1}단</span>
                    <div className="input-group input-group-sm" style={{ width: 130 }}>
                        <span className="input-group-text">오프셋%</span>
                        <input type="number" step="1" className="form-control"
                            value={Math.round(row.offset_pct * 100)}
                            onChange={(e) => updateLadder(key_, i, 'offset_pct', e.target.value / 100)} />
                    </div>
                    <div className="input-group input-group-sm" style={{ width: 130 }}>
                        <span className="input-group-text">비율</span>
                        <input type="number" step="0.01" className="form-control"
                            value={row.fraction}
                            onChange={(e) => updateLadder(key_, i, 'fraction', e.target.value)} />
                    </div>
                </div>
            ))}
        </div>
    );

    return (
        <div className="border rounded p-2 bg-light">
            <div className="d-flex align-items-center mb-2">
                <Cog size={14} className="me-1" />
                <span className="small fw-bold">{label} 밴드 설정</span>
                <button className="btn btn-sm btn-primary ms-auto" onClick={save}>저장</button>
                {msg && <span className="text-success small ms-2">{msg}</span>}
            </div>
            <div className="input-group input-group-sm mb-2" style={{ maxWidth: 220 }}>
                <span className="input-group-text">스윙 비율</span>
                <input type="number" step="0.05" className="form-control"
                    value={config.swing_fraction}
                    onChange={(e) => setConfig((c) => ({ ...c, swing_fraction: parseFloat(e.target.value) }))} />
                <span className="input-group-text">(0~1)</span>
            </div>
            <Ladder title="매도 사다리 (기대값 기준)" key_="sell_ladder" />
            <Ladder title="매수 사다리 (적정매수가 기준)" key_="buy_ladder" />
        </div>
    );
};

// ── 종목별 플랜 카드 ──
const PlanCard = ({ item, onChanged }) => {
    const { symbol, name, market, proposed, active } = item;
    const [analyzing, setAnalyzing] = useState(false);
    const [editTarget, setEditTarget] = useState('');
    const [editBuy, setEditBuy] = useState('');
    const [showConfig, setShowConfig] = useState(false);
    const [showReport, setShowReport] = useState(false);
    const [err, setErr] = useState('');

    useEffect(() => {
        if (proposed) {
            setEditTarget(proposed.target_price ?? '');
            setEditBuy(proposed.buy_anchor ?? '');
        }
    }, [proposed]);

    const analyze = async () => {
        setErr(''); setAnalyzing(true);
        try {
            await strategyAnalyze(symbol, market, name);
            await onChanged();
        } catch (e) {
            setErr(e.response?.data?.detail || '분석 실패');
        } finally {
            setAnalyzing(false);
        }
    };

    const approve = async () => {
        setErr('');
        try {
            await strategyApprove(symbol, parseFloat(editTarget), parseFloat(editBuy));
            await onChanged();
        } catch (e) {
            setErr(e.response?.data?.detail || '승인 실패');
        }
    };

    const deactivate = async () => {
        await strategyDeactivate(symbol);
        await onChanged();
    };

    return (
        <div className="card shadow-sm mb-3">
            <div className="card-header d-flex align-items-center">
                <span className="fw-bold">{name}</span>
                <span className="text-muted small ms-2">{symbol} · {market}</span>
                {active && <span className="badge bg-success ms-2"><CheckCircle size={12} className="me-1" />활성</span>}
                {!active && proposed && <span className="badge bg-warning text-dark ms-2">승인 대기</span>}
                <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={() => setShowConfig((s) => !s)}>
                    <Cog size={14} /> 밴드설정
                </button>
                <button className="btn btn-sm btn-primary ms-2" onClick={analyze} disabled={analyzing}>
                    {analyzing ? <><Loader2 size={14} className="me-1" />분석중(~1-2분)</> : <><RefreshCw size={14} className="me-1" />분석 실행</>}
                </button>
            </div>
            <div className="card-body">
                {err && <div className="alert alert-danger py-2">{err}</div>}
                {showConfig && <div className="mb-3"><BandConfigEditor scope={symbol} label={name} /></div>}

                {active && (
                    <div className="alert alert-success d-flex align-items-center mb-3">
                        <div>
                            <div className="small">활성 플랜 — 기대값(매도) <strong>{won(active.target_price)}</strong> · 적정매수가 <strong>{won(active.buy_anchor)}</strong></div>
                        </div>
                        <button className="btn btn-sm btn-outline-danger ms-auto" onClick={deactivate}>비활성화</button>
                    </div>
                )}

                {proposed ? (
                    <div className="border rounded p-3">
                        <div className="d-flex align-items-center mb-2">
                            <span className="badge bg-info me-2">{proposed.action}</span>
                            <span className="small text-muted">확신도 {Math.round((proposed.conviction || 0) * 100)}% · 현재가 {won(proposed.current_price)}</span>
                            <button className="btn btn-sm btn-link ms-auto p-0" onClick={() => setShowReport((s) => !s)}>
                                {showReport ? '리포트 접기' : '분석 리포트 보기'}
                            </button>
                        </div>
                        {showReport && (
                            <div className="border rounded p-2 bg-light mb-2" style={{ maxHeight: '35vh', overflowY: 'auto' }}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{proposed.report || ''}</ReactMarkdown>
                            </div>
                        )}
                        <div className="row g-2 align-items-end">
                            <div className="col-auto">
                                <label className="form-label small mb-0">기대값(매도 앵커)</label>
                                <input type="number" className="form-control form-control-sm" value={editTarget}
                                    onChange={(e) => setEditTarget(e.target.value)} />
                            </div>
                            <div className="col-auto">
                                <label className="form-label small mb-0">적정매수가(매수 앵커)</label>
                                <input type="number" className="form-control form-control-sm" value={editBuy}
                                    onChange={(e) => setEditBuy(e.target.value)} />
                            </div>
                            <div className="col-auto">
                                <button className="btn btn-success btn-sm" onClick={approve}>
                                    <CheckCircle size={14} className="me-1" /> 승인 → 활성화
                                </button>
                            </div>
                        </div>
                        <div className="form-text">LLM 제안값입니다. 수정 후 승인하세요.</div>
                    </div>
                ) : (
                    <div className="text-muted small">아직 분석 제안이 없습니다. "분석 실행"을 눌러 기대값을 제안받으세요.</div>
                )}
            </div>
        </div>
    );
};

const Strategy = () => {
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [newItem, setNewItem] = useState({ symbol: '', market: 'KR', name: '' });

    const reload = useCallback(async () => {
        const d = await getStrategyPlans();
        setPlans(d.plans || []);
        setLoading(false);
    }, []);

    useEffect(() => { reload(); }, [reload]);

    const addWatch = async () => {
        if (!newItem.symbol.trim()) return;
        const wl = await getWatchlist();
        const items = wl.watchlist || [];
        if (items.find((x) => x.symbol === newItem.symbol)) return;
        await putWatchlist([...items, { ...newItem, name: newItem.name || newItem.symbol }]);
        setNewItem({ symbol: '', market: 'KR', name: '' });
        await reload();
    };

    const removeWatch = async (symbol) => {
        const wl = await getWatchlist();
        await putWatchlist((wl.watchlist || []).filter((x) => x.symbol !== symbol));
        await reload();
    };

    return (
        <div className="container-fluid px-4 py-3">
            <div className="d-flex align-items-center mb-3">
                <Target className="me-2" size={24} />
                <h4 className="mb-0">스윙 밴드 전략</h4>
            </div>

            {/* 워치리스트 추가 */}
            <div className="card shadow-sm mb-3">
                <div className="card-body d-flex flex-wrap gap-2 align-items-end">
                    <div>
                        <label className="form-label small mb-0">종목코드</label>
                        <input className="form-control form-control-sm" style={{ width: 140 }}
                            placeholder="예: 005930" value={newItem.symbol}
                            onChange={(e) => setNewItem((s) => ({ ...s, symbol: e.target.value.trim() }))} />
                    </div>
                    <div>
                        <label className="form-label small mb-0">시장</label>
                        <select className="form-select form-select-sm" style={{ width: 90 }}
                            value={newItem.market} onChange={(e) => setNewItem((s) => ({ ...s, market: e.target.value }))}>
                            <option value="KR">KR</option>
                            <option value="US">US</option>
                        </select>
                    </div>
                    <div>
                        <label className="form-label small mb-0">이름(선택)</label>
                        <input className="form-control form-control-sm" style={{ width: 160 }}
                            placeholder="예: 삼성전자" value={newItem.name}
                            onChange={(e) => setNewItem((s) => ({ ...s, name: e.target.value }))} />
                    </div>
                    <button className="btn btn-primary btn-sm" onClick={addWatch}>
                        <Plus size={14} className="me-1" /> 워치리스트 추가
                    </button>
                </div>
            </div>

            {/* 전역 기본 밴드 설정 */}
            <div className="mb-3"><BandConfigEditor scope="_default" label="전역 기본" /></div>

            {loading && <div className="text-center py-4"><Loader2 size={32} className="text-primary" /></div>}

            {!loading && !plans.length && (
                <div className="alert alert-info">워치리스트가 비어 있습니다. 위에서 종목을 추가하세요.</div>
            )}

            {plans.map((item) => (
                <div key={item.symbol} className="position-relative">
                    <button
                        className="btn btn-sm btn-outline-danger position-absolute"
                        style={{ right: 8, top: -2, zIndex: 2 }}
                        onClick={() => removeWatch(item.symbol)}
                        title="워치리스트에서 제거"
                    >
                        <Trash2 size={14} />
                    </button>
                    <PlanCard item={item} onChanged={reload} />
                </div>
            ))}
        </div>
    );
};

export default Strategy;
