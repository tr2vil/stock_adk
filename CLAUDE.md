# CLAUDE.md - Trading System 개발 컨텍스트

## 프로젝트 개요

Google ADK + A2A Protocol 기반 멀티에이전트 자동매매 시스템.
Orchestrator가 5개의 전문 Sub-Agent를 조율하여 종합 분석 및 투자 결정을 수행.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator (8000)                       │
│           RemoteA2aAgent를 통해 Sub-Agent들과 A2A 통신           │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  News    │ │Fundament-│ │Technical │ │  Expert  │ │   Risk   │
│  Agent   │ │al Agent  │ │  Agent   │ │  Agent   │ │  Agent   │
│  (8001)  │ │  (8002)  │ │  (8003)  │ │  (8004)  │ │  (8005)  │
│  20% 가중│ │  25% 가중│ │  30% 가중│ │  15% 가중│ │  10% 가중│
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## 프로젝트 구조

```
trading-system/
├── orchestrator/              # 오케스트레이터 (Port 8000)
│   ├── __init__.py
│   ├── agent.py               # Root Agent with RemoteA2aAgent
│   ├── decision_engine.py     # 가중 합산 로직
│   ├── scheduler.py           # APScheduler
│   ├── server.py              # FastAPI + ADK API
│   ├── prompt.py              # ORCHESTRATOR_INSTRUCTION
│   └── Dockerfile
├── sub_agents/                # Sub-Agent 모음
│   ├── news_agent/            # Port 8001
│   ├── fundamental_agent/     # Port 8002
│   ├── technical_agent/       # Port 8003
│   ├── expert_agent/          # Port 8004
│   ├── risk_agent/            # Port 8005
│   └── Dockerfile             # 공유 Dockerfile
├── execution/                 # 주문 실행 모듈
│   ├── __init__.py
│   ├── kiwoom_rest.py         # 키움 REST API
│   ├── order_manager.py       # 주문 관리자
│   └── websocket_client.py    # 실시간 시세
├── shared/                    # 공유 모듈
│   ├── __init__.py
│   ├── models.py              # Pydantic 모델
│   ├── config.py              # pydantic-settings
│   ├── database.py            # SQLAlchemy
│   └── logger.py              # structlog
├── monitoring/                # 모니터링
│   ├── __init__.py
│   ├── dashboard.py           # Streamlit
│   └── alerting.py            # Telegram/Slack
├── tests/                     # 테스트
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Sub-Agent 개발 패턴

모든 Sub-Agent는 아래 구조를 따릅니다:

```
sub_agents/<agent_name>/
├── __init__.py       # from . import agent
├── agent.py          # root_agent 정의 (Google ADK Agent)
├── tools.py          # 도구 함수 (async, type hint + docstring 필수)
├── prompt.py         # AGENT_INSTRUCTION 상수
└── server.py         # A2A 프로토콜 서버
```

### agent.py 패턴

```python
import os
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()

