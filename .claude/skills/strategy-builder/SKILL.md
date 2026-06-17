---
name: strategy-builder
description: 스윙 밴드 매매 전략 빌더. 2계층(느린 분석/빠른 실행) 아키텍처에서 밴드·사다리·플랜·decision 점수화·가격 워처·백테스트를 구축한다.
user_invocable: true
---

# /strategy-builder - 스윙 밴드 전략 빌더

## 역할
`shared/strategy.py`, `orchestrator/decision_engine.py`, 가격 워처, 백테스트를 다룬다.
설계 문서: `docs/SWING_STRATEGY_DESIGN.md` (항상 먼저 참조).

## 핵심 원칙: 분석(느림) ↔ 실행(빠름) 분리
LLM 5-에이전트 분석은 ~100초 → **매수/매도 타이밍 결정에 직접 쓰지 않는다.**
```
[1] 분석(장전 스케줄+수동): 5-에이전트 → 기대값·적정매수가 "제안"  (느림)
[2] 전략/밴드(결정론적): 사다리 밴드 + 상태머신                    (decision_engine)
[3] 워처(장중 분단위 폴링): 밴드 교차 → 지정가 주문                (빠름, LLM 없음)
```
1~2종목·긴 호흡 스윙이라 실시간(틱/웹소켓) 불필요 — 분 단위 폴링이면 충분.

## 전략 사양 (확정)
- **코어+위성**: 봇은 스윙 트랜치(기본 보유의 20%)만 굴리고 코어는 고정(절대 매도 안 함)
- **하이브리드 기대값**: LLM 제안 → 사용자 승인(`/api/strategy/analyze` → `/approve`)
- **사다리 밴드**(종목별/일괄 설정): 매도=기대값 기준 `[+0,+5,+10%]`×1/3, 매수=적정매수가 기준 `[0,-5,-10%]`×1/3

## 데이터 모델 (`shared/strategy.py`, Redis)
```
strategy:watchlist               # [{symbol, market, name}]
strategy:config:_default | {sym} # {swing_fraction, sell_ladder[], buy_ladder[]} (병합)
strategy:plan:proposed:{sym}     # LLM 제안(승인 대기)
strategy:plan:active:{sym}       # 승인된 플랜 (+ 사다리 상태: ARMED/PENDING/FILLED)
```
`build_proposed_plan`: 분석 마크다운에서 목표가→기대값, 손절가→적정매수가, Action→확신도 파싱(실패 시 현재가 ±% 기본값).

## 워처/실행 (Phase 2 구현 대상)
- 장중 N분 폴링(`get_prices`) → 활성 플랜 사다리 단 교차 & 미체결 → 지정가 주문(order_manager)
- 매도 단 체결 후 하락 시 대응 매수 단 재무장 → "고점 실현·저점 되사기" 반복
- **히스테리시스/쿨다운**으로 thrash 방지, 코어 수량 보호

## 절대 규칙
- LLM은 기대값 설정에만. 타이밍은 결정론적 규칙.
- **DRY_RUN 페이퍼 → 과거 시세 백테스트 → 실거래** 순. 백테스트 없이 실거래 금지.
- 사다리 합 fraction은 트랜치 내 비율. 코어 침범 금지.
- 주문은 `/toss-execution`의 order_manager 경유 (DRY_RUN·지정가·한도).
- 변경 후 `/runner`로 analyze→propose→approve 흐름 검증.
