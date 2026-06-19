"""
밴드 앵커 추출 에이전트 (Phase 2 — 근거 강화).

5-에이전트 종합 리포트(마크다운)를 입력받아, 스윙 밴드의 두 앵커를
**산출 근거와 함께** 구조화 JSON으로 추출하는 경량 단발 LLM.

- 기대값(target_price): 매도 앵커 = 전문가 목표가·펀더멘털 적정가 상단 등
  근거로 한 보수적 상단.
- 적정매수가(buy_anchor): 매수 앵커 = 기술적 지지선·펀더멘털 적정가 하단.
  **손절가가 아니다** (손절은 "깨지면 이탈", 적정매수가는 "여기서 사면 좋음").

도구 없이 텍스트→JSON만 수행하므로 빠르고 저렴하다(오케스트레이터 재호출 X).
"""
import os

from google.adk.agents import Agent
from shared.model_factory import resolve_model

EXTRACT_INSTRUCTION = """\
당신은 스윙 밴드 매매의 가격 앵커를 산출하는 애널리스트입니다.
아래에 한 종목의 5-에이전트 종합 분석 리포트와 현재가가 주어집니다.

리포트의 **전문가 목표가, 펀더멘털 적정가 범위, 기술적 지지/저항, 손절가**
등을 근거로 다음 두 앵커를 산출하세요.

1. 기대값(target_price) — **매도 앵커**: 차익 실현 기준 상단.
   전문가 평균 목표가나 펀더멘털 적정가 상단을 우선 근거로 하되,
   과도하면 보수적으로 할인하세요.
2. 적정매수가(buy_anchor) — **매수 앵커**: 추가 매수하기 좋은 하단.
   기술적 지지선이나 펀더멘털 적정가 하단을 근거로 하세요.
   **손절가를 그대로 쓰지 마세요.** 손절가는 이탈 기준이지 매수 기준이 아닙니다.

제약:
- target_price > 현재가 > buy_anchor 가 자연스럽지만, 분석상 현재가가
  고평가면 buy_anchor가 더 낮게, 저평가면 target이 더 높게 둘 수 있습니다.
- 두 값 모두 양수. 근거(basis)는 어떤 수치에서 왔는지 한국어 1~2문장으로
  구체적으로(예: "전문가 평균 목표가 $244와 펀더멘털 적정가 상단 $250 기준 보수적 5% 할인").

**오직 아래 JSON만** 출력하세요. 코드펜스·설명 금지.
{
  "target_price": <number>,
  "buy_anchor": <number>,
  "target_basis": "<한국어 근거>",
  "buy_basis": "<한국어 근거>",
  "conviction": <0~1 사이 number>
}
"""

EXTRACT_MODEL = os.getenv("STRATEGY_EXTRACT_MODEL", "gemini-2.5-flash")

extract_agent = Agent(
    name="band_anchor_extractor",
    model=resolve_model(EXTRACT_MODEL),
    description="종합 분석 리포트에서 스윙 밴드 앵커(기대값/적정매수가)를 근거와 함께 추출",
    instruction=EXTRACT_INSTRUCTION,
)
