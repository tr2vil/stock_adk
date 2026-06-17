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
from shared.logger import get_logger
from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import root_agent
from .decision_engine import reload_config as reload_decision_config
from .scheduler import start_scheduler, stop_scheduler
from execution.toss_rest import TossRESTClient

_logger = get_logger("orchestrator.server")

# InMemoryRunner for REST API analysis
_runner = InMemoryRunner(agent=root_agent, app_name="stock_analysis")

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
        # start_scheduler()  # Uncomment to enable scheduled analysis
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
