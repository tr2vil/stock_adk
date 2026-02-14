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
├── frontend/                  # Frontend (React + Vite)
│   ├── src/
│   │   ├── main.jsx           # 진입점
│   │   ├── App.jsx            # 라우터 설정
│   │   ├── services/
│   │   │   └── api.js         # Model: API 통신 (axios)
│   │   ├── hooks/
│   │   │   └── useStockAnalysis.js  # Controller: 상태 관리
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx         # 대시보드
│   │   │   ├── AIAssistant.jsx       # AI 비서 (A2A 채팅)
│   │   │   └── StockAnalysis.jsx     # View: 종목 분석 페이지
│   │   └── components/
│   │       └── Navbar.jsx     # 네비게이션 바
│   ├── vite.config.js         # Vite 설정 + API 프록시
│   ├── package.json
│   └── Dockerfile
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
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

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

---

## 로컬 실행 및 테스트

### 사전 준비

```bash
# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 필요)
```

### 개별 Agent 실행

각 에이전트를 **별도 터미널**에서 실행합니다:

```bash
# Sub-Agents
python -m sub_agents.news_agent.server         # :8001
python -m sub_agents.fundamental_agent.server  # :8002
python -m sub_agents.technical_agent.server    # :8003
python -m sub_agents.expert_agent.server       # :8004
python -m sub_agents.risk_agent.server         # :8005

# Orchestrator (모든 Sub-Agent 실행 후)
python -m orchestrator.server                  # :8000
```

### Agent Card 확인

```bash
curl http://localhost:8001/.well-known/agent.json
curl http://localhost:8002/.well-known/agent.json
curl http://localhost:8003/.well-known/agent.json
curl http://localhost:8004/.well-known/agent.json
curl http://localhost:8005/.well-known/agent.json
```

---

## Orchestrator 종합 분석 (A2A)

Orchestrator는 5개 Sub-Agent를 순차적으로 호출하여 종합 분석을 수행합니다.
A2A 엔드포인트는 FastAPI 앱의 `/adk/` 경로에 마운트되어 있습니다.

### 로컬 실행 시

```bash
# 미국 주식 분석
curl -s -X POST http://localhost:8000/adk/ \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"AAPL US market stock analysis please"}]}}}'

# 한국 주식 분석
curl -s -X POST http://localhost:8000/adk/ \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"삼성전자 KR market 주식 분석해줘"}]}}}'
```

### Docker 환경 (Nginx 경유)

```bash
curl -s -X POST http://localhost/adk/ \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"AAPL US market stock analysis please"}]}}}'
```

### Windows PowerShell

```powershell
$body = @{
    jsonrpc = "2.0"
    id = "1"
    method = "message/send"
    params = @{
        message = @{
            messageId = "m1"
            role = "user"
            parts = @(@{kind = "text"; text = "삼성전자 KR market 주식 분석해줘"})
        }
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:8000/adk/" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -ContentType "application/json; charset=utf-8"
```

### Orchestrator 엔드포인트 정리

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/api/health` | GET | Health check |
| `/api/agents` | GET | Sub-agent 목록 |
| `/api/analyze` | POST | **종목 분석 요청 (InMemoryRunner)** |
| `/adk/` | POST | **A2A 종합 분석 (JSON-RPC 2.0)** |
| `/adk/.well-known/agent.json` | GET | Orchestrator Agent Card |

### 응답 구조

Orchestrator는 프롬프트에 정의된 형식대로 마크다운 응답을 반환합니다:

1. **종합 분석 요약** - 각 Agent 결과 요약
2. **점수 산출** - Agent별 신호/점수/가중치/가중점수 테이블
3. **최종 결정** - BUY/SELL/HOLD, 수량, 목표가, 손절가
4. **판단 근거** - 2~3문장 종합 판단

### 주의사항

- **한글 인코딩**: curl로 한글 전송 시 `charset=utf-8` 헤더 필수. Windows CMD에서는 JSON 파일(`-d @request.json`) 사용 권장
- **응답 시간**: 5개 Sub-Agent를 순차 호출하므로 30초~2분 소요 가능
- **ticker 명시**: "AAPL US market" 또는 "삼성전자 KR market"처럼 ticker와 market을 함께 제공하면 추가 질의 없이 바로 분석 시작

---

## 테스트 스크립트 사용

`test_agent.py` 스크립트로 간편하게 테스트할 수 있습니다:

```bash
# 기본 사용법
python test_agent.py <port> "<message>"

# 디버그 모드 (전체 JSON 응답 확인)
python test_agent.py <port> --debug "<message>"
```

### 에이전트별 테스트 예시

```bash
# News Agent (8001)
python test_agent.py 8001 "Analyze recent news for AAPL"
python test_agent.py 8001 "삼성전자 최신 뉴스 분석해줘"

# Fundamental Agent (8002)
python test_agent.py 8002 "Analyze financials for TSLA"
python test_agent.py 8002 "005930 재무제표 분석해줘"

# Technical Agent (8003)
python test_agent.py 8003 "Analyze technical indicators for AAPL"
python test_agent.py 8003 "NVDA 기술적 분석해줘"

# Expert Agent (8004)
python test_agent.py 8004 "Get analyst ratings for MSFT"
python test_agent.py 8004 "애플 애널리스트 의견 분석해줘"

