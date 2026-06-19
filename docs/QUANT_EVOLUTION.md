# 자가진화 퀀트 로직 — 구현 노트

> 설계서 v1.1 "자가진화 퀀트 로직 + Telegram 연동"의 **핵심 레이어** 구현.
> 브랜치: `quant-evolution-20260619`

## 1. 구현 범위 (이번 작업)

설계서의 **차별적 핵심**인 "자가진화 퀀트 로직"을 우선 구현했다. 전체 에이전트
토폴로지(Data/Sentiment/Signal/... 7개) 재작성은 위험·고비용이라 **기존
`sub_agents/`·`orchestrator/` 컨벤션 위에 진화 레이어를 신규 추가**하는 방향으로
결정했다(아래 §4 결정사항 참조).

### 결정론적 코어 — `shared/quant/` (LLM 미사용, 단위테스트 29개 통과)
| 모듈 | 역할 |
|------|------|
| `schema.py` | `StrategyConfig`(전략) / `EvolutionProposal`(제안) 스키마 |
| `indicators.py` | RSI(Wilder)·SMA·ATR 순수 함수 |
| `signal.py` | `strategy.yaml` 기반 Rule 신호 생성 (뉴스방어→손절→모멘텀매도→모멘텀매수) |
| `guardrails.py` | 진화 제안 **검증·적용·버전증가** — 허용목록 밖/범위초과/`position` 보호 자동거부 |
| `performance.py` | 승률·평균수익·샤프·MDD·신호정확도·RSI/감성 구간별 수익률 |
| `strategy_store.py` | 활성전략 + 버전이력 + 롤백 + 대기제안 (Redis, 시드=`config/strategy.yaml`) |
| `trade_log.py` | 신호/매매 결과 기록·조회 (Redis) |

### LLM·실행 레이어
- `sub_agents/evolution_agent/` — 성과통계 + 현재전략 → 개선안 JSON 제안 (port 8006, A2A)
- `orchestrator/evolution_runner.py` — **진화 파이프라인**:
  `매매수집 → 성과통계 → LLM제안 → 가드레일검증 → 대기제안 저장 → Telegram 승인요청`
  - 청산 매매 < 10건이면 LLM 미호출(과적합 방지, 설계서 11.1)
  - 가드레일 위반 제안은 자동 거부
- `shared/notifications.py` — Telegram 발송 (토큰 없으면 **graceful no-op**) + 승인 인라인버튼

### 연동
- **REST 엔드포인트** (orchestrator):
  - `GET  /api/quant/strategy` — 현재 활성 전략
  - `GET  /api/quant/strategy/history?limit=5` — 버전 이력
  - `POST /api/quant/strategy/rollback/{version}` — 롤백
  - `POST /api/quant/evolution/run?lookback_days=30` — 진화 분석 수동 실행
  - `POST /api/quant/evolution/approve/{pid}` — 제안 승인 → 전략 적용
  - `POST /api/quant/evolution/reject/{pid}` — 제안 거부
- **스케줄러**: 평일 16:00 KST 자동 진화 트리거 (HiL 승인 대기로 진입)
- **Docker**: orchestrator 이미지에 `sub_agents/`·`config/` 복사(in-process 진화),
  `evolution-agent`(8006) compose 서비스 추가

## 2. 진화 흐름

```
매매 실행 → trade_log(Redis) 기록
                    │  (평일 16:00 또는 수동)
                    ▼
   evolution_runner.run_evolution_analysis()
     1) 최근 N일 매매 수집 (trade_log)
     2) 성과 통계 산출 (performance, 결정론)
     3) [데이터 부족 시 중단]
     4) Evolution Agent(LLM) 개선안 제안
     5) 가드레일 검증 (guardrails, 결정론) ── 위반 시 자동 거부
     6) 대기 제안 저장 + Telegram 승인 버튼 발송
                    │
        ┌───── 승인(approve) ─────┐         거부(reject)
        ▼                                          ▼
  strategy_store.acommit_new_version       대기 제안 폐기
  (활성 전략 교체 + 버전 +1 + 이력 보존)     (현재 전략 유지)
        │
        ▼  다음 신호 사이클부터 새 파라미터 자동 적용
```

## 3. 안전장치 (가드레일)
- **허용목록 방식**: `EVOLUTION_GUARDRAILS`에 명시된 파라미터만 변경 가능.
  `position.max_single_weight`·`position.daily_loss_limit` 등 미명시 파라미터는 무조건 거부.
- **범위 검증**: 각 제안값이 `[low, high]` 이내. 예) `stop_loss.rate` 0.03~0.15 → 손절 완화 금지.
- **타입**: `ma_period` 정수 강제.
- **교차검증**: 적용 후 `rsi_buy_threshold < rsi_sell_threshold` 유지.
- **HiL 필수**: 전략 변경은 승인 없이는 절대 적용되지 않음(자동 적용 금지).
- **버전 이력**: 모든 변경/롤백을 Redis 이력에 보존 → 언제든 롤백.

## 4. 자율 결정 사항 (검토 요청)
1. **에이전트 토폴로지**: 설계서의 7-에이전트 재작성 대신, 기존 5-에이전트 분석
   시스템을 유지하고 진화 레이어만 추가. → 전면 전환 여부 결정 필요.
2. **저장소**: 설계서는 PostgreSQL(signals/orders/strategy_versions 테이블)이지만,
   기존 코드가 Redis 중심이라 **Redis로 구현**. PostgreSQL 마이그레이션은 인터페이스
   유지한 채 후속 가능. → DB 채택 시점 결정 필요.
3. **Telegram 버튼 콜백**: 발송 + REST 승인 엔드포인트는 구현. **버튼 클릭 콜백 처리
   봇(long-polling/webhook 컨슈머)은 미구현** → 토큰 발급 후 추가 필요.
4. **모델**: 설계서 `gemini-2.0-flash` 대신 프로젝트 표준 `gemini-2.5-flash`.
5. **신호 파이프라인 가동**: 현재 진화 루프는 `trade_log`에 매매 기록이 쌓여야
   작동. 기존 워처/주문 경로가 `trade_log.arecord_trade()`를 호출하도록 연결하는
   작업이 남음(설계서 Data/Signal/Execution 정식 파이프라인 미연결).

## 5. 테스트 상태
- ✅ 결정론 코어 단위테스트 29개 통과 (`tests/test_quant_*.py`)
- ✅ 전 파일 `py_compile` 통과
- ✅ 엔드포인트 스모크: `GET /api/quant/strategy`(시드 로드), `evolution/run`(데이터부족 응답), 롤백
- ⏳ 미검증(외부 의존): LLM 실제 제안 품질(GCP 필요), Telegram 실발송(토큰 필요),
  정식 매매 파이프라인 E2E
