FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ /app/agents/
COPY utils/ /app/utils/

# AGENT_MODULE: 실행할 에이전트의 A2A 서버 모듈 경로
# 예: agents.news_analysis.a2a_server:app
ENV AGENT_MODULE="agents.news_analysis.a2a_server:app"
ENV AGENT_PORT="8001"

EXPOSE ${AGENT_PORT}

CMD uvicorn ${AGENT_MODULE} --host 0.0.0.0 --port ${AGENT_PORT}
