# Trading System - AI 멀티에이전트 자동매매 시스템

Google ADK + A2A Protocol 기반의 주식 분석 멀티에이전트 시스템.
Orchestrator가 5개의 전문 Sub-Agent를 조율하여 종합 분석 및 투자 결정을 수행합니다.

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
│  20%     │ │  25%     │ │  30%     │ │  15%     │ │  10%     │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
     │            │            │            │            │
     ▼            ▼            ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ 네이버   │ │ yfinance │ │ yfinance │ │ yfinance │ │ 포지션   │
│ Google   │ │ 재무제표 │ │ 가격차트 │ │ 애널리스트│ │ 사이징   │
│ News     │ │          │ │          │ │ 리포트   │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## 에이전트 목록

| Agent | 포트 | 가중치 | 역할 | 주요 도구 |
|-------|------|--------|------|-----------|
| **Orchestrator** | 8000 | - | 전체 분석 조율 및 의사결정 | RemoteA2aAgent |
| News Agent | 8001 | 20% | 뉴스 수집 및 센티먼트 분석 | `fetch_korean_stock_news`, `fetch_us_stock_news` |
| Fundamental Agent | 8002 | 25% | 재무제표 분석 | `fetch_korean_financials`, `fetch_us_financials` |
| Technical Agent | 8003 | 30% | 기술적 지표 분석 | `analyze_technical`, `detect_patterns` |
| Expert Agent | 8004 | 15% | 애널리스트/기관 동향 분석 | `collect_analyst_ratings`, `analyze_institutional_flow` |
| Risk Agent | 8005 | 10% | 리스크 관리 및 포지션 사이징 | `calculate_position_size`, `assess_portfolio_risk` |

## 프로젝트 구조

```
trading-system/
├── orchestrator/              # 오케스트레이터 (Port 8000)
│   ├── agent.py               # Root Agent with RemoteA2aAgent
│   ├── decision_engine.py     # 가중 합산 로직
│   ├── scheduler.py           # APScheduler 스케줄러
│   ├── server.py              # FastAPI + ADK API Server
│   ├── prompt.py              # 오케스트레이터 인스트럭션
│   └── Dockerfile
├── sub_agents/                # Sub-Agent 모음
│   ├── news_agent/            # 뉴스 분석 에이전트
│   ├── fundamental_agent/     # 재무제표 분석 에이전트
│   ├── technical_agent/       # 기술적 분석 에이전트
│   ├── expert_agent/          # 전문가 신호 에이전트
│   ├── risk_agent/            # 리스크 관리 에이전트
│   └── Dockerfile             # 공유 Dockerfile
├── execution/                 # 주문 실행 모듈
│   ├── kiwoom_rest.py         # 키움증권 REST API
│   ├── order_manager.py       # 주문 관리자
│   └── websocket_client.py    # 실시간 시세
├── shared/                    # 공유 모듈
│   ├── models.py              # Pydantic 데이터 모델
│   ├── config.py              # 환경 설정 (pydantic-settings)
│   ├── database.py            # SQLAlchemy 설정
│   └── logger.py              # structlog 로깅
├── monitoring/                # 모니터링
│   ├── dashboard.py           # Streamlit 대시보드
│   └── alerting.py            # Telegram/Slack 알림
├── docker/
│   └── nginx/nginx.conf       # Nginx 리버스 프록시 설정
├── docker-compose.yml         # Docker Compose 설정
├── requirements.txt           # Python 의존성
├── pyproject.toml             # 프로젝트 메타데이터
├── test_agent.py              # 에이전트 테스트 스크립트
├── .env.example               # 환경변수 예시
└── CLAUDE.md                  # AI 개발 컨텍스트
```

## 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd trading-system

# 가상환경 생성 및 활성화
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env
```

`.env` 파일 편집:

```env
# Google Cloud (Vertex AI)
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_KEY='{ ... service account JSON ... }'

# 모델 설정
ORCHESTRATOR_MODEL=gemini-2.5-pro
NEWS_AGENT_MODEL=gemini-2.5-flash
FUNDAMENTAL_AGENT_MODEL=gemini-2.5-flash
TECHNICAL_AGENT_MODEL=gemini-2.5-flash
EXPERT_AGENT_MODEL=gemini-2.5-flash
RISK_AGENT_MODEL=gemini-2.5-flash

