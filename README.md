# StockADK - AI 주식 뉴스 분석 에이전트

Google ADK(Agent Development Kit) + A2A(Agent-to-Agent) 프로토콜 기반의 주식 뉴스 분석 시스템.

## 아키텍처

```
                          ┌─────────────────────────────┐
                          │      ADK Agent (Gemini)      │
                          │    news_analysis_agent       │
                          └──────┬──────────────┬───────┘
                                 │              │
                    ┌────────────▼──┐     ┌─────▼────────────┐
                    │  한국 뉴스 도구 │     │  미국 뉴스 도구   │
                    │  (네이버 뉴스) │     │  (Google News)   │
                    └───────────────┘     └──────────────────┘

  [사용자 질문] → ADK Runner / A2A Server → 에이전트 → 도구 호출 → 뉴스 분석 응답
```

- **에이전트**가 사용자 질문을 해석하여 적절한 도구를 자동 선택
- 한국 종목명(삼성전자, 현대차) → `fetch_korean_stock_news`
- 미국 티커(AAPL, TSLA) → `fetch_us_stock_news`
- 수집된 뉴스를 Gemini가 분석하여 요약/심리/주요뉴스 제공

## 프로젝트 구조

```
stock_adk/
├── agents/news_analysis/        # 뉴스 분석 에이전트
│   ├── agent.py                 # ADK Agent 정의 (root_agent)
│   ├── tools.py                 # 도구: 한국/미국 뉴스 수집
│   ├── a2a_server.py            # A2A 프로토콜 서버
│   └── __init__.py
├── backend/                     # FastAPI 백엔드
│   ├── main.py
│   ├── core/orchestrator.py
│   └── requirements.txt
├── frontend/                    # React 프론트엔드
├── utils/                       # 유틸리티 (인증 등)
├── .env                         # 환경변수 (API 키, 모델 설정)
├── test_news_agent.py           # 에이전트 테스트
├── test_a2a.py                  # A2A 통합 테스트
└── docker-compose.yml
```

## 환경 설정

### 1. 의존성 설치

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install "google-adk[a2a]" httpx beautifulsoup4 python-dotenv
```

### 2. 환경변수 (.env)

```env
# Google Cloud (Vertex AI)
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_KEY='{ ... service account JSON ... }'

# 모델 설정 (변경 가능)
NEWS_AGENT_MODEL=gemini-2.5-flash

# A2A 서버 포트
NEWS_AGENT_A2A_PORT=8001
```

## 실행 방법

### 로컬 테스트 (Runner)

```bash
# 기본 테스트 (삼성전자)
python test_news_agent.py

# 특정 종목
python test_news_agent.py 현대차
python test_news_agent.py AAPL

# 복수 종목
python test_news_agent.py "SK하이닉스" TSLA
```

### A2A 서버 실행

```bash
# 서버 시작 (포트 8001)
python -m agents.news_analysis.a2a_server

# Agent Card 확인
curl http://localhost:8001/.well-known/agent.json
```

### ADK Web UI

```bash
# agents/ 디렉토리 상위에서 실행
adk web agents/
# http://localhost:4200 에서 UI 접근
```

### A2A 통합 테스트

```bash
# 1. 먼저 A2A 서버 실행
python -m agents.news_analysis.a2a_server

# 2. 다른 터미널에서 테스트
python test_a2a.py
```

### Docker

```bash
docker-compose up -d --build
```

| 서비스 | URL |
|--------|-----|
| Backend API | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Grafana | http://localhost:3001 |
| A2A Agent | http://localhost:8001 |

## 에이전트 상세

### News Analysis Agent

| 항목 | 값 |
|------|-----|
| 이름 | `news_analysis_agent` |
| 모델 | `gemini-2.5-flash` (변경 가능) |
| 도구 | `fetch_korean_stock_news`, `fetch_us_stock_news` |

**분석 출력 항목:**
1. 뉴스 요약 (3-5문장)
2. 주요 뉴스 TOP 3 + 의미 분석
3. 투자 심리 판단 (Positive / Neutral / Negative)
4. 주의 사항 (리스크, 기회 요인)

### 새 에이전트 추가 방법

```python
# 1. agents/new_agent/tools.py - 도구 함수 (type hint + docstring 필수)
async def my_tool(param: str) -> dict:
    """도구 설명. LLM이 이 docstring을 읽고 호출 여부를 판단합니다.

    Args:
        param: 파라미터 설명

    Returns:
        dict: 결과
    """
    return {"result": "..."}

# 2. agents/new_agent/agent.py - ADK Agent 정의
from google.adk.agents import Agent
from .tools import my_tool

root_agent = Agent(
    name="new_agent",
    model="gemini-2.5-flash",
    instruction="에이전트 역할 설명",
    tools=[my_tool],
)

# 3. agents/new_agent/__init__.py
from . import agent
```

## Tech Stack

| 영역 | 기술 |
|------|------|
| AI Framework | Google ADK 1.23+ |
| LLM | Gemini 2.5 Flash (Vertex AI) |
| Protocol | A2A (Agent-to-Agent) |
| Backend | FastAPI, Python 3.10+ |
| Frontend | React, Vite |
| DB | PostgreSQL |
| Infra | Docker, Docker Compose |
