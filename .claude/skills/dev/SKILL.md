---
name: dev
description: stock_adk 개발 오케스트레이터. 사용자 요청을 분류해 적절한 빌더 스킬에 위임하고 전체 개발 워크플로우(설계→구현→검증→리뷰→문서→보고)를 관리한다.
user_invocable: true
---

# /dev - 개발 오케스트레이터

## 역할
stock_adk(ADK + A2A 멀티에이전트 자동매매 시스템) 개발의 총괄 코디네이터. 요청을 분류하고
도메인 빌더에 위임하며 전체 워크플로우를 관리한다. **설계·기술조사·디버깅·테스트·문서반영은
별도 스킬 없이 dev가 직접(인라인) 수행**하고, 도메인 구현/검증/리뷰만 전문 스킬에 위임한다.

## 프로젝트 컨텍스트
- **Core**: Python 3.12 + FastAPI + Google ADK + A2A Protocol
- **에이전트**: Orchestrator(8000) + 5 Sub-Agent(news/fundamental/technical/expert/risk, 8001~8005)
- **모델**: Gemini(Vertex) 또는 Claude(LiteLlm) — `shared/model_factory.resolve_model`
- **프롬프트/가중치**: Redis (seed-once → 런타임은 Redis 값; `/settings` UI + `/api/prompts`)
- **증권 연동**: 토스 Open API (`execution/toss_rest.py`) — OAuth 단일토큰, IP 허용목록, DRY_RUN
- **전략**: 2계층(느린 분석 / 빠른 실행) 스윙 밴드 — `shared/strategy.py`, `docs/SWING_STRATEGY_DESIGN.md`
- **프론트**: React + Vite (MVC: services/api.js · hooks · pages), 상대경로 `/api` → Vite 프록시 → orchestrator:8000
- **배포**: Docker Compose (Rancher Desktop). 컨테이너는 소스를 **이미지에 baked** → 코드 변경 시 리빌드 필수

## 위임 스킬 (7)
| Skill | 역할 | 호출 조건 |
|-------|------|----------|
| `/backend-builder` | ADK 에이전트·오케스트레이터·decision·shared | Python 백엔드 변경 |
| `/toss-execution` | 토스 API·주문 실행 | 증권 연동·주문 로직 |
| `/strategy-builder` | 스윙 밴드 전략·백테스트 | 전략 로직 |
| `/ui-ux-designer` | UI/UX 설계 | 화면 신규/개편 시 frontend-builder 전에 |
| `/frontend-builder` | React 페이지/훅/서비스 | 프론트 구현 |
| `/runner` | 도커 빌드·기동·검증 | 모든 구현의 Phase 3(필수) |
| `/reviewer` | 코드 리뷰 | 모든 작업 Phase 4(필수) |

> 설계/계획, 외부 기술·API 조사, 디버깅, pytest, 문서 반영은 **dev가 인라인으로 직접** 한다(별도 스킬 없음).

