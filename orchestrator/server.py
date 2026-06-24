"""
FastAPI + ADK API Server for Orchestrator
RESTful API와 ADK Agent를 통합한 서버
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

import os
import re
import time
import uuid
from contextlib import asynccontextmanager, AsyncExitStack
from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.middleware import A2ALoggingMiddleware
from shared.redis_client import (
    aget_prompt, aset_prompt, aget_weights, aset_weights,
    aget_thresholds, aset_thresholds,
)
from shared import strategy as strat
from shared.logger import get_logger
from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import root_agent
from .decision_engine import reload_config as reload_decision_config
from .scheduler import (
    start_scheduler, stop_scheduler,
    start_watcher, stop_watcher, get_watcher_job_info,
)
from execution.toss_rest import TossRESTClient
from execution.watcher import market_sessions
from shared.config import settings
from . import evolution_runner
from shared.quant import strategy_store as qstore

_logger = get_logger("orchestrator.server")

# InMemoryRunner for REST API analysis
_runner = InMemoryRunner(agent=root_agent, app_name="stock_analysis")

# 밴드 앵커 추출 전용 경량 runner (근거 강화)
from .extract_agent import extract_agent
_extract_runner = InMemoryRunner(agent=extract_agent, app_name="band_extract")

# Toss client for holdings/candles (포트폴리오 화면)
_toss = TossRESTClient()

# ADK sub-app startup handlers (populated below, executed in lifespan)
# 구버전 ADK: router.on_startup 리스트 / 신버전 ADK: lifespan 컨텍스트
_adk_startup_handlers = []
_adk_apps = []  # 마운트된 ADK 서브앱 (신버전 lifespan 실행용)


# Lifespan handler for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: trigger ADK sub-app route registration
    # to_a2a() registers A2A routes in on_startup, but mounted sub-apps'
    # startup events are not called automatically by FastAPI's lifespan.
    async with AsyncExitStack() as stack:
        # 구버전 ADK: on_startup 핸들러 직접 호출
        for handler in _adk_startup_handlers:
            await handler()
        # 신버전 ADK: 서브앱의 lifespan 컨텍스트를 진입시켜 초기화
        for sub_app in _adk_apps:
            await stack.enter_async_context(
                sub_app.router.lifespan_context(sub_app)
            )
        # 스케줄러 시작 (진화·일일 리포트 잡 등록)
        start_scheduler()

        # 컨테이너 재시작 후 워처 자동 재개
        # Redis에 enabled=true 플래그가 있으면 이전 상태를 복구한다
        try:
            _watcher_was_enabled = await strat.aget_watcher_enabled()
            if _watcher_was_enabled:
                start_watcher()
                _logger.info("watcher_auto_resumed", reason="redis_flag_was_enabled")
        except Exception as _e:
            _logger.warning("watcher_auto_resume_failed", error=str(_e))

        yield
        # Shutdown
        stop_scheduler()


app = FastAPI(
    title="Trading Orchestrator API",
    description="주식 자동매매 시스템 오케스트레이터 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A2A request/response logging middleware
app.add_middleware(A2ALoggingMiddleware, agent_name="orchestrator")


# Request/Response models
class AnalysisRequest(BaseModel):
    """종목 분석 요청"""
    ticker: str
    market: str = "US"


class ResolveTickerRequest(BaseModel):
    """종목 조회 요청"""
    query: str


class ChatRequest(BaseModel):
    """AI 비서 채팅 요청"""
    message: str


class WatchlistRequest(BaseModel):
    """워치리스트 수정 요청"""
    watchlist: list[dict]


class BandConfigRequest(BaseModel):
    """밴드 설정 수정 요청 (scope: '_default' 또는 종목코드)"""
    scope: str
    config: dict


class StrategyAnalyzeRequest(BaseModel):
    """전략 분석(기대값 제안) 요청"""
    symbol: str
    market: str = "KR"
    name: str = ""


class ApprovePlanRequest(BaseModel):
    """제안 플랜 승인 요청 (사용자 수정값 선택적)"""
    symbol: str
    target_price: float | None = None
    buy_anchor: float | None = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


class PromptRequest(BaseModel):
    """프롬프트 수정 요청"""
    prompt: str


class WeightsRequest(BaseModel):
    """가중치 수정 요청"""
    weights: dict[str, float]


class ThresholdsRequest(BaseModel):
    """임계값 수정 요청"""
    thresholds: dict[str, float]


# Valid agent names for prompt management
_AGENT_NAMES = [
    "orchestrator", "news_agent", "fundamental_agent",
    "technical_agent", "expert_agent", "risk_agent",
]

# Sub-agent host/port mapping for reload notifications
_SUB_AGENT_HOSTS = {
    "news_agent": ("NEWS_AGENT_HOST", "NEWS_AGENT_PORT", "localhost", "8001"),
    "fundamental_agent": ("FUNDAMENTAL_AGENT_HOST", "FUNDAMENTAL_AGENT_PORT", "localhost", "8002"),
    "technical_agent": ("TECHNICAL_AGENT_HOST", "TECHNICAL_AGENT_PORT", "localhost", "8003"),
    "expert_agent": ("EXPERT_AGENT_HOST", "EXPERT_AGENT_PORT", "localhost", "8004"),
    "risk_agent": ("RISK_AGENT_HOST", "RISK_AGENT_PORT", "localhost", "8005"),
}


def _update_weight_table_in_prompt(prompt_text: str, weights: dict) -> str:
    """Replace the weight table in the orchestrator prompt with new values."""
    agent_labels = {
        "technical": ("technical_agent", "차트 기술적 분석"),
        "fundamental": ("fundamental_agent", "재무제표 분석"),
        "news": ("news_agent", "뉴스/센티먼트"),
        "expert": ("expert_agent", "전문가 신호"),
        "risk": ("risk_agent", "리스크 조정"),
    }
    new_rows = []
    for key in ["technical", "fundamental", "news", "expert", "risk"]:
        agent_name, desc = agent_labels[key]
        pct = int(weights.get(key, 0) * 100)
        new_rows.append(f"| {agent_name} | {pct}% | {desc} |")

    new_table = (
        "## 가중치\n\n"
        "| Agent | 가중치 | 설명 |\n"
        "|-------|--------|------|\n"
        + "\n".join(new_rows)
        + "\n"
    )
    # Replace the existing weight section (from "## 가중치" to the next "##")
    replaced = re.sub(
        r"## 가중치\s*\n(?:.*\n)*?(?=## )",
        new_table + "\n",
        prompt_text,
    )
    return replaced


async def _notify_agent_reload(agent_name: str) -> None:
    """Notify a sub-agent to reload its prompt from Redis."""
    if agent_name not in _SUB_AGENT_HOSTS:
        return
    host_env, port_env, default_host, default_port = _SUB_AGENT_HOSTS[agent_name]
    host = os.getenv(host_env, default_host)
    port = os.getenv(port_env, default_port)
    url = f"http://{host}:{port}/reload"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, timeout=10)
            _logger.info("agent_reload", agent=agent_name, status=resp.status_code)
    except Exception as e:
        _logger.warning("agent_reload_failed", agent=agent_name, error=str(e))


# API Endpoints
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/api/resolve-ticker")
async def resolve_ticker(request: ResolveTickerRequest):
    """종목명/티커를 검색하여 정확한 티커와 마켓을 반환합니다."""
    from shared.ticker_utils import lookup_ticker

    result = lookup_ticker(request.query)
    if result.get("status") == "error":
        raise HTTPException(404, result.get("error", "종목을 찾을 수 없습니다"))
    return result


@app.post("/api/analyze")
async def analyze_stock(request: AnalysisRequest):
    """
    종목 분석 요청 엔드포인트.

    Orchestrator agent를 통해 전체 분석 파이프라인을 실행합니다.
    InMemoryRunner로 ADK Agent를 실행하고 최종 응답을 반환합니다.
    """
    start = time.monotonic()
    prompt = f"{request.ticker} {request.market} market 주식 분석해줘"
    user_id = f"web_{uuid.uuid4().hex[:8]}"

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=prompt)],
    )

    # InMemoryRunner requires an existing session — create one first
    session = await _runner.session_service.create_session(
        app_name=_runner.app_name,
        user_id=user_id,
    )

    final_text = ""
    async for event in _runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if not final_text:
        raise HTTPException(status_code=500, detail="분석 결과가 비어있습니다")

    return {
        "status": "success",
        "ticker": request.ticker,
        "market": request.market,
        "result": final_text,
        "elapsed_ms": elapsed_ms,
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """AI 비서 채팅 엔드포인트.

    자유 입력 메시지를 Orchestrator agent로 실행하고 텍스트 응답을 반환합니다.
    프론트엔드(AIAssistant)는 응답의 `message` 필드를 렌더링합니다.
    """
    user_id = f"chat_{uuid.uuid4().hex[:8]}"
    user_message = types.Content(role="user", parts=[types.Part(text=request.message)])

    session = await _runner.session_service.create_session(
        app_name=_runner.app_name,
        user_id=user_id,
    )

    final_text = ""
    async for event in _runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    if not final_text:
        raise HTTPException(status_code=500, detail="응답이 비어있습니다")

    return {"type": "text", "message": final_text}


@app.get("/api/holdings")
def get_holdings():
    """토스 보유종목 조회 (포트폴리오 화면).

    sync def → FastAPI가 스레드풀에서 실행하므로 blocking requests가
    이벤트 루프를 막지 않는다.
    """
    data = _toss.get_balance()
    if "error" in data:
        raise HTTPException(status_code=502, detail=f"토스 보유종목 조회 실패: {data['error']}")
    return data.get("result", data)


@app.get("/api/candles/{symbol}")
def get_candles(symbol: str, interval: str = "1d", count: int = 60):
    """토스 캔들(차트) 데이터 조회 (포트폴리오 화면)."""
    data = _toss.get_candles(symbol, interval=interval, count=count)
    if "error" in data:
        raise HTTPException(status_code=502, detail=f"토스 캔들 조회 실패: {data['error']}")
    result = data.get("result", {})
    return {"symbol": symbol, "interval": interval, "candles": result.get("candles", [])}


@app.get("/api/agents")
async def list_agents():
    """등록된 sub-agent 목록을 반환합니다."""
    return {
        "orchestrator": "trading_orchestrator",
        "sub_agents": [
            {"name": "news_agent", "port": 8001, "description": "종목 뉴스 수집 및 시황/센티먼트 분석"},
            {"name": "fundamental_agent", "port": 8002, "description": "재무제표 분석 및 밸류에이션 평가"},
            {"name": "technical_agent", "port": 8003, "description": "차트 기술적 분석 및 패턴 인식"},
            {"name": "expert_agent", "port": 8004, "description": "애널리스트 리포트 및 기관/외국인 수급 분석"},
            {"name": "risk_agent", "port": 8005, "description": "포지션 사이징 및 리스크 관리"},
        ],
    }


# ── Prompt Management API ──

@app.get("/api/prompts")
async def get_all_prompts():
    """전체 에이전트 프롬프트 조회."""
    prompts = {}
    for name in _AGENT_NAMES:
        prompts[name] = await aget_prompt(name)
    return {"prompts": prompts}


@app.get("/api/prompts/{agent_name}")
async def get_prompt_endpoint(agent_name: str):
    """개별 에이전트 프롬프트 조회."""
    if agent_name not in _AGENT_NAMES:
        raise HTTPException(404, f"Unknown agent: {agent_name}")
    text = await aget_prompt(agent_name)
    if text is None:
        raise HTTPException(404, f"Prompt not found: {agent_name}")
    return {"agent": agent_name, "prompt": text}


@app.put("/api/prompts/{agent_name}")
async def update_prompt(agent_name: str, body: PromptRequest):
    """에이전트 프롬프트 수정 + 핫 리로드."""
    if agent_name not in _AGENT_NAMES:
        raise HTTPException(404, f"Unknown agent: {agent_name}")
    if len(body.prompt.strip()) < 10:
        raise HTTPException(400, "Prompt is too short (min 10 chars)")

    await aset_prompt(agent_name, body.prompt)

    if agent_name == "orchestrator":
        root_agent.instruction = body.prompt
        _logger.info("orchestrator_prompt_reloaded", length=len(body.prompt))
    else:
        await _notify_agent_reload(agent_name)

    return {"status": "updated", "agent": agent_name}


# ── Weights / Thresholds API ──

@app.get("/api/weights")
async def get_weights():
    """가중치 및 임계값 조회."""
    weights = await aget_weights()
    thresholds = await aget_thresholds()
    return {"weights": weights, "thresholds": thresholds}


@app.put("/api/weights")
async def update_weights(body: WeightsRequest):
    """가중치 수정 (합계=1.0 검증) + 오케스트레이터 프롬프트 가중치 테이블 자동 갱신."""
    required_keys = {"technical", "fundamental", "news", "expert", "risk"}
    if set(body.weights.keys()) != required_keys:
        raise HTTPException(400, f"Must provide all keys: {required_keys}")

    total = sum(body.weights.values())
    if not (0.99 <= total <= 1.01):
        raise HTTPException(400, f"Weights must sum to 1.0, got {total:.4f}")

    await aset_weights(body.weights)

    # Update weight table in orchestrator prompt
    current_prompt = await aget_prompt("orchestrator")
    if current_prompt:
        updated_prompt = _update_weight_table_in_prompt(current_prompt, body.weights)
        await aset_prompt("orchestrator", updated_prompt)
        root_agent.instruction = updated_prompt

    reload_decision_config()
    _logger.info("weights_updated", weights=body.weights)
    return {"status": "updated", "weights": body.weights}


@app.put("/api/thresholds")
async def update_thresholds(body: ThresholdsRequest):
    """임계값 수정."""
    await aset_thresholds(body.thresholds)
    reload_decision_config()
    _logger.info("thresholds_updated", thresholds=body.thresholds)
    return {"status": "updated", "thresholds": body.thresholds}


# ── 스윙 밴드 전략 (Phase 1: 토대) ──

async def _run_agent_text(prompt: str, runner: InMemoryRunner | None = None) -> str:
    """ADK agent를 실행해 최종 텍스트를 반환 (analyze/chat과 동일 패턴).

    runner 미지정 시 오케스트레이터(_runner) 사용. 추출 등 경량 호출은
    _extract_runner를 넘긴다.
    """
    runner = runner or _runner
    user_id = f"strat_{uuid.uuid4().hex[:8]}"
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id=user_id,
    )
    final = ""
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=msg,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text
    return final


@app.get("/api/watchlist")
async def get_watchlist():
    """워치리스트 조회."""
    return {"watchlist": await strat.aget_watchlist()}


@app.put("/api/watchlist")
async def put_watchlist(body: WatchlistRequest):
    """워치리스트 수정."""
    await strat.aset_watchlist(body.watchlist)
    return {"status": "updated", "watchlist": body.watchlist}


@app.get("/api/strategy/config")
async def get_strategy_config(symbol: str | None = None):
    """밴드 설정 조회 (symbol 주면 전역 기본값+종목 오버라이드 병합)."""
    return {"scope": symbol or "_default", "config": await strat.aget_band_config(symbol)}


@app.put("/api/strategy/config")
async def put_strategy_config(body: BandConfigRequest):
    """밴드 설정 저장 (scope='_default' 또는 종목코드)."""
    await strat.aset_band_config(body.scope, body.config)
    return {"status": "updated", "scope": body.scope, "config": body.config}


@app.get("/api/strategy/plans")
async def get_strategy_plans():
    """워치리스트 종목별 제안/활성 플랜 조회."""
    return {"plans": await strat.aget_all_plans()}


@app.post("/api/strategy/analyze")
async def strategy_analyze(body: StrategyAnalyzeRequest):
    """5-에이전트 분석 → 기대값/적정매수가 제안 (승인 대기 상태로 저장)."""
    # 현재가 (토스)
    current = 0.0
    price_data = _toss.get_current_price_kr(body.symbol)
    res = price_data.get("result") if isinstance(price_data, dict) else None
    if res:
        try:
            current = float(res[0].get("lastPrice", 0))
        except (ValueError, TypeError, IndexError):
            current = 0.0

    report = await _run_agent_text(f"{body.symbol} {body.market} market 주식 분석해줘")
    if not report:
        raise HTTPException(status_code=500, detail="분석 결과가 비어있습니다")

    plan = strat.build_proposed_plan(
        body.symbol, body.market, body.name or body.symbol, report, current,
    )

    # 근거 강화: 집중 LLM 추출로 앵커 + 산출근거 보강 (실패 시 결정론적 파싱값 유지)
    try:
        extract_prompt = (
            f"종목: {body.name or body.symbol} ({body.symbol}, {body.market})\n"
            f"현재가: {current}\n\n--- 종합 분석 리포트 ---\n{report}"
        )
        extract_text = await _run_agent_text(extract_prompt, runner=_extract_runner)
        extracted = strat.parse_extracted_anchors(extract_text)
        plan = strat.apply_extracted_anchors(plan, extracted, current)
        _logger.info("strategy_extracted", symbol=body.symbol, ok=bool(extracted))
    except Exception as e:  # 추출 실패가 제안 자체를 막지 않도록
        _logger.warning("strategy_extract_failed", symbol=body.symbol, error=str(e))

    plan["generated_at"] = int(time.time() * 1000)
    await strat.aset_proposed_plan(body.symbol, plan)
    _logger.info("strategy_proposed", symbol=body.symbol, target=plan["target_price"])
    return {"status": "proposed", "plan": plan}


@app.post("/api/strategy/approve")
async def strategy_approve(body: ApprovePlanRequest):
    """제안 플랜을 승인하여 활성화 (사용자 수정값 반영)."""
    proposed = await strat.aget_proposed_plan(body.symbol)
    if not proposed:
        raise HTTPException(status_code=404, detail="제안된 플랜이 없습니다")
    plan = dict(proposed)
    if body.target_price is not None:
        plan["target_price"] = body.target_price
    if body.buy_anchor is not None:
        plan["buy_anchor"] = body.buy_anchor
    plan["source"] = "approved"
    plan["approved_at"] = int(time.time() * 1000)
    # 사다리 materialize (밴드 설정 + 승인된 기대값/적정매수가 기준)
    config = await strat.aget_band_config(body.symbol)
    plan["ladder"] = strat.build_ladder(plan, config)
    await strat.aset_active_plan(body.symbol, plan)
    _logger.info("strategy_approved", symbol=body.symbol, ladder_levels=len(plan["ladder"]))
    return {"status": "active", "plan": plan}


@app.delete("/api/strategy/plans/{symbol}")
async def strategy_deactivate(symbol: str):
    """활성 플랜 비활성화."""
    await strat.adelete_active_plan(symbol)
    return {"status": "deleted", "symbol": symbol}


# ── 가격 워처 (Phase 2: 수동 토글) ──

@app.get("/api/strategy/watcher/status")
async def watcher_status():
    """워처 상태 조회: 잡 실행여부·다음실행·최근 tick 요약·DRY_RUN."""
    sessions = market_sessions()
    return {
        "enabled": await strat.aget_watcher_enabled(),
        "dry_run": settings.DRY_RUN,
        "markets": sessions,
        "market_open": any(sessions.values()),
        **get_watcher_job_info(),
        "last_tick": await strat.aget_watcher_status(),
    }


@app.post("/api/strategy/watcher/start")
async def watcher_start():
    """워처 수동 시작 (5분 인터벌 잡 등록 + enabled=true)."""
    await strat.aset_watcher_enabled(True)
    info = start_watcher()
    _logger.info("watcher_started")
    return {"status": "started", "enabled": True, **info}


@app.post("/api/strategy/watcher/stop")
async def watcher_stop():
    """워처 수동 중지 (잡 제거 + enabled=false)."""
    await strat.aset_watcher_enabled(False)
    info = stop_watcher()
    _logger.info("watcher_stopped")
    return {"status": "stopped", "enabled": False, **info}


# ── 자가진화 퀀트 전략 (Evolution) ──

@app.get("/api/quant/strategy")
async def quant_strategy_active():
    """현재 활성 전략 파라미터 조회."""
    strategy = await qstore.aget_active_strategy()
    return {"strategy": strategy.model_dump()}


@app.get("/api/quant/strategy/history")
async def quant_strategy_history(limit: int = 5):
    """전략 변경 이력(최신순)."""
    return {"history": await qstore.aget_version_history(limit=limit)}


@app.post("/api/quant/strategy/rollback/{version}")
async def quant_strategy_rollback(version: str):
    """지정 버전으로 전략 롤백."""
    restored, msg = await qstore.arollback(version)
    if not restored:
        return JSONResponse({"status": "error", "message": msg}, status_code=404)
    _logger.info("strategy_rollback", version=version)
    return {"status": "rolled_back", "strategy": restored.model_dump()}


@app.post("/api/quant/evolution/run")
async def quant_evolution_run(lookback_days: int = 30):
    """진화 분석 1회 수동 실행 (데이터 충분 시 LLM 제안 → 대기/Telegram)."""
    result = await evolution_runner.run_evolution_analysis(
        lookback_days=lookback_days, trigger="manual",
    )
    return result


@app.post("/api/quant/evolution/approve/{pid}")
async def quant_evolution_approve(pid: str):
    """대기 중인 진화 제안 승인 → 전략 적용."""
    return await evolution_runner.approve_proposal(pid, approved_by="user")


@app.post("/api/quant/evolution/reject/{pid}")
async def quant_evolution_reject(pid: str):
    """대기 중인 진화 제안 거부."""
    return await evolution_runner.reject_proposal(pid)


# ── 디버그: 강제 BUY 테스트 (DRY_RUN 전용) ──

@app.post("/api/debug/test-buy/{symbol}")
async def debug_test_buy(symbol: str):
    """DRY_RUN 상태에서 강제 매수 1회 실행 — 메커니즘 검증용.

    실제 주문 없이 OrderManager → trade_log → 신호 상태까지
    BUY 전체 흐름을 한 번 실행합니다.
    """
    import asyncio, time
    from shared.config import settings as cfg
    if not cfg.DRY_RUN:
        raise HTTPException(status_code=403, detail="DRY_RUN=true일 때만 사용 가능합니다")

    from execution.toss_rest import TossRESTClient
    from execution.order_manager import OrderManager
    from shared.quant import strategy_store as qs
    from shared.quant.signal_state import aput_state
    from shared.quant.trade_log import arecord_trade
    from execution.watcher import _parse_candles

    toss = TossRESTClient()
    om = OrderManager()

    # 현재가 조회 (1m 봉 마지막 종가)
    candle_resp = await asyncio.to_thread(toss.get_candles, symbol.upper(), "1m", 5)
    candles = _parse_candles(candle_resp)
    if not candles:
        raise HTTPException(status_code=502, detail=f"{symbol} 캔들 조회 실패")

    current_price = candles[-1]["closePrice"]
    watchlist = await strat.aget_watchlist()
    watch_item = next((w for w in watchlist if w["symbol"] == symbol.upper()), None)
    budget_usd = float(watch_item["budget_usd"]) if watch_item else 100.0
    entry_qty = max(1, int(budget_usd / current_price))

    # DRY_RUN 주문
    order_result = om.place_limit(symbol.upper(), "US", "BUY", entry_qty, current_price)

    # 신호 상태 저장 (M1_OPEN_FIRST)
    strategy = await qs.aget_active_strategy()
    sl = round(current_price * (1 - 0.05), 2)
    target = round(current_price + (current_price - sl) * 2, 2)
    new_state = {
        "state": "M1_OPEN_FIRST", "method": 1,
        "entry_price": current_price, "stop_loss": sl,
        "target1": target, "target_full": target, "prev_rsi": None,
    }
    await aput_state(symbol.upper(), new_state)

    # trade_log 기록
    now_ms = int(time.time() * 1000)
    await arecord_trade({
        "ts": now_ms, "ticker": symbol.upper(), "signal": "BUY",
        "rsi": None, "sentiment": 0.0, "confidence": 1.0,
        "strategy_version": strategy.version,
        "side": "buy", "quantity": entry_qty, "price": current_price,
        "entry_price": current_price, "return_rate": None,
        "reasoning": "[DEBUG] 강제 매수 테스트",
    })

    _logger.info("debug_test_buy", symbol=symbol, qty=entry_qty, price=current_price)
    return {
        "symbol": symbol.upper(),
        "action": "BUY",
        "order_status": order_result.get("status"),
        "qty": entry_qty,
        "price": current_price,
        "stop_loss": sl,
        "target1": target,
        "budget_usd": budget_usd,
        "signal_state": "M1_OPEN_FIRST",
        "note": "DRY_RUN — 실제 주문 없음, 신호 상태 저장됨",
    }


# ── Telegram 테스트 ──

@app.post("/api/telegram/test")
async def telegram_test():
    """Telegram 연결 테스트 메시지 발송."""
    from shared import notifications
    if not notifications.telegram_enabled():
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다")
    result = await notifications.send_message(
        "✅ Stock ADK 연결 테스트\n\n"
        "MACD+RSI 자동매매 시스템이 정상 연결됐습니다.\n"
        "US 장 마감(16:30 ET) 후 일일 결산 리포트가 이 채널로 발송됩니다."
    )
    return {"status": result.get("status"), "telegram_enabled": True}


# ── MACD+RSI 유니버스 스캐너 ──

class ScreenerRequest(BaseModel):
    symbols: list[str]
    filters: dict | None = None


@app.post("/api/screener/check")
async def screener_check(body: ScreenerRequest):
    """US 종목 유니버스 적합성 판정 (시가총액·Float·상대거래량·갭).

    Body: {"symbols": ["CRWD", "AAPL", ...], "filters": {...} (optional)}
    """
    import asyncio
    from shared.screener import check_stocks
    if not body.symbols:
        raise HTTPException(status_code=400, detail="symbols 필드가 비어 있습니다")
    if len(body.symbols) > 20:
        raise HTTPException(status_code=400, detail="한 번에 최대 20개까지 조회 가능합니다")
    results = await asyncio.to_thread(check_stocks, body.symbols, body.filters)
    return {"results": results, "count": len(results)}


@app.get("/api/portfolio/strategy-fit")
async def portfolio_strategy_fit():
    """현재 Toss 보유종목의 MACD+RSI 전략 적합성 판정.

    Toss holdings → 각 종목 yfinance 조회 → 유니버스 필터 적용.
    """
    import asyncio
    from shared.screener import check_stocks

    holdings_resp = await asyncio.to_thread(_toss.get_balance)
    result = holdings_resp.get("result", holdings_resp) if isinstance(holdings_resp, dict) else {}
    items = result.get("items", []) if isinstance(result, dict) else []

    if not items:
        return {"holdings": [], "summary": {"fit": 0, "border": 0, "reject": 0}}

    symbols = []
    holding_map = {}
    for it in items:
        sym = it.get("symbol", "")
        if sym:
            symbols.append(sym)
            holding_map[sym] = it

    screen_results = await asyncio.to_thread(check_stocks, symbols)

    enriched = []
    for r in screen_results:
        sym = r["symbol"]
        h = holding_map.get(sym, {})
        r["holding_value"] = h.get("marketValue") or h.get("purchaseAmount")
        r["quantity"] = h.get("quantity")
        enriched.append(r)

    summary = {"fit": 0, "border": 0, "reject": 0}
    for r in enriched:
        summary[r.get("fit", "reject")] = summary.get(r.get("fit", "reject"), 0) + 1

    return {"holdings": enriched, "summary": summary}


@app.get("/api/signal/states")
async def signal_states_all():
    """워치리스트 전 종목 신호 상태 일괄 조회."""
    from shared.quant.signal_state import aget_all_states
    watchlist = await strat.aget_watchlist()
    all_states = await aget_all_states()
    strategy = await qstore.aget_active_strategy()

    result = []
    for w in watchlist:
        sym = w.get("symbol", "")
        st = all_states.get(sym, {"state": "IDLE"})
        result.append({
            "symbol": sym,
            "market": w.get("market", "US"),
            "name": w.get("name", sym),
            "budget_usd": w.get("budget_usd", 0),
            "signal_state": st.get("state", "IDLE"),
            "entry_price": st.get("entry_price"),
            "stop_loss": st.get("stop_loss"),
            "target1": st.get("target1"),
            "target_full": st.get("target_full"),
            "method": st.get("method"),
            "prev_rsi": st.get("prev_rsi"),
        })

    return {
        "signals": result,
        "strategy_version": strategy.version,
        "strategy": {
            "macd": strategy.macd.model_dump(),
            "rsi": strategy.rsi.model_dump(),
            "hma_filter": strategy.hma_filter.model_dump(),
        },
    }


# ── 트레이딩 예산 설정 ──

class BudgetRequest(BaseModel):
    budget_usd: float


@app.get("/api/settings/trading-budget")
async def get_trading_budget():
    """총 트레이딩 예산 조회."""
    total = await strat.aget_trading_budget()
    watchlist = await strat.aget_watchlist()
    allocated = await strat.aget_allocated_budget(watchlist)
    return {
        "total_budget_usd": total,
        "allocated_usd": allocated,
        "available_usd": max(0.0, total - allocated),
    }


@app.put("/api/settings/trading-budget")
async def set_trading_budget(body: BudgetRequest):
    """총 트레이딩 예산 설정."""
    if body.budget_usd < 0:
        raise HTTPException(status_code=400, detail="예산은 0 이상이어야 합니다")
    await strat.aset_trading_budget(body.budget_usd)
    _logger.info("trading_budget_set", budget_usd=body.budget_usd)
    return {"status": "ok", "budget_usd": body.budget_usd}


# Mount ADK A2A server
try:
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    adk_app = to_a2a(root_agent, port=ORCHESTRATOR_PORT)

    # FastAPI lifespan does not propagate to mounted sub-apps, so we trigger
    # ADK 초기화를 직접 수행한다. 구버전은 on_startup 리스트, 신버전은
    # lifespan 컨텍스트를 사용하므로 둘 다 처리한다.
    _adk_startup_handlers.extend(getattr(adk_app.router, "on_startup", None) or [])
    _adk_apps.append(adk_app)

    # Mount ADK app at /adk path
    app.mount("/adk", adk_app)
except ImportError:
    pass  # ADK not available


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
