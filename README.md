# StockADK - AI 주식 분석 멀티 에이전트 시스템

Google ADK + A2A 프로토콜 기반의 주식 분석 멀티 에이전트 시스템.
각 에이전트가 독립 컨테이너로 실행되며, Nginx를 통해 라우팅됩니다.

## 아키텍처

```
                     ┌──────────┐
                     │  Nginx   │ :80
                     └────┬─────┘
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
   ┌──────────────┐ ┌───────────┐ ┌──────────────────┐
   │ news_agent   │ │  backend  │ │ balance_sheet     │
   │ :8001        │ │  :8000    │ │ _agent :8002      │
   └──────┬───────┘ └───────────┘ └──────┬───────────┘
          │                              │
   ┌──────┴───────┐              ┌───────┴──────────┐
   │네이버 / Google│              │    yfinance       │
   │   News       │              │ (KR+US 재무제표)   │
   └──────────────┘              └──────────────────┘
```

## 프로젝트 구조

```
stock_adk/
├── agents/
│   ├── Dockerfile                   # 에이전트 공용 Docker 이미지
│   ├── news_analysis/               # 뉴스 분석 에이전트
│   │   ├── agent.py                 # root_agent
│   │   ├── tools.py                 # 뉴스 수집 (네이버, Google News)
│   │   ├── prompt.py                # 에이전트 지시문
│   │   ├── a2a_server.py            # A2A 서버 (:8001)
│   │   └── __init__.py
│   └── balance_sheet/               # 재무제표 분석 에이전트
│       ├── agent.py                 # root_agent
│       ├── tools.py                 # 재무제표 수집 (yfinance)
│       ├── prompt.py                # 에이전트 지시문
│       ├── a2a_server.py            # A2A 서버 (:8002)
│       └── __init__.py
├── backend/                         # FastAPI 백엔드
├── frontend/                        # React 프론트엔드
├── docker/nginx/nginx.conf          # 리버스 프록시 설정
├── .env                             # 환경변수
├── docker-compose.yml
└── CLAUDE.md                        # AI 개발 컨텍스트
```

## 환경 설정

### 의존성 설치

```bash
python -m venv .venv
.venv\Scripts\activate
pip install "google-adk[a2a]" httpx beautifulsoup4 python-dotenv yfinance
```

### 환경변수 (.env)

```env
# Google Cloud
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_KEY='{ ... service account JSON ... }'

# 에이전트별 모델 (기본값: gemini-2.5-flash)
NEWS_AGENT_MODEL=gemini-2.5-flash
BALANCE_SHEET_AGENT_MODEL=gemini-2.5-flash

# A2A 포트
NEWS_AGENT_A2A_PORT=8001
BALANCE_SHEET_AGENT_A2A_PORT=8002
```

## 실행 방법

### 로컬 테스트

```bash
# 뉴스 분석
python test_news_agent.py 삼성전자
python test_news_agent.py AAPL
```

### A2A 서버 기동

각 에이전트를 별도 터미널에서 실행:

```bash
python -m agents.news_analysis.a2a_server      # :8001
python -m agents.balance_sheet.a2a_server       # :8002
```

서버 정상 동작 확인 (Agent Card):

```bash
curl http://localhost:8001/.well-known/agent.json
curl http://localhost:8002/.well-known/agent.json
```

### A2A 질의 (curl)

A2A는 JSON-RPC 2.0 프로토콜을 사용합니다 (A2A SDK 0.3.x).

```bash
# 뉴스 분석 요청
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
        "parts": [{"kind": "text", "text": "Analyze recent news for AAPL"}]
      }
    }
  }'

# 재무제표 분석 요청
curl -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-002",
        "role": "user",
        "parts": [{"kind": "text", "text": "Analyze financials for TSLA"}]
      }
    }
  }'
```

> **Note**: Windows CMD에서 한글 사용 시 UTF-8 인코딩 문제가 발생할 수 있습니다.

| 메서드 | 설명 |
|--------|------|
| `message/send` | 완료 후 전체 응답 반환 |
| `message/stream` | SSE 스트리밍 (실시간 응답) |

### Docker (전체 서비스)

```bash
docker-compose up -d --build
```

| 서비스 | URL | 설명 |
|--------|-----|------|
| Nginx | http://localhost | 리버스 프록시 |
| Backend API | http://localhost:8000 | FastAPI |
| Frontend | http://localhost:5173 | React |
| News Agent | http://localhost:8001 | 뉴스 분석 A2A |
| Balance Sheet Agent | http://localhost:8002 | 재무제표 분석 A2A |
| Grafana | http://localhost:3001 | 모니터링 |

## 에이전트 목록

### 1. News Analysis Agent

뉴스를 수집하고 투자 심리를 분석합니다.

| 항목 | 값 |
|------|-----|
| 이름 | `news_analysis_agent` |
| 포트 | 8001 |
| 도구 | `fetch_korean_stock_news`, `fetch_us_stock_news` |
| 데이터 소스 | 네이버 뉴스 (KR), Google News RSS (US) |

**분석 항목:** 뉴스 요약, 주요 뉴스 TOP 3, 투자 심리(Positive/Neutral/Negative), 리스크/기회 요인

### 2. Balance Sheet Agent

재무제표를 수집하고 투자 적합성을 판단합니다.

| 항목 | 값 |
|------|-----|
| 이름 | `balance_sheet_agent` |
| 포트 | 8002 |
| 도구 | `fetch_korean_financials`, `fetch_us_financials` |
| 데이터 소스 | yfinance (API 키 불필요) |

**분석 항목:**
- 단기 건전성: 유동비율, 당좌비율, 현금 보유량
- 중기 수익성: 매출/영업이익/순이익 성장률, 마진 추세
- 장기 안정성: 부채비율, 자기자본비율, FCF 추세
- 투자 등급: A(적극매수) ~ F(부적합)

**종목 입력:** 한국어 종목명(삼성전자) 자동 변환, 미국 티커(AAPL) 직접 사용

## 새 에이전트 추가 가이드

`CLAUDE.md` 참조.

## Tech Stack

| 영역 | 기술 |
|------|------|
| AI Framework | Google ADK 1.23+ |
| LLM | Gemini 2.5 Flash (Vertex AI) |
| Protocol | A2A (Agent-to-Agent) |
| Financial Data | yfinance |
| Backend | FastAPI, Python 3.12 |
| Frontend | React, Vite |
| Proxy | Nginx |
| Infra | Docker, Docker Compose |
