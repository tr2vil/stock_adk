"""자가진화 퀀트 로직 패키지.

결정론적 코어(LLM 미사용):
- schema       : 전략/제안 Pydantic 스키마
- indicators   : RSI/SMA/ATR 등 기술지표 (순수 함수)
- signal       : strategy.yaml 기반 Rule 신호 생성 (순수 함수)
- guardrails   : 진화 제안 검증·적용·버전 관리 (순수 함수)
- performance  : 매매 결과 성과 통계 (순수 함수)
- trade_log    : 신호/주문/결과 기록·조회 (Redis)
- strategy_store: 활성 전략 + 버전 이력 (Redis)

LLM 레이어는 sub_agents/evolution_agent 가 담당한다.
"""
