"""퀀트 전략 / 진화 제안 Pydantic 스키마.

strategy.yaml 의 구조를 검증하고, Evolution Agent(LLM) 출력 파싱에 사용한다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Momentum(BaseModel):
    rsi_buy_threshold: float = 30
    rsi_sell_threshold: float = 70
    ma_period: int = 20
    sentiment_min: float = -0.3


class StopLoss(BaseModel):
    rate: float = 0.05


class NewsDefense(BaseModel):
    sentiment_threshold: float = -0.7
    confidence_min: float = 0.8


class Position(BaseModel):
    """리스크 안전구역 — 진화가 변경할 수 없는 섹션."""
    max_single_weight: float = 0.20
    daily_loss_limit: float = 0.03


class StrategyConfig(BaseModel):
    """활성 전략 전체 스냅샷."""
    version: str = "1.0.0"
    updated_at: str = ""
    updated_by: str = "seed"
    momentum: Momentum = Field(default_factory=Momentum)
    stop_loss: StopLoss = Field(default_factory=StopLoss)
    news_defense: NewsDefense = Field(default_factory=NewsDefense)
    position: Position = Field(default_factory=Position)

    def get_param(self, path: str):
        """점 경로로 파라미터 조회 (예: 'momentum.rsi_buy_threshold')."""
        section, _, key = path.partition(".")
        obj = getattr(self, section, None)
        if obj is None or not key:
            return None
        return getattr(obj, key, None)


class ProposedChange(BaseModel):
    """진화 제안의 단일 파라미터 변경."""
    param: str                      # "momentum.rsi_buy_threshold"
    current: float | int | None = None
    proposed: float | int
    reason: str = ""


class EvolutionProposal(BaseModel):
    """Evolution Agent(LLM) 출력."""
    analysis: str = ""
    changes: list[ProposedChange] = Field(default_factory=list)
    expected_improvement: str = ""
    confidence: float = 0.0