# Risk Agent (8005)
python test_agent.py 8005 "Calculate position size for AAPL with 100000 capital"
python test_agent.py 8005 "10만달러 자본으로 TSLA 포지션 사이징해줘"
```

---

## curl을 사용한 A2A 질의

A2A는 JSON-RPC 2.0 프로토콜을 사용합니다.

### Windows PowerShell

```powershell
# News Agent 테스트
$body = @{
    jsonrpc = "2.0"
    id = "1"
    method = "message/send"
    params = @{
        message = @{
            messageId = "m1"
            role = "user"
            parts = @(@{kind = "text"; text = "Analyze recent news for AAPL"})
        }
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:8001/" -Method Post -Body $body -ContentType "application/json"
```

### Linux/Mac (또는 Git Bash)

```bash
# News Agent (8001)
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Analyze recent news for AAPL"}]
      }
    }
  }'

# Fundamental Agent (8002)
curl -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Analyze financials for TSLA"}]
      }
    }
  }'

# Technical Agent (8003)
curl -X POST http://localhost:8003/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Analyze technical indicators for NVDA"}]
      }
    }
  }'

# Expert Agent (8004)
curl -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Get analyst ratings for MSFT"}]
      }
    }
  }'

# Risk Agent (8005)
curl -X POST http://localhost:8005/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Calculate position size for AAPL with 100000 capital"}]
      }
    }
  }'
```

### JSON 파일 사용 (Windows CMD 권장)

1. `request.json` 파일 생성:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "m1",
      "role": "user",
      "parts": [{"kind": "text", "text": "Analyze technical indicators for AAPL"}]
    }
  }
}
```

2. curl 실행:

```bash
curl -X POST http://localhost:8003/ -H "Content-Type: application/json" -d @request.json
```

### A2A 메서드

| 메서드 | 설명 |
|--------|------|
| `message/send` | 완료 후 전체 응답 반환 |
| `message/stream` | SSE 스트리밍 (실시간 응답) |

---

## Docker 실행

### 전체 시스템 빌드 및 실행

```bash
docker compose up --build
```

### 개별 서비스 실행

```bash
# Orchestrator + Sub-Agents + 인프라 (depends_on으로 자동 포함)
docker compose up --build orchestrator

# Sub-Agents만 실행
docker compose up news-agent fundamental-agent technical-agent expert-agent risk-agent
```

### Docker 환경에서 테스트 (Nginx 경유)

```bash
# 에이전트 목록 확인
curl http://localhost/agents

# Orchestrator Health Check
curl http://localhost/api/health

# Orchestrator 종합 분석 (A2A)
curl -s -X POST http://localhost/adk/ \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"AAPL US market stock analysis please"}]}}}'

# 한국 주식 종합 분석
curl -s -X POST http://localhost/adk/ \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"삼성전자 KR market 주식 분석해줘"}]}}}'

# 개별 에이전트 테스트 (Nginx 경유)
curl -X POST http://localhost/agents/news/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"Analyze AAPL news"}]}}}'

curl -X POST http://localhost/agents/fundamental/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"Analyze TSLA financials"}]}}}'

curl -X POST http://localhost/agents/technical/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"Analyze NVDA technicals"}]}}}'
```

---

## Frontend (React + Vite)

### 아키텍처 (MVC 패턴)

```
Model (데이터)         → services/api.js          axios HTTP 통신
Controller (상태/로직) → hooks/useStockAnalysis.js  useState + useCallback
View (렌더링)          → pages/StockAnalysis.jsx   JSX + react-markdown
```

### 페이지 구성

| 경로 | 컴포넌트 | 설명 |
|------|----------|------|
| `/` | `Dashboard` | 대시보드 |
| `/ai-assistant` | `AIAssistant` | AI 비서 (A2A 채팅) |
| `/stock-analysis` | `StockAnalysis` | 종목 분석 (종목코드 + 마켓 입력 → 마크다운 결과) |
| `/portfolio` | - | 포트폴리오 (준비중) |

### API 프록시 (CORS 해결)

Vite dev server가 `/api` 요청을 Orchestrator로 프록시합니다:

```
브라우저 → localhost:5173/api/analyze → (Vite proxy) → orchestrator:8000/api/analyze
```

`vite.config.js`:
```javascript
proxy: {
    '/api': { target: 'http://orchestrator:8000', changeOrigin: true }
}
```

### Docker 실행

Frontend는 `docker compose up --build`로 전체 시스템과 함께 기동됩니다.
별도 실행 불필요 (docker-compose.yml에 frontend 서비스 포함).

```bash
# 전체 시스템 (Backend + Frontend)
docker compose up --build

# Frontend 접속
http://localhost:5173
```

### Frontend 의존성

- `react`, `react-dom` 18.x
- `react-router-dom` 6.x (클라이언트 라우팅)
- `axios` (HTTP 클라이언트)
- `react-markdown` + `remark-gfm` (마크다운 렌더링)
- `bootstrap` 5.x (UI 프레임워크)
- `lucide-react` (아이콘)

---

## 주요 의존성

- `google-adk[a2a]` >= 1.23
- `yfinance` (재무제표, API 키 불필요)
- `httpx`, `beautifulsoup4` (뉴스 스크래핑)
- `fastapi`, `uvicorn` (웹 서버)
- `pydantic-settings` (설정 관리)
- `apscheduler` (스케줄링)
