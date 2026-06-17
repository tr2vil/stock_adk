# 스윙 밴드 매매 + 포트폴리오 화면 설계

## 배경 / 문제의식
가격은 실시간으로 변하는데 5-에이전트 LLM 분석은 ~100초 걸린다. 분석 결과로 시장가 주문을
내면 이미 가격이 변해 있다. → **분석(느림)과 실행(빠름)을 시간축으로 분리**한다.

목표 사용자 전략: **장기 코어 누적 + 위성 트랜치로 밴드 매매** (스윙, 일~주 호흡).
"웬만하면 안 팔되, 기대값 도달 시 일부 실현하고 내려오면 되산다."
대상: 사용자가 지정한 1~2 종목. → 실시간(틱/웹소켓) 불필요, **분 단위 폴링이면 충분**.

## 2계층 아키텍처
```
[1] 분석 계층 (느림, 장전 스케줄 + 수동)   ← 5-에이전트 LLM
      → 기대값(목표가 상단)·적정매수가(하단)·확신도·근거 "제안"
              │  사용자 승인 → Redis 캐시
              ▼
[2] 전략/밴드 계층 (결정론적)              ← decision_engine 확장
      종목별: core_qty, swing_qty, 매도 사다리[], 매수 사다리[], 사다리 상태
              │
              ▼
[3] 워처/실행 계층 (장중 분 단위 폴링)      ← execution/watcher (신규) + order_manager
      토스 /api/v1/prices 폴링 → 사다리 단 교차 & 미체결 → 지정가 주문 → 상태 갱신
      매도 체결 후 하락 시 대응 매수 단 재무장(ARMED) → "고점 실현·저점 되사기" 반복
      코어 수량(core_qty) 밑으로는 절대 매도 안 함
```
LLM은 **기대값 설정에만** 관여. 실제 진입/청산 타이밍은 [3]의 싼 규칙이 담당.

## 전략 사양 (확정)
- **기대값 설정**: 하이브리드 — LLM이 제안(애널리스트 목표가·펀더멘털) → 사용자가 UI에서 승인/수정.
- **밴드**: 사다리(다단계 분할), **종목별/일괄 설정 가능**.
  - 기본 매도 사다리: 기대값 기준 `[+0%, +5%, +10%]` 각 트랜치의 `1/3`
  - 기본 매수 사다리: 적정매수가 기준 `[0%, -5%, -10%]` 각 트랜치의 `1/3`
- **코어 vs 스윙**: 기본 스윙 트랜치 = 보유의 **20%** (80% 코어 고정), 설정 가능.
- **분석 주기**: 장 시작 전 1회 자동 + 수동 버튼.

## 데이터 모델 (Redis)
```
watchlist                      : ["005930", ...]            # 사용자 지정
strategy:config:_default       : 전역 기본 밴드/트랜치 설정
strategy:config:{ticker}       : 종목별 오버라이드(부분)
strategy:plan:proposed:{ticker}: {target, buy_anchor, conviction, rationale, generated_at}  # 승인 대기
strategy:plan:active:{ticker}  : 승인된 plan + ladder 상태([{level, price, frac, state}])
                                 state ∈ ARMED | PENDING(주문중) | FILLED
position:{ticker}              : {core_qty, swing_qty, ...} # 토스 holdings에서 동기화
```

## 모듈 & 단계
| Phase | 내용 | 산출물 |
|------|------|--------|
| **A. 포트폴리오 화면** | 토스 보유종목 조회 + 현재가/캔들차트 + 캐시 리포트 | `/portfolio` 페이지, `GET /api/holdings`, `GET /api/candles/{symbol}` |
| **1. 전략 토대** | 데이터 모델 + 워치리스트/밴드설정 API + Settings UI 탭 + 분석→제안→승인 | Redis 스키마, API, UI |
| **2. 실행** | 가격 워처(폴링) + 사다리 상태머신 + DRY_RUN 지정가 주문 | `execution/watcher.py`, decision_engine 확장 |
| **3. 자동화** | 장전 스케줄러 잡 + 백테스트 하니스 | `scheduler.py` 잡, 백테스트 |

## 포트폴리오 화면 (Phase A) 사양
- 데이터: 토스 `/api/v1/holdings`(보유), `/api/v1/candles`(차트, `interval=1d&count=N`), `/api/v1/prices`(현재가).
  - 모든 토스 호출은 **백엔드(orchestrator)** 경유 (API 키 서버측·IP 허용목록·`X-Tossinvest-Account` 때문).
- UI(`/portfolio`, 현재 "준비중" 자리):
  - 보유종목 리스트 (종목명/수량/평단/현재가/수익률, 총평가·총손익)
  - 종목 선택 → 현재가 + 캔들차트(일봉) + 캐시된 분석 리포트(있으면) + "재분석" 버튼
  - 차트 라이브러리: `lightweight-charts`(TradingView, 캔들 특화, 경량) 추가 예정

## 안전 / 검증
- `DRY_RUN=true` 페이퍼 트레이딩으로 먼저 → 과거 시세 **백테스트**로 사다리 파라미터 튜닝 → 실거래.
- 코어 보호(보유 ≥ core_qty), **지정가만**, 일일 거래 제한, 히스테리시스/쿨다운으로 밴드 thrash 방지.
- 토스 IP 허용목록: 운영 시 시스템이 도는 호스트의 공인 IP 등록 필요.

## Phase 2 확정 파라미터 (구현 대기)
- **폴링**: 장중 **5분** 간격 (KR 09:00~15:30 KST). 워처는 **LLM 미사용** — 토스 `get_prices` REST + 사다리 평가는 결정론적.
- **워처 시작**: **수동 토글**(전략 페이지 버튼 + start/stop API). 자동 시작 안 함(실주문 안전).
- **거래**: `DRY_RUN=true` 페이퍼만. order_manager(지정가·일일한도·코어보호·멱등키) 경유.
- **포지션 산정**: 매 틱 토스 보유 동기화 → `core_qty = floor(total × (1 - swing_fraction))`, 봇은 `swing_qty`만 거래(코어 밑 매도 금지).
- **사다리 상태머신**: ARMED→FILLED, 매도 체결 후 하락 시 대응 매수단 재무장(히스테리시스/쿨다운으로 thrash 방지). 상태는 Redis 활성 플랜에 저장.
- **통합 지점**: `orchestrator/scheduler.py`(APScheduler interval), `execution/order_manager.py`, `shared/strategy.py`.
- **구현 방식**: 재시작 후 `/dev`로 진행 — `/strategy-builder`(상태머신·워처) + `/toss-execution`(주문) + `/runner`(검증) + `/reviewer`.

## 이미 구현된 것 (재사용)
- **프롬프트 Redis + UI 편집**: `Settings.jsx` + `/api/prompts` (GET/PUT) — 6개 에이전트 프롬프트
  확인/수정 + 가중치/임계값 편집 **완성됨**. 추가 작업 불필요.
- **병렬 에이전트 호출**: `analyze_all_agents`가 `asyncio.gather`로 이미 동시 호출.
- **주문 실행**: `order_manager`(지정가, DRY_RUN, 일일한도), 토스 클라이언트(`execution/toss_rest.py`).