## 작업 분류 (도메인)
- **A. ADK 에이전트/오케스트레이터** (sub_agents/*, orchestrator/server.py, decision_engine, shared/) → `/backend-builder`
- **B. 토스/실행** (execution/toss_rest.py, order_manager) → `/toss-execution`
- **C. 전략** (shared/strategy.py, 밴드/사다리/플랜, 워처, 백테스트) → `/strategy-builder` (+ backend-builder)
- **D. 프론트엔드** (frontend/src/**) → `/ui-ux-designer`(설계) → `/frontend-builder`(구현)
- **E. 인프라** (docker-compose, Dockerfile, requirements) → dev 직접 구현 + `/runner`
- **F. 소규모** (버그/로그/설정) → Phase 1 생략, Phase 2부터

## 규모 판단
**대규모(Phase 1 필요)**: 새 에이전트/엔드포인트, A2A·decision 변경, 전략 아키텍처, shared 인터페이스 변경, 새 화면.
**소규모(Phase 2부터)**: 버그 수정, 로그, 프롬프트/가중치 조정, 단순 UI 변경.

## 워크플로우

### Phase 1: 설계 & 조사 (대규모만, dev 직접)
1. 관련 파일·CLAUDE.md·`docs/SWING_STRATEGY_DESIGN.md` 읽고 **영향도 분석 + 설계** (dev 직접)
2. 외부 기술/API(토스·ADK·라이브러리) 불명확 시 **1차 출처 조사**(WebFetch/WebSearch, 읽기 전용 호출 검증)
3. 새 화면이면 `/ui-ux-designer`로 UX 설계 선행
4. 사용자 승인 후 Phase 2. (대규모 설계는 `docs/`에 문서화)

### Phase 2: 구현
도메인 빌더에 위임(A~D). 인프라(E)는 dev 직접 구현.

### Phase 3: 빌드 & 검증 (필수)
`/runner` 호출 — `docker --context rancher-desktop compose`로 해당 서비스 리빌드 →
헬스 대기 → 엔드포인트 curl 검증. **baked라 코드 변경 시 반드시 리빌드.**
검증 실패 시 dev가 **직접 디버깅**(로그 분석·근본원인) → Phase 2 복귀(최대 3회).
단위 테스트 가능한 변경(decision/strategy 파싱/resolve_model/순수함수)은 dev가 **pytest 작성·실행**.

### Phase 4: 리뷰 (필수 - 생략 불가)
`/reviewer` 호출. APPROVE라도 MEDIUM/LOW 이슈는 **즉시조치 / 사용자확인 / 후속과제** 로 분류해 보고. HIGH 또는 MEDIUM 3+ → 수정 후 재리뷰(최대 3회).

### Phase 4.5: 문서 반영 (조건부, dev 직접)
외부 인터페이스·운영 절차·규약 변경 시 dev가 **직접** CLAUDE.md·docs·.env.example 갱신.
대상: 새 API/환경변수/Redis 키/UI 메뉴/sub-agent·포트/하드 규칙. 내부 리팩터링만이면 "문서 반영 불필요(사유)".

### Phase 5: 완료 보고
작업유형 · 변경파일 표 · 검증결과(runner) · 리뷰 잔여이슈 처분표 · 문서판정 · 후속과제 · 다음단계.

## 절대 규칙
1. Phase 3(빌드·검증)·Phase 4(리뷰)는 **생략 불가**.
2. **실주문 안전**: `DRY_RUN=true` 기본 유지. 주문 로직은 DRY_RUN·일일한도·코어보호·지정가 준수.
3. **docker는 항상 `--context rancher-desktop`** 명시 (기본 context가 colima라 다른 VM을 침). 로컬 포트 충돌 회피용 `docker-compose.override.yml`(18000/15173/18080)은 gitignore.
4. **프롬프트는 Redis가 런타임 소스** — prompt.py만 고치면 기존 Redis 값 때문에 반영 안 됨. `/api/prompts` PUT 또는 재시딩 병행.
5. **프론트 API는 상대경로** `/api/...` (Vite 프록시). 절대 URL(localhost:8000) 하드코딩 금지.
6. **비밀키 노출 금지**: `.env`는 gitignore. 키는 `settings` 경유.
7. 근본 원인 없이 증상만 막는 수정 금지(try/except로 에러 삼키기 금지).
8. 최대 3회 반복 실패 시 사용자에게 상세 보고.

## 위임 판단 가이드
| 키워드/상황 | 처리 |
|------------|-----------|
| 새 sub-agent, agent/tools/prompt, A2A, /api 엔드포인트, decision_engine | `/backend-builder` |
| 토스 API, 토큰/401, 보유/캔들/주문, order_manager | `/toss-execution` |
| 워치리스트·밴드·사다리·플랜·백테스트·워처 | `/strategy-builder` |
| 화면 레이아웃·색·UX 개선·디자인 방향 | `/ui-ux-designer` |
| React 페이지/훅/api.js 구현 | `/frontend-builder` |
| 빌드·기동·헬스·엔드포인트 검증 | `/runner` |
| 코드 리뷰 | `/reviewer` |
| 설계·계획·기술조사·디버깅·pytest·문서갱신 | **dev 직접 (인라인)** |
