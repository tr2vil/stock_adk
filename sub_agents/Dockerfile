FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing .pyc files and ensure real-time log output
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (separate layer for Docker cache efficiency)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY sub_agents/ /app/sub_agents/
COPY shared/ /app/shared/

# Set Python path
ENV PYTHONPATH=/app

# Supported agents (override AGENT_NAME and AGENT_PORT at build or run time):
#   news_agent (8001), fundamental_agent (8002), technical_agent (8003),
#   expert_agent (8004), risk_agent (8005)
#
# Build:  docker build --build-arg AGENT_NAME=technical_agent --build-arg AGENT_PORT=8003 ...
# Run:    docker run -e AGENT_MODULE=sub_agents.technical_agent.server:app -e AGENT_PORT=8003 ...
ARG AGENT_NAME=news_agent
ARG AGENT_PORT=8001

ENV AGENT_MODULE="sub_agents.${AGENT_NAME}.server:app" \
    AGENT_PORT="${AGENT_PORT}"

EXPOSE ${AGENT_PORT}

# Health check via A2A agent card endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c 'import urllib.request,os; urllib.request.urlopen("http://localhost:"+os.environ["AGENT_PORT"]+"/.well-known/agent.json")' || exit 1

# exec ensures uvicorn is PID 1 and receives SIGTERM for graceful shutdown
CMD ["sh", "-c", "exec uvicorn ${AGENT_MODULE} --host 0.0.0.0 --port ${AGENT_PORT}"]
