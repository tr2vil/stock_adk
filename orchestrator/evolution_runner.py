"""자가진화 파이프라인 오케스트레이션 (설계서 5.2).

데이터 수집(결정론) → 성과 통계(결정론) → LLM 제안(Evolution Agent)
→ 가드레일 검증(결정론) → 대기 제안 저장 → Telegram 승인 요청.

승인 시에만 전략이 갱신된다(HiL). LLM 출력은 guardrails 에서 재검증되므로
범위를 벗어난 제안은 자동 거부된다. 매매 데이터가 부족하면 LLM을 호출하지 않는다.

server 엔드포인트와 scheduler(16:00) 둘 다 이 모듈을 사용한다.
"""
from __future__ import annotations

import re
import json
import time
import uuid

from google.adk.runners import InMemoryRunner
from google.genai import types

from sub_agents.evolution_agent.agent import root_agent as _evolution_agent
from shared.logger import get_logger
from shared.quant.schema import StrategyConfig, EvolutionProposal
from shared.quant.performance import compute_performance
from shared.quant.guardrails import validate_proposal, apply_proposal
from shared.quant import strategy_store as store
from shared.quant.trade_log import aget_recent_trades
from shared import notifications

_logger = get_logger("orchestrator.evolution")

_runner = InMemoryRunner(agent=_evolution_agent, app_name="evolution")

# 진화 허용 최소 청산 매매 수 (데이터 부족 시 과적합 방지 — 설계서 11.1)
MIN_CLOSED_TRADES = 10
_DAY_MS = 86_400_000


async def _run_agent_text(prompt: str) -> str:
    """Evolution Agent 실행 → 최종 텍스트."""
    user_id = f"evo_{uuid.uuid4().hex[:8]}"
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    session = await _runner.session_service.create_session(
        app_name=_runner.app_name, user_id=user_id,
    )
    final = ""
    async for event in _runner.run_async(
        user_id=user_id, session_id=session.id, new_message=msg,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def _parse_proposal(text: str) -> EvolutionProposal | None:
    """LLM JSON 응답을 EvolutionProposal 로 파싱(코드펜스/잡텍스트 허용)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return EvolutionProposal.model_validate(json.loads(m.group(0)))
    except Exception:
        return None


def _format_proposal_msg(current: StrategyConfig, new_version: str,
                         proposal: EvolutionProposal, applied: list[dict]) -> str:
    lines = [
        f"🧬 전략 진화 제안  v{current.version} → v{new_version}",
        "",
        f"📊 분석: {proposal.analysis}",
        "",
        "📝 변경 항목",
    ]
    for c in applied:
        lines.append(f"• {c['param']}: {c['current']} → {c['proposed']}")
    lines += [
        "",
        f"💡 기대 효과: {proposal.expected_improvement}",
        f"신뢰도: {proposal.confidence:.0%}",
    ]
    return "\n".join(lines)


async def run_evolution_analysis(lookback_days: int = 30, trigger: str = "manual") -> dict:
    """진화 분석 1회 실행. 제안 생성 시 대기 저장 + Telegram 발송.

    Returns:
        dict: {status, ...}
        status ∈ insufficient_data | rejected | error | proposed
    """
    since_ms = int(time.time() * 1000) - lookback_days * _DAY_MS
    trades = await aget_recent_trades(limit=5000, since_ms=since_ms)
    perf = compute_performance(trades)
    current = await store.aget_active_strategy()

    base = {"trigger": trigger, "lookback_days": lookback_days,
            "performance": perf, "current_version": current.version}

    if perf["total_trades"] < MIN_CLOSED_TRADES:
        _logger.info("evolution_insufficient", trades=perf["total_trades"])
        return {**base, "status": "insufficient_data",
                "message": f"need >= {MIN_CLOSED_TRADES} closed trades, got {perf['total_trades']}"}

    prompt = (
        "## 현재 전략 파라미터 (JSON)\n"
        f"{json.dumps(current.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "## 최근 매매 성과 통계 (JSON)\n"
        f"{json.dumps(perf, ensure_ascii=False, indent=2)}"
    )

    try:
        text = await _run_agent_text(prompt)
    except Exception as e:
        _logger.warning("evolution_llm_failed", error=str(e))
        return {**base, "status": "error", "message": f"LLM call failed: {e}"}

    proposal = _parse_proposal(text)
    if proposal is None or not proposal.changes:
        return {**base, "status": "rejected", "message": "no valid changes proposed",
                "raw": text[:500]}

    ok, msg = validate_proposal(proposal)
    if not ok:
        _logger.info("evolution_guardrail_block", reason=msg)
        await notifications.send_message(f"🧬 진화 제안이 가드레일에 막혔습니다: {msg}")
        return {**base, "status": "rejected", "message": msg,
                "proposal": proposal.model_dump()}

    new_strategy, applied, err = apply_proposal(current, proposal, approved_by="user")
    if err:
        return {**base, "status": "rejected", "message": err,
                "proposal": proposal.model_dump()}

    pid = await store.aput_pending_proposal({
        "proposal": proposal.model_dump(),
        "applied_changes": applied,
        "new_strategy": new_strategy.model_dump(),
        "performance_before": perf,
        "current_version": current.version,
        "new_version": new_strategy.version,
        "created_at": int(time.time() * 1000),
    })

    await notifications.send_strategy_proposal(
        pid, _format_proposal_msg(current, new_strategy.version, proposal, applied)
    )
    _logger.info("evolution_proposed", pid=pid, new_version=new_strategy.version,
                 changes=len(applied), confidence=proposal.confidence)

    return {**base, "status": "proposed", "proposal_id": pid,
            "new_version": new_strategy.version, "changes": applied,
            "proposal": proposal.model_dump()}


async def approve_proposal(pid: str, approved_by: str = "user") -> dict:
    """대기 제안 승인 → 전략 갱신 + 버전 이력 기록."""
    pending = await store.aget_pending_proposal(pid)
    if not pending:
        return {"status": "not_found", "proposal_id": pid}

    current = await store.aget_active_strategy()
    proposal = EvolutionProposal.model_validate(pending["proposal"])
    # 승인 시점 기준으로 재적용·재검증 (활성 전략이 그새 바뀌었을 수 있음)
    new_strategy, applied, err = apply_proposal(current, proposal, approved_by=approved_by)
    if err:
        await store.adelete_pending_proposal(pid)
        return {"status": "rejected", "message": err}

    await store.acommit_new_version(
        new_strategy, analysis=proposal.analysis, changes=applied,
        performance_before=pending.get("performance_before", {}), approved_by=approved_by,
    )
    await store.adelete_pending_proposal(pid)
    await notifications.send_message(
        f"✅ 전략 적용 완료: v{new_strategy.version} ({len(applied)}개 변경)"
    )
    return {"status": "applied", "version": new_strategy.version, "changes": applied}


async def reject_proposal(pid: str) -> dict:
    """대기 제안 거부 → 폐기, 현재 전략 유지."""
    pending = await store.aget_pending_proposal(pid)
    if not pending:
        return {"status": "not_found", "proposal_id": pid}
    await store.adelete_pending_proposal(pid)
    await notifications.send_message("❌ 전략 진화 제안 거부됨. 현재 전략 유지.")
    return {"status": "rejected", "proposal_id": pid}
