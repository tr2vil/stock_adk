FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY sub_agents/ /app/sub_agents/
COPY shared/ /app/shared/

# Set Python path
ENV PYTHONPATH=/app

# Default values (override in docker-compose)
ENV AGENT_MODULE="sub_agents.news_agent.server:app"
ENV AGENT_PORT="8001"

EXPOSE ${AGENT_PORT}

CMD uvicorn ${AGENT_MODULE} --host 0.0.0.0 --port ${AGENT_PORT}