# 호스트 설정 (로컬 실행 시)
NEWS_AGENT_HOST=localhost
FUNDAMENTAL_AGENT_HOST=localhost
TECHNICAL_AGENT_HOST=localhost
EXPERT_AGENT_HOST=localhost
RISK_AGENT_HOST=localhost
```

### 3. 로컬 실행

각 에이전트를 **별도 터미널**에서 실행:

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

### 4. 테스트

```bash
# 테스트 스크립트 사용
python test_agent.py 8003 "Analyze technical indicators for AAPL"

# 디버그 모드
python test_agent.py 8003 --debug "Analyze technical indicators for AAPL"
```

## 에이전트별 테스트 예시

### News Agent (8001)

```bash
python test_agent.py 8001 "Analyze recent news for AAPL"
python test_agent.py 8001 "삼성전자 최신 뉴스 분석해줘"
```

### Fundamental Agent (8002)

```bash
python test_agent.py 8002 "Analyze financials for TSLA"
python test_agent.py 8002 "005930 재무제표 분석해줘"
```

### Technical Agent (8003)

```bash
python test_agent.py 8003 "Analyze technical indicators for NVDA"
python test_agent.py 8003 "애플 기술적 분석해줘"
```

### Expert Agent (8004)

```bash
python test_agent.py 8004 "Get analyst ratings for MSFT"
python test_agent.py 8004 "테슬라 애널리스트 의견 분석해줘"
```

### Risk Agent (8005)

```bash
python test_agent.py 8005 "Calculate position size for AAPL with 100000 capital"
python test_agent.py 8005 "10만달러로 NVDA 포지션 사이징해줘"
```

## Docker 실행

### 전체 시스템

```bash
# 빌드 및 실행
docker-compose up --build

# 백그라운드 실행
docker-compose up -d --build
```

### 서비스 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| Nginx | http://localhost | 리버스 프록시 |
| Orchestrator API | http://localhost/api/ | REST API |
| Orchestrator ADK | http://localhost/adk/ | A2A 엔드포인트 |
| News Agent | http://localhost/agents/news/ | 뉴스 분석 |
| Fundamental Agent | http://localhost/agents/fundamental/ | 재무 분석 |
| Technical Agent | http://localhost/agents/technical/ | 기술적 분석 |
| Expert Agent | http://localhost/agents/expert/ | 전문가 분석 |
| Risk Agent | http://localhost/agents/risk/ | 리스크 관리 |
| Grafana | http://localhost:3001 | 모니터링 대시보드 |
| PostgreSQL | localhost:5432 | 데이터베이스 |
| Redis | localhost:6379 | 캐시 |

### Docker 환경 테스트

```bash
# 에이전트 목록 확인
curl http://localhost/agents

# Health Check
curl http://localhost/api/health

# 기술적 분석 요청
curl -X POST http://localhost/agents/technical/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"kind":"text","text":"Analyze AAPL technicals"}]}}}'
```

## 의사결정 로직

1. Orchestrator가 5개 Sub-Agent에게 분석 요청
2. 각 Agent 결과를 `-1.0` ~ `+1.0` 점수로 변환
3. 가중 합산: `final_score = Σ(agent_score × weight)`
4. 결정:
   - `final_score > +0.3`: **BUY**
   - `final_score < -0.3`: **SELL**
   - 그 외: **HOLD**
5. Risk Agent가 "high" 리스크 판정 시 수량 50% 감소

## 안전 규칙

- 단일 종목 최대 투자비율: **20%**
- 1회 거래 최대 리스크: **2%**
- 최소 손익비: **1.5:1**
- 일일 최대 거래: **10회**
- 동시 보유 최대: **10종목**

## Tech Stack

| 영역 | 기술 |
|------|------|
| AI Framework | Google ADK 1.23+ |
| LLM | Gemini 2.5 Pro/Flash (Vertex AI) |
| Protocol | A2A (Agent-to-Agent) JSON-RPC 2.0 |
| Financial Data | yfinance, 네이버 뉴스, Google News RSS |
| Backend | FastAPI, Python 3.12+ |
| Database | PostgreSQL, Redis |
| Infra | Docker, Docker Compose, Nginx |
| Monitoring | Grafana, Streamlit |

## 개발 가이드

새 에이전트 추가 및 개발 패턴은 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

## 라이선스

MIT License
