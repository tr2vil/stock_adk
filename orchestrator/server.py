"""
FastAPI + ADK API Server for Orchestrator
RESTful API와 ADK Agent를 통합한 서버
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

import os
import time
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.middleware import A2ALoggingMiddleware
from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import root_agent
from .scheduler import start_scheduler, stop_scheduler

# InMemoryRunner for REST API analysis
_runner = InMemoryRunner(agent=root_agent, app_name="stock_analysis")

# ADK sub-app startup handlers (populated below, executed in lifespan)
_adk_startup_handlers = []


# Lifespan handler for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: trigger ADK sub-app route registration
    # to_a2a() registers A2A routes in on_startup, but mounted sub-apps'
    # startup events are not called automatically by FastAPI's lifespan.
    for handler in _adk_startup_handlers:
        await handler()
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


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


# API Endpoints
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


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


# Mount ADK A2A server
try:
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    adk_app = to_a2a(root_agent, port=ORCHESTRATOR_PORT)

    # Capture startup handlers before mounting — FastAPI lifespan does not
    # propagate on_startup to mounted sub-apps, so we trigger them manually.
    _adk_startup_handlers.extend(adk_app.router.on_startup)

    # Mount ADK app at /adk path
    app.mount("/adk", adk_app)
except ImportError:
    pass  # ADK not available


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