# GOOGLE_KEY JSON → GOOGLE_APPLICATION_CREDENTIALS 자동 설정
_google_key = os.getenv("GOOGLE_KEY")
if _google_key and _google_key.strip().startswith("{"):
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        _cred_dir = os.path.join(tempfile.gettempdir(), "trading_system")
        os.makedirs(_cred_dir, exist_ok=True)
        _cred_path = os.path.join(_cred_dir, "service_account.json")
        with open(_cred_path, "w", encoding="utf-8") as f:
            json.dump(json.loads(_google_key), f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _cred_path

from google.adk.agents import Agent
from .prompt import AGENT_INSTRUCTION
from .tools import tool_a, tool_b

MODEL = os.getenv("<AGENT_NAME>_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="<agent_name>",
    model=MODEL,
    description="에이전트 설명",
    instruction=AGENT_INSTRUCTION,
    tools=[tool_a, tool_b],
)
```

### tools.py 규칙

- 함수는 `async def` 권장 (ADK 1.10+ 비동기 도구 지원)
- **type hint 필수**: LLM이 파라미터 스키마로 사용
- **docstring 필수**: LLM이 도구 호출 판단에 사용
- 반환 타입은 `dict`
- 반환 데이터 크기 주의: **15KB 이내** 권장 (초과 시 LLM 응답 실패 가능)
- JSON 직렬화 안전: `NaN`, `Inf` → `None` 변환 필요

```python
async def my_tool(param: str) -> dict:
    """도구 설명 (LLM이 읽음).

    Args:
        param: 파라미터 설명

    Returns:
        dict: 결과 설명
    """
    return {"status": "success", "data": ...}
```

### server.py 패턴

```python
import os
from dotenv import load_dotenv
load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from .agent import root_agent

A2A_PORT = int(os.getenv("<AGENT_NAME>_PORT", "<port>"))
app = to_a2a(root_agent, port=A2A_PORT)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=A2A_PORT)
```

## Sub-Agent 목록

| Agent | 디렉토리 | 포트 | 가중치 | 역할 |
|-------|----------|------|--------|------|
| news_agent | `sub_agents/news_agent/` | 8001 | 20% | 뉴스/센티먼트 분석 |
| fundamental_agent | `sub_agents/fundamental_agent/` | 8002 | 25% | 재무제표 분석 |
| technical_agent | `sub_agents/technical_agent/` | 8003 | 30% | 기술적 분석 |
| expert_agent | `sub_agents/expert_agent/` | 8004 | 15% | 전문가 신호 |
| risk_agent | `sub_agents/risk_agent/` | 8005 | 10% | 리스크 관리 |

## 포트 할당

| 포트 | 서비스 |
|------|--------|
| 80 | Nginx |
| 3001 | Grafana |
| 5173 | Frontend |
| 5432 | PostgreSQL |
| 6379 | Redis |
| 8000 | Orchestrator |
| 8001 | News Agent |
| 8002 | Fundamental Agent |
| 8003 | Technical Agent |
| 8004 | Expert Agent |
| 8005 | Risk Agent |

## 의사결정 로직

1. Orchestrator가 5개 Sub-Agent에게 분석 요청
2. 각 Agent 결과를 -1.0 ~ +1.0 점수로 변환
3. 가중 합산: `final_score = Σ(agent_score × weight)`
4. 결정:
   - `final_score > +0.3`: **BUY**
   - `final_score < -0.3`: **SELL**
   - 그 외: **HOLD**
5. Risk Agent가 "high" 리스크 → 수량 50% 감소

## 안전 규칙

- 단일 종목 최대 투자비율: **20%**
- 1회 거래 최대 리스크: **2%**
- 최소 손익비: **1.5:1**
- 일일 최대 거래: **10회**
- 동시 보유 최대: **10종목**

## 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GOOGLE_GENAI_USE_VERTEXAI` | Vertex AI 사용 여부 | TRUE |
| `GOOGLE_CLOUD_PROJECT` | GCP 프로젝트 ID | - |
| `GOOGLE_CLOUD_LOCATION` | GCP 리전 | us-central1 |
| `GOOGLE_KEY` | 서비스 계정 JSON 문자열 | - |
| `NEWS_AGENT_MODEL` | 뉴스 에이전트 모델 | gemini-2.5-flash |
| `ORCHESTRATOR_MODEL` | 오케스트레이터 모델 | gemini-2.5-pro |
| `DRY_RUN` | 실제 주문 실행 여부 | true |

## 로컬 실행

### 개별 Agent 실행

```bash
# 각 에이전트를 별도 터미널에서 실행
python -m sub_agents.news_agent.server         # :8001
python -m sub_agents.fundamental_agent.server  # :8002
python -m sub_agents.technical_agent.server    # :8003
python -m sub_agents.expert_agent.server       # :8004
python -m sub_agents.risk_agent.server         # :8005
python -m orchestrator.server                  # :8000
```

### Agent Card 확인

```bash
curl http://localhost:8001/.well-known/agent.json
```

### A2A 질의 (JSON-RPC 2.0)

```bash
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-001",
        "role": "user",
        "parts": [{"kind": "text", "text": "Analyze AAPL news"}]
      }
    }
  }'
```

## Docker 실행

```bash
# 전체 시스템 빌드 및 실행
docker-compose up --build

# Nginx 경유 테스트
curl http://localhost/agents
curl http://localhost/api/health
```

## 주요 의존성

- `google-adk[a2a]` >= 1.23
- `yfinance` (재무제표, API 키 불필요)
- `httpx`, `beautifulsoup4` (뉴스 스크래핑)
- `fastapi`, `uvicorn` (웹 서버)
- `pydantic-settings` (설정 관리)
- `apscheduler` (스케줄링)
