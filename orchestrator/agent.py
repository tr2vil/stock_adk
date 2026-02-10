"""
Trading Orchestrator - Root Agent with Sub-Agent Coordination
RemoteA2aAgent를 통해 5개의 sub-agent와 통신하여 종합 분석 수행
"""
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
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from .prompt import ORCHESTRATOR_INSTRUCTION

# Configuration from environment or defaults
NEWS_AGENT_HOST = os.getenv("NEWS_AGENT_HOST", "localhost")
NEWS_AGENT_PORT = os.getenv("NEWS_AGENT_PORT", "8001")
FUNDAMENTAL_AGENT_HOST = os.getenv("FUNDAMENTAL_AGENT_HOST", "localhost")
FUNDAMENTAL_AGENT_PORT = os.getenv("FUNDAMENTAL_AGENT_PORT", "8002")
TECHNICAL_AGENT_HOST = os.getenv("TECHNICAL_AGENT_HOST", "localhost")
TECHNICAL_AGENT_PORT = os.getenv("TECHNICAL_AGENT_PORT", "8003")
EXPERT_AGENT_HOST = os.getenv("EXPERT_AGENT_HOST", "localhost")
EXPERT_AGENT_PORT = os.getenv("EXPERT_AGENT_PORT", "8004")
RISK_AGENT_HOST = os.getenv("RISK_AGENT_HOST", "localhost")
RISK_AGENT_PORT = os.getenv("RISK_AGENT_PORT", "8005")

# Remote Sub-Agent connections via A2A Protocol
# google-adk 1.24+: agent_card URL must point to the agent card JSON endpoint,
# not the RPC root. The resolver GETs this URL to fetch the AgentCard.
AGENT_CARD_PATH = "/.well-known/agent.json"

news_agent = RemoteA2aAgent(
    name="news_agent",
    agent_card=f"http://{NEWS_AGENT_HOST}:{NEWS_AGENT_PORT}{AGENT_CARD_PATH}",
    description="종목 뉴스 수집 및 시황/센티먼트 분석",
)

fundamental_agent = RemoteA2aAgent(
    name="fundamental_agent",
    agent_card=f"http://{FUNDAMENTAL_AGENT_HOST}:{FUNDAMENTAL_AGENT_PORT}{AGENT_CARD_PATH}",
    description="재무제표 분석 및 밸류에이션 평가",
)

technical_agent = RemoteA2aAgent(
    name="technical_agent",
    agent_card=f"http://{TECHNICAL_AGENT_HOST}:{TECHNICAL_AGENT_PORT}{AGENT_CARD_PATH}",
    description="차트 기술적 분석 및 패턴 인식",
)

expert_agent = RemoteA2aAgent(
    name="expert_agent",
    agent_card=f"http://{EXPERT_AGENT_HOST}:{EXPERT_AGENT_PORT}{AGENT_CARD_PATH}",
    description="애널리스트 리포트 및 기관/외국인 수급 분석",
)

risk_agent = RemoteA2aAgent(
    name="risk_agent",
    agent_card=f"http://{RISK_AGENT_HOST}:{RISK_AGENT_PORT}{AGENT_CARD_PATH}",
    description="포지션 사이징 및 리스크 관리",
)

MODEL = os.getenv("ORCHESTRATOR_MODEL", "gemini-2.5-pro")

root_agent = Agent(
    name="trading_orchestrator",
    model=MODEL,
    description="주식 자동매매 시스템 오케스트레이터 - 5개 전문 에이전트를 조율하여 종합 분석 및 매매 결정",
    instruction=ORCHESTRATOR_INSTRUCTION,
    sub_agents=[
        news_agent,
        fundamental_agent,
        technical_agent,
        expert_agent,
        risk_agent,
    ],
)
