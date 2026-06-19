# Multi-Agent Stock Trading System — Technical Specification

> **목적**: Google ADK + A2A Protocol 기반 멀티에이전트 자동매매 시스템 구현
> **기술 스택**: Python 3.13+, Google ADK v1.0+, A2A Protocol, 토스증권 Open API, Gemini 2.5

---

## 1. 프로젝트 구조

```
trading-system/
├── orchestrator/
│   ├── __init__.py
│   ├── agent.py              # Root Agent (Orchestrator)
│   ├── decision_engine.py    # 가중 합산 & 최종 판단 로직
│   ├── scheduler.py          # 정기 분석 스케줄러 (APScheduler)
│   ├── server.py             # FastAPI + ADK api_server
│   └── Dockerfile
├── sub_agents/
│   ├── news_agent/
│   │   ├── __init__.py
│   │   ├── agent.py          # News & Sentiment Agent
│   │   ├── server.py         # A2A Server (uvicorn)
│   │   ├── tools.py          # 뉴스 수집 & 분석 도구
│   │   └── Dockerfile
│   ├── fundamental_agent/
│   │   ├── __init__.py
│   │   ├── agent.py          # 재무제표 분석 Agent
│   │   ├── server.py
│   │   ├── tools.py          # DART, SEC EDGAR, Yahoo Finance 도구
│   │   └── Dockerfile
│   ├── technical_agent/
│   │   ├── __init__.py
│   │   ├── agent.py          # 차트 기술적 분석 Agent
│   │   ├── server.py
│   │   ├── tools.py          # TA-Lib, pandas-ta 기반 도구
│   │   └── Dockerfile
│   ├── expert_agent/
│   │   ├── __init__.py
│   │   ├── agent.py          # 전문가 신호 수집 Agent
│   │   ├── server.py
│   │   ├── tools.py          # 애널리스트 리포트, 수급 데이터 도구
│   │   └── Dockerfile
│   └── risk_agent/
│       ├── __init__.py
│       ├── agent.py          # 리스크 관리 Agent
│       ├── server.py
│       ├── tools.py          # 포지션 사이징, VaR 계산 도구
│       └── Dockerfile
├── execution/
│   ├── __init__.py
│   ├── toss_rest.py          # 토스증권 REST API 클라이언트
│   ├── order_manager.py      # 주문 상태 관리 & 체결 추적
│   └── websocket_client.py   # 실시간 시세 WebSocket
├── shared/
│   ├── __init__.py
│   ├── models.py             # Pydantic 데이터 모델 (공통)
│   ├── config.py             # 환경변수 & 설정 관리
│   ├── database.py           # PostgreSQL 연결 (SQLAlchemy)
│   └── logger.py             # 구조화 로깅
├── monitoring/
│   ├── dashboard.py          # Streamlit 대시보드
│   └── alerting.py           # 텔레그램/슬랙 알림
├── tests/
│   ├── test_orchestrator.py
│   ├── test_agents/
│   └── test_execution/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 2. 공통 데이터 모델 (shared/models.py)

모든 Sub-Agent 출력과 Orchestrator 입출력에 사용할 Pydantic 모델을 정의합니다.

```python
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class Market(str, Enum):
    KR = "KR"
    US = "US"

