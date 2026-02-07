"""
Shared Pydantic Data Models for Trading System.
Based on TRADING_SYSTEM_SPEC.md Section 2.
"""
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class Market(str, Enum):
    """Market identifier."""
    KR = "KR"
    US = "US"


class SignalStrength(str, Enum):
    """Trading signal strength levels."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TrendDirection(str, Enum):
    """Trend direction indicators."""
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class MarketRegime(str, Enum):
    """Market regime classification."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


class FinancialHealth(str, Enum):
    """Financial health grade."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class RiskLevel(str, Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Analysis Request (Orchestrator → Sub-Agent) ──
class AnalysisRequest(BaseModel):
    """Analysis request from Orchestrator to Sub-Agent."""
    ticker: str
    market: Market
    timestamp: datetime = Field(default_factory=datetime.now)


# ── News Agent Output ──
class NewsAnalysisResult(BaseModel):
    """Output from News Agent."""
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    market_regime: MarketRegime
    key_events: list[str]
    news_count: int
    confidence: float = Field(ge=0.0, le=1.0)


# ── Fundamental Agent Output ──
class FundamentalAnalysisResult(BaseModel):
    """Output from Fundamental Agent."""
    valuation_score: float = Field(ge=0.0, le=100.0)
    financial_health: FinancialHealth
    fair_value_range: tuple[float, float]
    growth_momentum: float = Field(ge=-1.0, le=1.0)
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)


# ── Technical Agent Output ──
class TechnicalAnalysisResult(BaseModel):
    """Output from Technical Agent."""
    technical_signal: SignalStrength
    trend_direction: TrendDirection
    key_levels: dict  # {"support": [...], "resistance": [...]}
    rsi: float | None = None
    macd_histogram: float | None = None
    patterns: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


# ── Expert Signal Agent Output ──
class ExpertSignalResult(BaseModel):
    """Output from Expert Signal Agent."""
    consensus_rating: SignalStrength
    target_price_avg: float | None = None
    target_price_range: tuple[float, float] | None = None
    institutional_flow: float
    insider_activity: list[str]
    analyst_count: int
    confidence: float = Field(ge=0.0, le=1.0)


# ── Risk Agent Output ──
class RiskAnalysisResult(BaseModel):
    """Output from Risk Agent."""
    position_size: int
    stop_loss_price: float
    take_profit_price: float
    risk_level: RiskLevel
    max_loss_amount: float
    risk_reward_ratio: float
    confidence: float = Field(ge=0.0, le=1.0)


# ── Orchestrator Final Decision ──
class TradeDecision(BaseModel):
    """Final trade decision from Orchestrator."""
    ticker: str
    market: Market
    action: str  # "BUY" | "SELL" | "HOLD"
    final_score: float
    quantity: int
    target_price: float
    stop_loss: float
    take_profit: float
    reasoning: str
    agent_scores: dict[str, float]
    timestamp: datetime = Field(default_factory=datetime.now)
