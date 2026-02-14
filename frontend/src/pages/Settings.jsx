import React, { useState, useEffect, useCallback } from 'react';
import { Settings as SettingsIcon, Save, RotateCcw, CheckCircle, AlertCircle } from 'lucide-react';
import { getPrompts, updatePrompt, getWeights, updateWeights, updateThresholds } from '../services/api';
import styles from './Settings.module.css';

const AGENTS = [
    { key: 'orchestrator', label: 'Orchestrator', desc: '오케스트레이터' },
    { key: 'news_agent', label: 'News Agent', desc: '뉴스/센티먼트 분석' },
    { key: 'fundamental_agent', label: 'Fundamental Agent', desc: '재무제표 분석' },
    { key: 'technical_agent', label: 'Technical Agent', desc: '기술적 분석' },
    { key: 'expert_agent', label: 'Expert Agent', desc: '전문가 신호' },
    { key: 'risk_agent', label: 'Risk Agent', desc: '리스크 관리' },
];

const WEIGHT_KEYS = [
    { key: 'technical', label: 'Technical Agent' },
    { key: 'fundamental', label: 'Fundamental Agent' },
    { key: 'news', label: 'News Agent' },
    { key: 'expert', label: 'Expert Agent' },
    { key: 'risk', label: 'Risk Agent' },
];

