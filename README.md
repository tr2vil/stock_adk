# StockADK: AI-Powered Trading Assistant

StockADK는 인공지능을 활용하여 주식 뉴스 분석, 재무제표 진단 및 시장 예측을 도와주는 개인용 트레이딩 비서 시스템입니다. Google의 최신 LLM인 **Gemini 2.5 Flash**와 **Vertex AI**를 기반으로 하며, 사용자 친화적인 **A2UI(Agent-to-User Interface)**를 제공합니다.

## 🚀 주요 기능

### 1. AI 뉴스 분석 (완료)
- **실시간 뉴스 스크래핑**: 네이버 뉴스(모바일) 검색 결과를 바탕으로 최신 트렌드를 파악합니다.
- **Gemini 분석**: 뉴스 요약, 주요 이슈 선별 및 투자 심리(긍정/중립/부정)를 분석합니다.
- **A2UI 카드**: 채팅 인터페이스를 통해 구조화된 분석 결과를 시각적으로 제공합니다.
- **하이브리드 파싱**: 정적 셀렉터와 LLM 기반 HTML 파싱을 결합하여 스크래핑 신뢰도를 극대화했습니다.

### 2. 시장 대시보드 및 지표 시각화 (준비 중)
- **Grafana 통합**: 주요 경제 지표 및 주가 데이터를 시각화하여 대시보드에 표시합니다.
- **PostgreSQL 기반**: 안정적인 데이터 저장 및 관리를 위한 DBMS 구성.

### 3. 향후 구현 예정
- **재무제표 분석**: 기업의 공시 및 재무 데이터를 기반으로 한 자동 진단.
- **주가 예측 에이전트**: 머신러닝 및 AI를 활용한 단기/중기 주가 흐름 예측.

## 🛠 기술 스택

### Backend
- **Framework**: FastAPI (Python 3.10)
- **AI/LLM**: Google Vertex AI (Gemini 2.5 Flash)
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Scraping**: BeautifulSoup4, HTTPX

### Frontend
- **Framework**: React (Vite)
- **UI Components**: Bootstrap 5, Lucide React
- **Aesthetics**: Modern Dark Mode, Glassmorphism, Responsive Design

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Monitoring/Visualization**: Grafana

## ⚙️ 시작하기

### 환경 변수 설정
`.env` 파일을 루트 디렉토리에 생성하고 아래 정보를 입력합니다:
```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_KEY=your-service-account-json-content-or-path
# 포트 설정
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

### 실행 방법
Docker Compose를 사용하여 모든 서비스를 한 번에 실행합니다:
```bash
docker-compose up -d --build
```

- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`
- **Grafana**: `http://localhost:3000`

## � Docker 관리 및 운영

컨테이너 환경을 효율적으로 관리하기 위한 주요 명령어 모음입니다.

### 1. 서비스 시작 및 빌드
- **전체 서비스 빌드 및 실행**:
  ```bash
  docker-compose up -d --build
  ```
- **특정 서비스만 다시 빌드 (예: 백엔드)**:
  ```bash
  docker-compose up -d --build backend
  ```

### 2. 서비스 중지
- **컨테이너 정지 및 유지**:
  ```bash
  docker-compose stop
  ```
- **컨테이너 정지 및 네트워크/이미지 정리**:
  ```bash
  docker-compose down
  ```

### 3. 로그 확인 및 모니터링
- **전체 로그 실시간 확인**:
  ```bash
  docker-compose logs -f
  ```
- **특정 컨테이너 로그 확인**:
  ```bash
  docker-compose logs -f backend
  ```

### 4. 컨테이너 내부 접속 및 명령 실행
- **백엔드 컨테이너 접속**:
  ```bash
  docker exec -it stock_backend /bin/bash
  ```
- **데이터베이스(PostgreSQL) 접속**:
  ```bash
  docker exec -it stock_db psql -U admin -d stock_db
  ```

### 5. 문제 해결 (Troubleshooting)
- **백엔드 소스코드 수정 후 즉시 반영**:
  (볼륨 마운트 설정으로 대부분 자동 반영되나, 패키지 추가 시 필요)
  ```bash
  docker-compose restart backend
  ```
- **도커 캐시 무시하고 클린 빌드**:
  ```bash
  docker-compose build --no-cache
  ```

## �📄 최근 업데이트
- **Version 0.2**: 백엔드 500 에러 해결 및 Vertex AI(Gemini 2.5 Flash) 연동 완료.
- **News Agent**: 모바일 페이지 스크래퍼 및 LLM 폴백 파서 도입으로 안정성 강화.
- **Documentation**: Docker 운영 가이드 및 상세 README 작성.
