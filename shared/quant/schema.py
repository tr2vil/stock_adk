"""퀀트 전략 / 진화 제안 Pydantic 스키마 (MACD+RSI 모멘텀 전략 v2).

strategy.yaml 구조를 검증하고 Evolution Agent(LLM) 출력 파싱에 사용한다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MACDConfig(BaseModel):
    fast: int = 12      # 단기 EMA 기간
    slow: int = 26      # 장기 EMA 기간
    signal: int = 9     # 시그널 EMA 기간


class RSIConfig(BaseModel):
    period: int = 14
    buy_low: float = 50           # 정상 진입 RSI 하한 (50 이상)
    buy_high: float = 70          # 정상 진입 RSI 상한 (70 이상 → 눌림목 대기)
    pullback_zone_high: float = 55  # 눌림목 대기 시 반등 인정 RSI 상한


class HMAFilterConfig(BaseModel):
    enabled: bool = True
    timeframe: str = "1d"   # "1d" 또는 "1h"
    period: int = 50        # HMA 기간


class VolumeFilterConfig(BaseModel):
    enabled: bool = True
    lookback: int = 20          # 평균 거래량 산출 구간
    multiplier: float = 1.5     # 현재 거래량 ≥ 평균 × multiplier


class StopLossConfig(BaseModel):
    lookback_candles: int = 10  # 손절가 = 최근 N캔들 저점


class DivergenceConfig(BaseModel):
    enabled: bool = True
    swing_window: int = 5       # 스윙 고점 판별 윈도우 (양쪽 각 N캔들)


class Position(BaseModel):
    """리스크 안전구역 — 진화가 변경할 수 없는 섹션."""
    max_single_weight: float = 0.20
    daily_loss_limit: float = 0.03


class StrategyConfig(BaseModel):
    """활성 전략 전체 스냅샷."""
    version: str = "2.0.0"
    updated_at: str = ""
    updated_by: str = "seed"

    macd: MACDConfig = Field(default_factory=MACDConfig)
    rsi: RSIConfig = Field(default_factory=RSIConfig)
    hma_filter: HMAFilterConfig = Field(default_factory=HMAFilterConfig)
    volume_filter: VolumeFilterConfig = Field(default_factory=VolumeFilterConfig)
    stop_loss: StopLossConfig = Field(default_factory=StopLossConfig)
    divergence: DivergenceConfig = Field(default_factory=DivergenceConfig)
    position: Position = Field(default_factory=Position)

    def get_param(self, path: str):
        """점 경로로 파라미터 조회 (예: 'rsi.buy_low')."""
        section, _, key = path.partition(".")
        obj = getattr(self, section, None)
        if obj is None or not key:
            return None
        return getattr(obj, key, None)


class ProposedChange(BaseModel):
    """진화 제안의 단일 파라미터 변경."""
    param: str
    current: float | int | None = None
    proposed: float | int
    reason: str = ""


class EvolutionProposal(BaseModel):
    """Evolution Agent(LLM) 출력."""
    analysis: str = ""
    changes: list[ProposedChange] = Field(default_factory=list)
    expected_improvement: str = ""
    confidence: float = 0.0