const Settings = () => {
    const [prompts, setPrompts] = useState({});
    const [originalPrompts, setOriginalPrompts] = useState({});
    const [selectedAgent, setSelectedAgent] = useState('orchestrator');
    const [editedPrompt, setEditedPrompt] = useState('');
    const [weights, setWeights] = useState({});
    const [thresholds, setThresholds] = useState({ buy: 0.3, sell: -0.3 });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState(null);

    // Load all data on mount
    useEffect(() => {
        Promise.all([getPrompts(), getWeights()])
            .then(([promptsRes, weightsRes]) => {
                setPrompts(promptsRes.prompts);
                setOriginalPrompts(promptsRes.prompts);
                setWeights(weightsRes.weights || {});
                setThresholds(weightsRes.thresholds || { buy: 0.3, sell: -0.3 });
                setEditedPrompt(promptsRes.prompts['orchestrator'] || '');
                setLoading(false);
            })
            .catch(() => {
                showToast('error', '설정을 불러오는데 실패했습니다');
                setLoading(false);
            });
    }, []);

    // When selected agent changes, update textarea
    useEffect(() => {
        setEditedPrompt(prompts[selectedAgent] || '');
    }, [selectedAgent, prompts]);

    // Auto-dismiss toast
    useEffect(() => {
        if (toast) {
            const timer = setTimeout(() => setToast(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [toast]);

    const showToast = useCallback((type, message) => {
        setToast({ type, message });
    }, []);

    const savePrompt = async () => {
        setSaving(true);
        try {
            await updatePrompt(selectedAgent, editedPrompt);
            setPrompts(prev => ({ ...prev, [selectedAgent]: editedPrompt }));
            setOriginalPrompts(prev => ({ ...prev, [selectedAgent]: editedPrompt }));
            showToast('success', `${selectedAgent} 프롬프트가 저장되었습니다`);
        } catch (e) {
            showToast('error', e.response?.data?.detail || '프롬프트 저장 실패');
        }
        setSaving(false);
    };

    const resetPrompt = () => {
        setEditedPrompt(originalPrompts[selectedAgent] || '');
    };

    const handleWeightChange = (key, value) => {
        setWeights(prev => ({ ...prev, [key]: parseFloat(value) / 100 }));
    };

    const saveWeights = async () => {
        setSaving(true);
        try {
            await updateWeights(weights);
            // Reload orchestrator prompt since weight table was updated
            const promptsRes = await getPrompts();
            setPrompts(promptsRes.prompts);
            setOriginalPrompts(promptsRes.prompts);
            if (selectedAgent === 'orchestrator') {
                setEditedPrompt(promptsRes.prompts['orchestrator'] || '');
            }
            showToast('success', '가중치가 저장되었습니다');
        } catch (e) {
            showToast('error', e.response?.data?.detail || '가중치 저장 실패');
        }
        setSaving(false);
    };

    const saveThresholds = async () => {
        setSaving(true);
        try {
            await updateThresholds(thresholds);
            showToast('success', '임계값이 저장되었습니다');
        } catch (e) {
            showToast('error', e.response?.data?.detail || '임계값 저장 실패');
        }
        setSaving(false);
    };

    const totalWeight = Object.values(weights).reduce((s, v) => s + v, 0);
    const isValidTotal = Math.abs(totalWeight - 1.0) < 0.01;
    const hasPromptChanges = editedPrompt !== (prompts[selectedAgent] || '');

    if (loading) {
        return (
            <div className="container-fluid py-4">
                <div className="text-center py-5">
                    <div className="spinner-border text-primary" role="status" />
                    <p className="mt-3 text-muted">설정을 불러오는 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="container-fluid py-3 px-4">
            {/* Toast */}
            {toast && (
                <div className={`${styles.toast} alert ${toast.type === 'success' ? 'alert-success' : 'alert-danger'} d-flex align-items-center`}>
                    {toast.type === 'success' ? <CheckCircle size={18} className="me-2" /> : <AlertCircle size={18} className="me-2" />}
                    {toast.message}
                </div>
            )}

            {/* Header */}
            <div className={styles.pageHeader}>
                <SettingsIcon size={24} className="me-2" />
                <h4 className="mb-0 fw-bold">에이전트 설정</h4>
            </div>

            <div className="row g-3">
                {/* Left: Agent List */}
                <div className="col-md-3 col-lg-2">
                    <div className={`${styles.card} card`}>
                        <div className={styles.cardHeader}>
                            <small className="fw-semibold text-muted">에이전트</small>
                        </div>
                        <div className="card-body p-2">
                            <ul className={styles.agentList}>
                                {AGENTS.map(agent => (
                                    <li
                                        key={agent.key}
                                        className={`${styles.agentItem} ${selectedAgent === agent.key ? styles.agentItemActive : ''}`}
                                        onClick={() => setSelectedAgent(agent.key)}
                                    >
                                        <div>{agent.label}</div>
                                        <small className="text-muted" style={{ fontSize: '0.78rem' }}>{agent.desc}</small>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>

                {/* Right: Prompt Editor + Weights */}
                <div className="col-md-9 col-lg-10">
                    {/* Prompt Editor */}
                    <div className={`${styles.card} card mb-3`}>
                        <div className={`${styles.cardHeader} d-flex justify-content-between align-items-center`}>
                            <span className="fw-semibold">
                                {AGENTS.find(a => a.key === selectedAgent)?.label} 프롬프트
                            </span>
                            <span className={styles.charCount}>{editedPrompt.length} chars</span>
                        </div>
                        <div className="card-body p-3">
                            <textarea
                                className={`form-control ${styles.promptTextarea}`}
                                rows={30}
                                value={editedPrompt}
                                onChange={e => setEditedPrompt(e.target.value)}
                                spellCheck={false}
                            />
                            <div className="d-flex justify-content-between mt-3">
                                <button
                                    className="btn btn-outline-secondary btn-sm"
                                    onClick={resetPrompt}
                                    disabled={!hasPromptChanges || saving}
                                >
                                    <RotateCcw size={16} className="me-1" /> 되돌리기
                                </button>
                                <button
                                    className="btn btn-primary btn-sm"
                                    onClick={savePrompt}
                                    disabled={!hasPromptChanges || saving}
                                >
                                    <Save size={16} className="me-1" />
                                    {saving ? '저장 중...' : '프롬프트 저장'}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Weights Section (only for orchestrator) */}
                    {selectedAgent === 'orchestrator' && (
                        <div className="row g-3">
                            <div className="col-lg-7">
                                <div className={`${styles.card} card`}>
                                    <div className={styles.cardHeader}>
                                        <span className="fw-semibold">에이전트 가중치</span>
                                    </div>
                                    <div className="card-body p-3">
                                        {WEIGHT_KEYS.map(({ key, label }) => (
                                            <div key={key} className={styles.sliderRow}>
                                                <span className={styles.sliderLabel}>{label}</span>
                                                <input
                                                    type="range"
                                                    className={`form-range ${styles.sliderInput}`}
                                                    min="0"
                                                    max="100"
                                                    step="1"
                                                    value={Math.round((weights[key] || 0) * 100)}
                                                    onChange={e => handleWeightChange(key, e.target.value)}
                                                />
                                                <span className={styles.sliderValue}>
                                                    {Math.round((weights[key] || 0) * 100)}%
                                                </span>
                                            </div>
                                        ))}
                                        <div className={styles.totalRow}>
                                            <span>합계</span>
                                            <span className={isValidTotal ? styles.totalValid : styles.totalInvalid}>
                                                {Math.round(totalWeight * 100)}%
                                                {!isValidTotal && ' (100%여야 합니다)'}
                                            </span>
                                        </div>
                                        <div className="text-end mt-3">
                                            <button
                                                className="btn btn-primary btn-sm"
                                                onClick={saveWeights}
                                                disabled={!isValidTotal || saving}
                                            >
                                                <Save size={16} className="me-1" />
                                                {saving ? '저장 중...' : '가중치 저장'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="col-lg-5">
                                <div className={`${styles.card} card`}>
                                    <div className={styles.cardHeader}>
                                        <span className="fw-semibold">의사결정 임계값</span>
                                    </div>
                                    <div className="card-body p-3">
                                        <div className={styles.thresholdRow}>
                                            <span className={styles.thresholdLabel}>
                                                <span className="badge bg-success me-1">BUY</span>
                                            </span>
                                            <span className="text-muted me-2">점수 &gt;</span>
                                            <input
                                                type="number"
                                                className={`form-control form-control-sm ${styles.thresholdInput}`}
                                                value={thresholds.buy}
                                                step="0.05"
                                                min="-1"
                                                max="1"
                                                onChange={e => setThresholds(prev => ({ ...prev, buy: parseFloat(e.target.value) }))}
                                            />
                                        </div>
                                        <div className={styles.thresholdRow}>
                                            <span className={styles.thresholdLabel}>
                                                <span className="badge bg-danger me-1">SELL</span>
                                            </span>
                                            <span className="text-muted me-2">점수 &lt;</span>
                                            <input
                                                type="number"
                                                className={`form-control form-control-sm ${styles.thresholdInput}`}
                                                value={thresholds.sell}
                                                step="0.05"
                                                min="-1"
                                                max="1"
                                                onChange={e => setThresholds(prev => ({ ...prev, sell: parseFloat(e.target.value) }))}
                                            />
                                        </div>
                                        <p className="text-muted small mt-2 mb-3">
                                            그 외 점수는 HOLD로 판단됩니다.
                                        </p>
                                        <div className="text-end">
                                            <button
                                                className="btn btn-primary btn-sm"
                                                onClick={saveThresholds}
                                                disabled={saving}
                                            >
                                                <Save size={16} className="me-1" />
                                                {saving ? '저장 중...' : '임계값 저장'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Settings;
