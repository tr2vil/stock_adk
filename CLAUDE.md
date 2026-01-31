# CLAUDE.md - StockADK 개발 컨텍스트

## 프로젝트 개요

Google ADK + A2A 기반 주식 분석 멀티 에이전트 시스템.
각 에이전트는 독립 컨테이너로 실행되며, 향후 오케스트레이터가 에이전트들을 조율하여 종합 분석/투자 전략을 수립할 예정.

## 에이전트 개발 패턴

모든 에이전트는 아래 구조를 따른다:

```
agents/<agent_name>/
├── __init__.py       # from . import agent
├── agent.py          # root_agent 정의 (Google ADK Agent)
├── tools.py          # 도구 함수 (async, type hint + docstring 필수)
├── prompt.py         # AGENT_INSTRUCTION 상수
└── a2a_server.py     # A2A 프로토콜 서버
```

### agent.py 패턴

```python
import os, json, tempfile
from dotenv import load_dotenv
load_dotenv()

# GOOGLE_KEY JSON → GOOGLE_APPLICATION_CREDENTIALS 자동 설정
_google_key = os.getenv("GOOGLE_KEY")
if _google_key and _google_key.strip().startswith("{"):
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        _cred_dir = os.path.join(tempfile.gettempdir(), "stock_adk")
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
- JSON 직렬화 안전: `NaN`, `Inf` → `None` 변환 필요 (`_safe_float`)

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

### a2a_server.py 패턴

```python
import os
from dotenv import load_dotenv
load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from .agent import root_agent

A2A_PORT = int(os.getenv("<AGENT_NAME>_A2A_PORT", "<port>"))
app = to_a2a(root_agent, port=A2A_PORT)
```

### prompt.py 패턴

```python
AGENT_INSTRUCTION = """\
역할, 도구 사용법, 분석 항목, 응답 형식, 주의사항을 포함.
"""
```

## 인프라 패턴

### Docker 서비스 추가 (docker-compose.yml)

```yaml
<agent_name>_agent:
  build:
    context: .
    dockerfile: ./agents/Dockerfile
  container_name: stock_<agent_name>_agent
  environment:
    - AGENT_MODULE=agents.<agent_name>.a2a_server:app
    - AGENT_PORT=<port>
  env_file:
    - .env
  volumes:
    - ./agents:/app/agents
    - ./utils:/app/utils
  ports:
    - "<port>:<port>"
  networks:
    - stock_network
```

### Nginx 라우팅 추가 (docker/nginx/nginx.conf)

```nginx
upstream <agent_name>_agent { server <agent_name>_agent:<port>; }

location /agents/<agent_name>/ {
    proxy_pass http://<agent_name>_agent/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
}
```

## 기존 에이전트

| 에이전트 | 디렉토리 | 포트 | 도구 | 데이터 소스 |
|----------|----------|------|------|-------------|
| news_analysis | `agents/news_analysis/` | 8001 | `fetch_korean_stock_news`, `fetch_us_stock_news` | 네이버 뉴스, Google News RSS |
| balance_sheet | `agents/balance_sheet/` | 8002 | `fetch_korean_financials`, `fetch_us_financials` | yfinance |

## 포트 할당

| 포트 | 서비스 |
|------|--------|
| 80 | Nginx |
| 3001 | Grafana |
| 5173 | Frontend |
| 5432 | PostgreSQL |
| 8000 | Backend API |
| 8001 | news_analysis agent |
| 8002 | balance_sheet agent |
| 8003+ | 향후 에이전트용 |

## 한국 주식 종목명 처리

- `_KR_NAME_MAP` 딕셔너리로 한글 → 영문 매핑 후 `yf.Search()` 호출
- 6자리 숫자는 종목코드로 직접 사용 (`.KS` suffix)
- `.KS`(KOSPI) 실패 시 `.KQ`(KOSDAQ) 자동 재시도

## 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GOOGLE_GENAI_USE_VERTEXAI` | Vertex AI 사용 여부 | TRUE |
| `GOOGLE_CLOUD_PROJECT` | GCP 프로젝트 ID | - |
| `GOOGLE_CLOUD_LOCATION` | GCP 리전 | us-central1 |
| `GOOGLE_KEY` | 서비스 계정 JSON 문자열 | - |
| `NEWS_AGENT_MODEL` | 뉴스 에이전트 모델 | gemini-2.5-flash |
| `BALANCE_SHEET_AGENT_MODEL` | 재무제표 에이전트 모델 | gemini-2.5-flash |

## A2A 서버 기동 및 질의

### 서버 기동

각 에이전트를 별도 터미널에서 실행 (프로젝트 루트에서, venv 활성화 상태):

```bash
python -m agents.news_analysis.a2a_server      # :8001
python -m agents.balance_sheet.a2a_server       # :8002
```

### Agent Card 확인

```bash
curl http://localhost:8001/.well-known/agent.json
curl http://localhost:8002/.well-known/agent.json
```

### A2A 질의 (JSON-RPC 2.0)

```bash
# 뉴스 분석
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/send",
    "params": {
      "id": "task-001",
      "message": {
        "role": "user",
        "parts": [{"text": "삼성전자 최근 뉴스를 분석해줘"}]
      }
    }
  }'

# 재무제표 분석
curl -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/send",
    "params": {
      "id": "task-002",
      "message": {
        "role": "user",
        "parts": [{"text": "AAPL 재무제표를 분석해줘"}]
      }
    }
  }'

# SSE 스트리밍 (실시간 응답)
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/sendSubscribe",
    "params": {
      "id": "task-003",
      "message": {
        "role": "user",
        "parts": [{"text": "현대차 뉴스 분석해줘"}]
      }
    }
  }'
```

### A2A 메서드

| 메서드 | 설명 |
|--------|------|
| `tasks/send` | 완료 후 전체 응답 반환 |
| `tasks/sendSubscribe` | SSE 스트리밍 (실시간 응답) |

### Docker 환경에서 질의 (Nginx 경유)

```bash
# Nginx 리버스 프록시 경유 (:80)
curl -X POST http://localhost/agents/news/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tasks/send","params":{"id":"t1","message":{"role":"user","parts":[{"text":"TSLA 뉴스 분석"}]}}}'

curl -X POST http://localhost/agents/balance_sheet/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tasks/send","params":{"id":"t2","message":{"role":"user","parts":[{"text":"삼성전자 재무제표 분석"}]}}}'

# 에이전트 목록 디스커버리
curl http://localhost/agents
```

## 테스트

```bash
# ADK Runner 기반 테스트
python test_news_agent.py 삼성전자

# A2A 통합 테스트 (서버 먼저 실행 필요)
python -m agents.news_analysis.a2a_server &
python test_a2a.py
```

## 주요 의존성

- `google-adk[a2a]` >= 1.23
- `yfinance` (재무제표, API 키 불필요)
- `httpx`, `beautifulsoup4` (뉴스 스크래핑)
- `python-dotenv` (환경변수)
