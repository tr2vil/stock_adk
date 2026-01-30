"""
A2A Server - News Analysis Agent

이 스크립트를 실행하면 뉴스 분석 에이전트가 A2A 프로토콜 서버로 노출됩니다.
다른 에이전트가 A2A 프로토콜을 통해 이 에이전트와 통신할 수 있습니다.

Agent Card: http://localhost:8001/.well-known/agent.json

사용법:
    python -m agents.news_analysis.a2a_server
    또는
    uvicorn agents.news_analysis.a2a_server:app --host 0.0.0.0 --port 8001
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import root_agent

A2A_PORT = int(os.getenv("NEWS_AGENT_A2A_PORT", "8001"))

app = to_a2a(root_agent, port=A2A_PORT)

if __name__ == "__main__":
    import uvicorn

    print(f"Starting News Analysis A2A Server on port {A2A_PORT}")
    print(f"Agent Card: http://localhost:{A2A_PORT}/.well-known/agent.json")
    uvicorn.run(app, host="0.0.0.0", port=A2A_PORT)
