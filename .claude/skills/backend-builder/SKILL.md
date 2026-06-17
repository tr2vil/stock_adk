---
name: backend-builder
description: ADK 에이전트·오케스트레이터·decision·shared 모듈 빌더. Google ADK 에이전트(agent/tools/prompt/server 패턴)와 FastAPI 오케스트레이터, decision_engine, shared 모듈을 표준 구조로 구축한다.
user_invocable: true
---

# /backend-builder - 백엔드 빌더 (ADK + 오케스트레이터)

## 역할
`sub_agents/`, `orchestrator/`, `shared/`의 Python 백엔드를 생성/수정한다. 새 sub-agent 추가,
도구/프롬프트 변경, 오케스트레이터 API 엔드포인트, decision_engine 로직을 담당한다.

## ADK Sub-Agent 표준 구조
각 에이전트는 `sub_agents/<name>/`에 4파일:
- `__init__.py` — `from . import agent`
- `agent.py` — `root_agent` 정의
- `tools.py` — 도구 함수
- `prompt.py` — `AGENT_INSTRUCTION` 상수
- `server.py` — A2A 서버 (`to_a2a(root_agent, port=...)`)

### agent.py 규칙
```python
# 상단: GOOGLE_KEY(JSON) → GOOGLE_APPLICATION_CREDENTIALS 자동 설정 보일러플레이트 유지
from google.adk.agents import Agent
from .prompt import AGENT_INSTRUCTION
from .tools import tool_a
from shared.redis_client import seed_defaults, get_prompt_safe
from shared.model_factory import resolve_model      # ← Gemini/Claude 전환 필수

MODEL = os.getenv("<AGENT>_MODEL", "gemini-2.5-flash")
seed_defaults({"prompt:<agent>": AGENT_INSTRUCTION})
_instruction = get_prompt_safe("<agent>", AGENT_INSTRUCTION)

root_agent = Agent(
    name="<agent>", model=resolve_model(MODEL),   # ← 반드시 resolve_model 경유
    description="...", instruction=_instruction, tools=[tool_a],
)
```

### tools.py 규칙
- `async def`, **type hint 필수**(LLM 스키마), **docstring 필수**(호출 판단), 반환 `dict`
- 반환 크기 **15KB 이내** (초과 시 LLM 응답 실패). 오케스트레이터 툴은 3000자 절단 적용
- JSON 안전: `NaN`/`Inf` → `None`

### server.py 규칙
```python
import warnings; warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from .agent import root_agent
app = to_a2a(root_agent, port=int(os.getenv("<AGENT>_PORT", "<port>")))
```

## 오케스트레이터 (orchestrator/)
- `agent.py` — `analyze_all_agents` 툴로 5개 에이전트 **병렬**(`asyncio.gather`) 호출
- `server.py` — FastAPI. 토스 등 **blocking 호출 엔드포인트는 `def`(sync)** 로 선언 → FastAPI가 스레드풀 실행(이벤트 루프 비차단). LLM 실행은 `_runner`(InMemoryRunner) + `run_async`
- `to_a2a` 서브앱은 신버전 ADK에서 `router.on_startup` 대신 lifespan 사용 → `AsyncExitStack`로 lifespan_context 진입 (server.py lifespan 참조)
- decision_engine — 가중합산 점수화. 가중치/임계값은 Redis

## 프롬프트는 Redis가 런타임 소스
`seed_defaults`는 **키가 없을 때만** 시딩(SET NX). 그래서 `prompt.py`만 고치면 기존 Redis 값 때문에 반영 안 됨. 변경 반영은 `/api/prompts` PUT(즉시) 또는 Redis 키 재시딩.

## 새 sub-agent 추가 절차
1. 유사 에이전트(예: news_agent) 복사 → 4파일 작성
2. `shared/config.py`에 `<AGENT>_MODEL/_HOST/_PORT` 추가
3. `docker-compose.yml`에 서비스 + 포트 추가
4. 오케스트레이터 `tools.py`의 `AGENT_CONFIG`에 엔트리 추가
5. 가중치(`weights`) 반영
6. `/runner`로 리빌드·검증, dev가 CLAUDE.md 표 갱신

## 절대 규칙
- `model=`은 항상 `resolve_model(MODEL)` (직접 문자열 금지)
- 도구는 type hint + docstring + dict 반환 + 15KB 이내
- 하드코딩 URL/포트/키 금지 → `settings`/환경변수
- 비밀키 노출 금지, 한글 로그 `ensure_ascii=False`
- 변경 후 반드시 `/runner` 검증 (baked 이미지)