class SignalStrength(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"

class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"

class FinancialHealth(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# ── 분석 요청 (Orchestrator → Sub-Agent) ──
class AnalysisRequest(BaseModel):
    ticker: str                    # 종목코드 (예: "005930", "AAPL")
    market: Market                 # KR 또는 US
    timestamp: datetime = Field(default_factory=datetime.now)

# ── News Agent 출력 ──
class NewsAnalysisResult(BaseModel):
    sentiment_score: float = Field(ge=-1.0, le=1.0)     # -1(극부정) ~ +1(극긍정)
    market_regime: MarketRegime
    key_events: list[str]                                 # 주요 이벤트 요약
    news_count: int                                       # 분석한 뉴스 수
    confidence: float = Field(ge=0.0, le=1.0)

# ── Fundamental Agent 출력 ──
class FundamentalAnalysisResult(BaseModel):
    valuation_score: float = Field(ge=0.0, le=100.0)     # 0(고평가) ~ 100(저평가)
    financial_health: FinancialHealth
    fair_value_range: tuple[float, float]                 # (하한, 상한)
    growth_momentum: float = Field(ge=-1.0, le=1.0)
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)

# ── Technical Agent 출력 ──
class TechnicalAnalysisResult(BaseModel):
    technical_signal: SignalStrength
    trend_direction: TrendDirection
    key_levels: dict                # {"support": [...], "resistance": [...]}
    rsi: float | None = None
    macd_histogram: float | None = None
    patterns: list[str]             # 감지된 캔들 패턴
    confidence: float = Field(ge=0.0, le=1.0)

# ── Expert Signal Agent 출력 ──
class ExpertSignalResult(BaseModel):
    consensus_rating: SignalStrength
    target_price_avg: float | None = None
    target_price_range: tuple[float, float] | None = None
    institutional_flow: float        # 양수=순매수, 음수=순매도
    insider_activity: list[str]
    analyst_count: int
    confidence: float = Field(ge=0.0, le=1.0)

# ── Risk Agent 출력 ──
class RiskAnalysisResult(BaseModel):
    position_size: int               # 추천 매수 수량
    stop_loss_price: float
    take_profit_price: float
    risk_level: RiskLevel
    max_loss_amount: float           # 최대 예상 손실금
    risk_reward_ratio: float
    confidence: float = Field(ge=0.0, le=1.0)

# ── Orchestrator 최종 결정 ──
class TradeDecision(BaseModel):
    ticker: str
    market: Market
    action: str                      # "BUY" | "SELL" | "HOLD"
    final_score: float               # 가중 합산 점수
    quantity: int
    target_price: float
    stop_loss: float
    take_profit: float
    reasoning: str                   # 의사결정 근거 요약
    agent_scores: dict[str, float]   # 각 Agent 스코어
    timestamp: datetime = Field(default_factory=datetime.now)
```

---

## 3. Sub-Agent 구현 상세

### 3.1 News Agent (Port: 8001)

**역할**: 종목별 뉴스 수집, 시장 시황 분석, 센티먼트 스코어 산출

```python
# sub_agents/news_agent/tools.py
from google.adk.tools import FunctionTool

def collect_news(ticker: str, market: str = "US") -> dict:
    """
    종목 관련 뉴스를 수집하고 센티먼트를 분석합니다.
    
    Args:
        ticker: 종목코드 (예: "AAPL", "005930")
        market: "US" 또는 "KR"
    
    Returns:
        dict with keys: sentiment_score, market_regime, key_events, 
                        news_count, confidence
    """
    # 구현 사항:
    # 1. Google Search API 또는 News API로 최근 7일 뉴스 수집
    # 2. 한국: 네이버 뉴스 API, 미국: Google News / Seeking Alpha
    # 3. Gemini로 각 뉴스의 긍정/부정 분류
    # 4. 전체 센티먼트 스코어 산출 (-1.0 ~ 1.0)
    # 5. 시장 전체 시황 판단 (FRED API: 금리, 실업률 등)
    pass

def analyze_market_macro(market: str = "US") -> dict:
    """
    거시경제 지표를 분석하여 시장 전체 시황을 판단합니다.
    
    Args:
        market: "US" 또는 "KR"
    
    Returns:
        dict with keys: market_regime, macro_indicators, risk_factors
    """
    # 구현 사항:
    # 1. FRED API: 미국 국채 금리, VIX, 실업률, CPI
    # 2. 한국은행 API: 기준금리, 환율, 소비자물가
    # 3. Fear & Greed Index
    pass

news_tools = [
    FunctionTool(func=collect_news),
    FunctionTool(func=analyze_market_macro),
]
```

```python
# sub_agents/news_agent/agent.py
from google.adk.agents import Agent
from tools import news_tools

root_agent = Agent(
    name="news_agent",
    model="gemini-2.5-flash",
    instruction="""
    당신은 주식 뉴스 & 시황 분석 전문 에이전트입니다.
    
    [역할]
    1. 요청된 종목의 최근 뉴스를 수집하고 센티먼트를 분석합니다
    2. 시장 전체 거시경제 상황을 평가합니다
    3. 뉴스 기반 이벤트 리스크를 식별합니다
    
    [출력 규칙]
    - sentiment_score: -1.0(극부정) ~ +1.0(극긍정) 사이의 실수
    - market_regime: "bull", "bear", "sideways" 중 하나
    - key_events: 주요 이벤트 3-5개를 한줄 요약 리스트
    - confidence: 분석 신뢰도 0.0 ~ 1.0
    
    반드시 collect_news 도구를 사용하여 최신 데이터를 수집한 후 분석하세요.
    """,
    description="종목 뉴스 수집 및 시황/센티먼트 분석 에이전트",
    tools=news_tools,
)
```

```python
# sub_agents/news_agent/server.py
from google.adk.agents.a2a import to_a2a
from agent import root_agent
import uvicorn

app = to_a2a(root_agent)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 3.2 Fundamental Agent (Port: 8002)

**역할**: 재무제표 3표 분석, 밸류에이션 계산, 동종업계 비교

```python
# sub_agents/fundamental_agent/tools.py

def analyze_financials(ticker: str, market: str = "US") -> dict:
    """
    재무제표를 분석하고 밸류에이션 스코어를 산출합니다.
    
    구현 사항:
    1. 데이터 소스:
       - 한국: DART OpenAPI (https://opendart.fss.or.kr/)
       - 미국: SEC EDGAR API, Yahoo Finance (yfinance 패키지)
    2. 분석 지표:
       - 수익성: ROE, ROA, 영업이익률, 순이익률
       - 안전성: 부채비율, 유동비율, 이자보상배율
       - 성장성: 매출 성장률, 이익 성장률 (YoY, QoQ)
       - 밸류에이션: PER, PBR, PSR, EV/EBITDA
    3. 동종업계 비교: 동일 섹터 평균 대비 위치
    4. DCF 간이 모델로 적정가치 범위 산출
    """
    pass

def get_peer_comparison(ticker: str, market: str = "US") -> dict:
    """동종업계 대비 재무 지표를 비교합니다."""
    pass
```

```python
# sub_agents/fundamental_agent/agent.py
from google.adk.agents import Agent
from tools import FunctionTool, analyze_financials, get_peer_comparison

root_agent = Agent(
    name="fundamental_agent",
    model="gemini-2.5-flash",
    instruction="""
    당신은 재무제표 분석 전문 에이전트입니다.
    
    [역할]
    1. 종목의 최근 4분기 + 연간 재무제표를 분석합니다
    2. 밸류에이션 멀티플을 계산하고 적정가치를 산출합니다
    3. 동종업계 대비 재무 건전성을 평가합니다
    
    [출력 규칙]
    - valuation_score: 0(극도로 고평가) ~ 100(극도로 저평가)
    - financial_health: A/B/C/D/F 등급
    - fair_value_range: [하한가, 상한가] 적정주가 범위
    - growth_momentum: -1.0(역성장) ~ +1.0(고성장)
    
    반드시 도구를 사용하여 실제 재무 데이터를 조회한 후 분석하세요.
    """,
    description="재무제표 분석 및 밸류에이션 평가 에이전트",
    tools=[
        FunctionTool(func=analyze_financials),
        FunctionTool(func=get_peer_comparison),
    ],
)
```

### 3.3 Technical Agent (Port: 8003)

**역할**: 차트 기술적 지표 분석, 패턴 인식, 지지/저항선 탐지

```python
# sub_agents/technical_agent/tools.py
import pandas as pd
import pandas_ta as ta

def analyze_technical(ticker: str, market: str = "US") -> dict:
    """
    차트 기술적 분석을 수행합니다.
    
    구현 사항:
    1. 데이터 소스:
       - 미국: yfinance (1년 일봉 + 최근 1개월 시간봉)
       - 한국: pykrx 또는 토스증권 Open API 시세 조회
    2. 기술적 지표:
       - 이동평균선: SMA(20,50,200), EMA(12,26)
       - 오실레이터: RSI(14), Stochastic(14,3,3)
       - 추세: MACD(12,26,9), ADX(14)
       - 변동성: Bollinger Bands(20,2), ATR(14)
       - 거래량: OBV, Volume SMA
    3. 패턴 인식:
       - 골든크로스/데드크로스
       - 더블탑/더블바텀
       - 헤드앤숄더
       - 캔들 패턴 (도지, 해머, 잉핑 등)
    4. 지지/저항선:
       - 피봇 포인트
       - 최근 고점/저점 기반 수평선
    """
    pass

def detect_patterns(ticker: str, market: str = "US") -> dict:
    """캔들스틱 패턴을 감지합니다."""
    pass
```

```python
# sub_agents/technical_agent/agent.py
from google.adk.agents import Agent
from tools import FunctionTool, analyze_technical, detect_patterns

root_agent = Agent(
    name="technical_agent",
    model="gemini-2.5-flash",
    instruction="""
    당신은 차트 기술적 분석 전문 에이전트입니다.
    
    [역할]
    1. 종목의 가격/거래량 데이터를 기반으로 기술적 지표를 계산합니다
    2. 차트 패턴을 인식하고 매매 신호를 생성합니다
    3. 주요 지지선/저항선을 식별합니다
    
    [출력 규칙]
    - technical_signal: "strong_buy", "buy", "hold", "sell", "strong_sell"
    - trend_direction: "up", "down", "neutral"
    - key_levels: {"support": [가격들], "resistance": [가격들]}
    - patterns: 감지된 패턴 이름 리스트
    - confidence: 0.0 ~ 1.0
    
    여러 지표가 동일 방향을 가리킬수록 confidence를 높게 설정하세요.
    """,
    description="차트 기술적 분석 및 패턴 인식 에이전트",
    tools=[
        FunctionTool(func=analyze_technical),
        FunctionTool(func=detect_patterns),
    ],
)
```

### 3.4 Expert Signal Agent (Port: 8004)

**역할**: 애널리스트 리포트 수집, 기관/외국인 수급 분석, 내부자 거래 모니터링

```python
# sub_agents/expert_agent/tools.py

def collect_analyst_ratings(ticker: str, market: str = "US") -> dict:
    """
    애널리스트 목표가 및 투자의견을 수집합니다.
    
    구현 사항:
    1. 미국: Yahoo Finance analyst recommendations, Tipranks
    2. 한국: 증권사 리포트 (네이버 금융, FnGuide)
    3. 컨센서스 목표가 평균/중앙값 계산
    4. 최근 3개월 목표가 변경 추이
    """
    pass

def analyze_institutional_flow(ticker: str, market: str = "US") -> dict:
    """
    기관/외국인 매매 동향을 분석합니다.
    
    구현 사항:
    1. 한국: KRX 정보데이터시스템 - 투자자별 매매동향
    2. 미국: SEC 13F Filing, Institutional holdings
    3. 최근 5/10/20일 순매수/순매도 추이
    """
    pass

def check_insider_trading(ticker: str, market: str = "US") -> dict:
    """
    내부자 거래(대량보유 변동)를 확인합니다.
    
    구현 사항:
    1. 한국: DART 대량보유상황보고
    2. 미국: SEC Form 4 (Insider transactions)
    """
    pass
```

```python
# sub_agents/expert_agent/agent.py
from google.adk.agents import Agent

root_agent = Agent(
    name="expert_agent",
    model="gemini-2.5-flash",
    instruction="""
    당신은 전문가 매매신호 수집 에이전트입니다.
    
    [역할]
    1. 증권사 애널리스트들의 목표가와 투자의견을 수집합니다
    2. 기관투자자와 외국인의 매매 동향을 분석합니다
    3. 내부자(임원/대주주) 거래 내역을 모니터링합니다
    
    [출력 규칙]
    - consensus_rating: 전체 애널리스트 컨센서스
    - target_price_avg: 평균 목표가
    - institutional_flow: 양수(순매수), 음수(순매도)
    - insider_activity: 최근 내부자 거래 요약
    - confidence: 0.0 ~ 1.0 (애널리스트 수가 많을수록 높게)
    """,
    description="애널리스트 리포트 및 기관/외국인 수급 분석 에이전트",
    tools=[...],  # 위 도구들 등록
)
```

### 3.5 Risk Manager Agent (Port: 8005)

**역할**: 포지션 사이징, 손절/익절 설정, 포트폴리오 리스크 관리

```python
# sub_agents/risk_agent/tools.py

def calculate_position_size(
    ticker: str,
    market: str,
    account_balance: float,
    current_price: float,
    atr: float,
    risk_per_trade: float = 0.02,  # 1회 거래당 최대 리스크 2%
) -> dict:
    """
    켈리 기준 + ATR 기반 포지션 사이징을 계산합니다.
    
    구현 사항:
    1. ATR 기반 손절 거리 계산 (2 × ATR)
    2. 계좌 잔고 대비 리스크 금액 산출
    3. 최대 포지션 비율 제한 (단일 종목 20%)
    4. 최종 매수 수량 결정
    """
    pass

def assess_portfolio_risk(
    current_positions: list[dict],
    new_trade: dict,
) -> dict:
    """
    신규 매매가 포트폴리오에 미치는 리스크를 평가합니다.
    
    구현 사항:
    1. 기존 보유 종목과의 상관관계 분석
    2. 섹터 집중도 확인
    3. 포트폴리오 VaR (Value at Risk) 산출
    4. 최대 동시 보유 종목 수 제한
    """
    pass
```

```python
# sub_agents/risk_agent/agent.py
from google.adk.agents import Agent

root_agent = Agent(
    name="risk_agent",
    model="gemini-2.5-flash",
    instruction="""
    당신은 리스크 관리 전문 에이전트입니다.
    
    [역할]
    1. 매매 수량(포지션 사이즈)을 계산합니다
    2. 손절가와 익절가를 설정합니다
    3. 포트폴리오 전체 리스크를 관리합니다
    
    [출력 규칙]
    - position_size: 추천 매수 수량 (정수)
    - stop_loss_price: 손절 가격
    - take_profit_price: 익절 가격
    - risk_level: "low", "medium", "high"
    - risk_reward_ratio: 손익비 (1.0 이상이어야 유효)
    
    [안전 규칙 — 절대 위반 금지]
    - 단일 종목 최대 투자비율: 계좌의 20%
    - 1회 거래 최대 리스크: 계좌의 2%
    - 최소 손익비: 1.5:1
    - 동시 보유 최대 종목 수: 10개
    """,
    description="포지션 사이징 및 리스크 관리 에이전트",
    tools=[...],
)
```

---

## 4. Orchestrator Agent 구현

### 4.1 Root Agent 정의

```python
# orchestrator/agent.py
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from shared.config import settings

# ── 원격 Sub-Agent 연결 (A2A Protocol) ──
news_agent = RemoteA2aAgent(
    name="news_agent",
    description="종목 뉴스 수집 및 시황/센티먼트 분석",
    agent_url=f"http://{settings.NEWS_AGENT_HOST}:{settings.NEWS_AGENT_PORT}/a2a/news_agent",
)

fundamental_agent = RemoteA2aAgent(
    name="fundamental_agent",
    description="재무제표 분석 및 밸류에이션 평가",
    agent_url=f"http://{settings.FUNDAMENTAL_AGENT_HOST}:{settings.FUNDAMENTAL_AGENT_PORT}/a2a/fundamental_agent",
)

technical_agent = RemoteA2aAgent(
    name="technical_agent",
    description="차트 기술적 분석 및 패턴 인식",
    agent_url=f"http://{settings.TECHNICAL_AGENT_HOST}:{settings.TECHNICAL_AGENT_PORT}/a2a/technical_agent",
)

expert_agent = RemoteA2aAgent(
    name="expert_agent",
    description="애널리스트 리포트 및 기관/외국인 수급 분석",
    agent_url=f"http://{settings.EXPERT_AGENT_HOST}:{settings.EXPERT_AGENT_PORT}/a2a/expert_agent",
)

risk_agent = RemoteA2aAgent(
    name="risk_agent",
    description="포지션 사이징 및 리스크 관리",
    agent_url=f"http://{settings.RISK_AGENT_HOST}:{settings.RISK_AGENT_PORT}/a2a/risk_agent",
)

# ── Orchestrator (Root Agent) ──
root_agent = Agent(
    name="trading_orchestrator",
    model="gemini-2.5-pro",
    instruction="""
    당신은 주식 자동매매 시스템의 오케스트레이터입니다.
    사용자가 종목 분석을 요청하면 다음 프로세스를 수행합니다:
    
    [분석 프로세스]
    1. 사용자로부터 종목코드(ticker)와 시장(KR/US)을 확인합니다
    2. 모든 sub-agent에게 해당 종목의 분석을 요청합니다:
       - news_agent: "다음 종목의 뉴스와 시황을 분석해주세요: {ticker} ({market})"
       - fundamental_agent: "다음 종목의 재무제표를 분석해주세요: {ticker} ({market})"
       - technical_agent: "다음 종목의 기술적 분석을 해주세요: {ticker} ({market})"
       - expert_agent: "다음 종목의 전문가 신호를 수집해주세요: {ticker} ({market})"
       - risk_agent: "현재 계좌 상태를 고려하여 리스크를 평가해주세요: {ticker} ({market})"
    3. 각 agent의 결과를 수집하여 가중 합산합니다
    4. 최종 매수/매도/홀드 결정을 내립니다
    
    [가중치]
    - 기술적 분석 (technical_agent): 30%
    - 재무 분석 (fundamental_agent): 25%
    - 뉴스/센티먼트 (news_agent): 20%
    - 전문가 신호 (expert_agent): 15%
    - 리스크 조정 (risk_agent): 10%
    
    [의사결정 기준]
    - 가중 합산 점수 > +0.3: BUY (매수)
    - 가중 합산 점수 < -0.3: SELL (매도)
    - 그 외: HOLD (관망)
    
    [안전 규칙]
    - 단일 종목 최대 투자비율: 20%
    - 일일 최대 거래 횟수: 10회
    - 모든 매매에 손절가 필수 설정
    - Risk Agent가 "high" 리스크를 반환하면 거래량을 50% 감소
    
    모든 분석 결과와 최종 판단 근거를 상세히 설명해주세요.
    """,
    sub_agents=[
        news_agent,
        fundamental_agent,
        technical_agent,
        expert_agent,
        risk_agent,
    ],
)
```

### 4.2 의사결정 엔진

```python
# orchestrator/decision_engine.py
from shared.models import TradeDecision, Market

WEIGHTS = {
    "technical": 0.30,
    "fundamental": 0.25,
    "news": 0.20,
    "expert": 0.15,
    "risk": 0.10,
}

THRESHOLDS = {
    "buy": 0.3,
    "sell": -0.3,
}

def compute_final_score(agent_results: dict[str, float]) -> float:
    """각 Agent 스코어를 가중 합산합니다."""
    score = sum(
        agent_results.get(key, 0.0) * weight
        for key, weight in WEIGHTS.items()
    )
    return round(score, 4)

def make_decision(
    ticker: str,
    market: Market,
    agent_results: dict[str, float],
    risk_output: dict,
) -> TradeDecision:
    """최종 매매 의사결정을 생성합니다."""
    final_score = compute_final_score(agent_results)
    
    if final_score > THRESHOLDS["buy"]:
        action = "BUY"
    elif final_score < THRESHOLDS["sell"]:
        action = "SELL"
    else:
        action = "HOLD"
    
    # 리스크 레벨이 HIGH면 수량 50% 감소
    quantity = risk_output.get("position_size", 0)
    if risk_output.get("risk_level") == "high":
        quantity = max(1, quantity // 2)
    
    return TradeDecision(
        ticker=ticker,
        market=market,
        action=action,
        final_score=final_score,
        quantity=quantity,
        target_price=risk_output.get("current_price", 0),
        stop_loss=risk_output.get("stop_loss_price", 0),
        take_profit=risk_output.get("take_profit_price", 0),
        reasoning=f"가중합산 {final_score:.3f} → {action}",
        agent_scores=agent_results,
    )
```

---

## 5. 토스증권 Open API 연동

### 5.1 REST API 클라이언트

> **참고**: 토스증권 Open API는 OAuth 2.0(client_credentials, form-urlencoded) 기반 HTTP API입니다.
> Base URL `https://openapi.tossinvest.com`. KR/US 주문을 단일 엔드포인트(`/api/v1/orders`)로
> 통합 처리하며 TR_ID 개념이 없고, 모든 숫자 필드는 문자열입니다. 실시간 시세(WebSocket)는
> 미지원(REST only)이라 시세는 폴링으로 조회합니다. 전체 구현은 `execution/toss_rest.py` 참조.

```python
# execution/toss_rest.py (요약)
from shared.config import settings

class TossRESTClient:
    """토스증권 Open API 클라이언트"""

    BASE_URL = "https://openapi.tossinvest.com"

    def __init__(self):
        self.client_id = settings.TOSS_API_KEY         # client_id (tsck_live_...)
        self.client_secret = settings.TOSS_SECRET_KEY  # client_secret (tssk_live_...)
        self._account_seq = settings.TOSS_ACCOUNT_SEQ or None  # 비우면 /api/v1/accounts 자동 조회

    def _ensure_token(self): ...   # OAuth client_credentials(form-urlencoded), 만료 60초 전 갱신

    # ── 주문 (KR/US 단일 엔드포인트, 거래소 코드 불필요) ──
    def order_kr_stock(self, ticker, qty, price, order_type="BUY") -> dict: ...
    def order_us_stock(self, ticker, qty, price, order_type="BUY") -> dict: ...

    # ── 조회 ──
    def get_balance(self) -> dict: ...                 # 계좌 잔고/보유 종목
    def get_current_price_kr(self, ticker) -> dict: ...
    def get_prices(self, symbols) -> dict: ...         # 복수 종목 현재가(워처용)
    def get_candles(self, *args) -> dict: ...          # 일/분봉
```

### 5.2 주문 관리자

```python
# execution/order_manager.py
from shared.models import TradeDecision
from execution.toss_rest import TossRESTClient
from shared.database import save_trade_log
import logging

logger = logging.getLogger(__name__)

class OrderManager:
    """매매 의사결정을 실제 주문으로 변환하고 관리합니다."""
    
    def __init__(self, dry_run: bool = True):
        self.client = TossRESTClient()
        self.dry_run = dry_run  # True면 주문 미실행 (로그만)
        self.daily_trade_count = 0
        self.max_daily_trades = 10
    
    def execute(self, decision: TradeDecision) -> dict:
        """TradeDecision을 받아 주문을 실행합니다."""
        
        if decision.action == "HOLD":
            logger.info(f"[HOLD] {decision.ticker} - 관망")
            return {"status": "hold", "decision": decision}
        
        if self.daily_trade_count >= self.max_daily_trades:
            logger.warning("일일 최대 거래 횟수 도달")
            return {"status": "limit_reached"}
        
        # Dry run 모드
        if self.dry_run:
            logger.info(f"[DRY RUN] {decision.action} {decision.ticker} "
                       f"x{decision.quantity} @ {decision.target_price}")
            save_trade_log(decision, status="dry_run")
            return {"status": "dry_run", "decision": decision}
        
        # 실제 주문 실행
        try:
            if decision.market == "KR":
                result = self.client.order_kr_stock(
                    ticker=decision.ticker,
                    qty=decision.quantity,
                    price=int(decision.target_price),
                    order_type=decision.action,
                )
            else:
                result = self.client.order_us_stock(
                    ticker=decision.ticker,
                    qty=decision.quantity,
                    price=decision.target_price,
                    order_type=decision.action,
                )
            
            self.daily_trade_count += 1
            save_trade_log(decision, status="executed", result=result)
            
            # 알림 전송
            send_notification(
                f"🔔 {decision.action} {decision.ticker} "
                f"x{decision.quantity} @ {decision.target_price}\n"
                f"Score: {decision.final_score:.3f}\n"
                f"Reason: {decision.reasoning}"
            )
            
            return {"status": "executed", "result": result}
            
        except Exception as e:
            logger.error(f"주문 실행 실패: {e}")
            save_trade_log(decision, status="failed", error=str(e))
            return {"status": "failed", "error": str(e)}
```

---

## 6. 설정 관리

```python
# shared/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str
    
    # 토스증권 Open API
    TOSS_API_KEY: str = ""        # client_id (tsck_live_...)
    TOSS_SECRET_KEY: str = ""     # client_secret (tssk_live_...)
    TOSS_ACCOUNT_SEQ: str = ""    # 계좌 시퀀스(비우면 /api/v1/accounts 자동 조회)
    
    # Sub-Agent 호스트 (Docker Compose 서비스명)
    NEWS_AGENT_HOST: str = "news-agent"
    NEWS_AGENT_PORT: int = 8001
    FUNDAMENTAL_AGENT_HOST: str = "fundamental-agent"
    FUNDAMENTAL_AGENT_PORT: int = 8002
    TECHNICAL_AGENT_HOST: str = "technical-agent"
    TECHNICAL_AGENT_PORT: int = 8003
    EXPERT_AGENT_HOST: str = "expert-agent"
    EXPERT_AGENT_PORT: int = 8004
    RISK_AGENT_HOST: str = "risk-agent"
    RISK_AGENT_PORT: int = 8005
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@postgres:5432/trading"
    REDIS_URL: str = "redis://redis:6379/0"
    
    # 알림
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SLACK_WEBHOOK_URL: str = ""
    
    # 거래 제한
    MAX_SINGLE_STOCK_RATIO: float = 0.20   # 단일 종목 최대 20%
    MAX_RISK_PER_TRADE: float = 0.02       # 1회 거래 리스크 2%
    MAX_DAILY_TRADES: int = 10
    DRY_RUN: bool = True                    # True면 주문 미실행
    
    class Config:
        env_file = ".env"

settings = Settings()
```

```
# .env.example
GEMINI_API_KEY=your_gemini_api_key
TOSS_API_KEY=your_toss_client_id
TOSS_SECRET_KEY=your_toss_client_secret
TOSS_ACCOUNT_SEQ=
DATABASE_URL=postgresql://trading:password@localhost:5432/trading
REDIS_URL=redis://localhost:6379/0
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DRY_RUN=true
```

---

## 7. Docker Compose

```yaml
# docker-compose.yml
version: "3.9"

services:
  orchestrator:
    build: ./orchestrator
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - news-agent
      - fundamental-agent
      - technical-agent
      - expert-agent
      - risk-agent
      - redis
      - postgres
    restart: unless-stopped

  news-agent:
    build: ./sub_agents/news_agent
    ports:
      - "8001:8001"
    env_file: .env
    restart: unless-stopped

  fundamental-agent:
    build: ./sub_agents/fundamental_agent
    ports:
      - "8002:8002"
    env_file: .env
    restart: unless-stopped

  technical-agent:
    build: ./sub_agents/technical_agent
    ports:
      - "8003:8003"
    env_file: .env
    restart: unless-stopped

  expert-agent:
    build: ./sub_agents/expert_agent
    ports:
      - "8004:8004"
    env_file: .env
    restart: unless-stopped

  risk-agent:
    build: ./sub_agents/risk_agent
    ports:
      - "8005:8005"
    env_file: .env
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  pgdata:
```

---

## 8. 개발 순서 (권장)

| 순서 | 작업 | 예상 기간 |
|------|------|-----------|
| 1 | 프로젝트 scaffolding + shared 모듈 (models, config, database) | 1일 |
| 2 | Technical Agent 단독 구현 & A2A Server 노출 테스트 | 3일 |
| 3 | News Agent 구현 | 3일 |
| 4 | Fundamental Agent 구현 | 3일 |
| 5 | Expert Signal Agent 구현 | 3일 |
| 6 | Risk Manager Agent 구현 | 2일 |
| 7 | Orchestrator Agent + Decision Engine | 3일 |
| 8 | 토스증권 Open API 연동 | 2일 |
| 9 | Docker Compose 통합 + 전체 E2E 테스트 | 2일 |
| 10 | 모니터링 대시보드 + 알림 | 2일 |
| 11 | 모의투자 실전 테스트 (2주 이상 권장) | 14일+ |

---

## 9. 의존성 (pyproject.toml)

```toml
[project]
name = "trading-system"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # Agent Framework
    "google-adk[a2a]>=1.6.1",
    
    # Web Framework
    "uvicorn>=0.30.0",
    "fastapi>=0.115.0",
    
    # Data & Analysis
    "pandas>=2.2.0",
    "pandas-ta>=0.3.14b",
    "yfinance>=0.2.40",
    "pykrx>=1.0.45",       # 한국 주식 데이터
    "ta-lib",                # 기술적 분석 (별도 C 라이브러리 설치 필요)
    
    # LLM & AI
    "google-genai>=1.0.0",
    
    # Database
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",
    "redis>=5.0.0",
    
    # HTTP
    "httpx>=0.27.0",
    "requests>=2.31.0",
    
    # Config & Validation
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-dotenv>=1.0.0",
    
    # Monitoring
    "streamlit>=1.37.0",
    "python-telegram-bot>=21.0",
    
    # Scheduling
    "apscheduler>=3.10.0",
    
    # Utilities
    "structlog>=24.0.0",
    "numpy>=1.26.0",
    "scipy>=1.13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.5.0",
]
```

---

## 10. 중요 참고사항

1. **토스증권 Open API**: OAuth 2.0(client_credentials) 기반 HTTP API. 개발자 포털(developers.tossinvest.com)에서 앱 등록 후 client_id/secret 발급. 단일 토큰·IP 허용목록 등 제약은 공식 문서에서 확인.

2. **API 호출 제한**: 토스 Open API도 호출 빈도 제한이 있으므로 재시도/백오프와 폴링 주기 조절 필수.

3. **모의투자 우선**: `DRY_RUN=true`로 시작하고, 모의투자 계좌로 최소 2주 이상 테스트 후 실전 적용.

4. **금융 리스크**: 자동매매 시스템은 예상치 못한 손실을 초래할 수 있음. 반드시 손절 로직과 일일 거래 제한을 적용할 것.

5. **Google ADK 버전**: Python ADK v1.0.0+ 사용. `pip install google-adk[a2a]`로 A2A 지원 포함 설치.

6. **A2A vs MCP**: A2A는 Agent 간 통신, MCP는 Agent-Tool 통신. 외부 API 연동은 MCP Tool로, Agent 간 협업은 A2A로 구현.