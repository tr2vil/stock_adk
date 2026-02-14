"""
Trading Orchestrator - Root Agent with Parallel Sub-Agent Tool
analyze_all_agents 도구를 통해 5개의 sub-agent를 동시에 호출하여 종합 분석 수행
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
from .prompt import ORCHESTRATOR_INSTRUCTION
from .tools import analyze_all_agents
from shared.redis_client import seed_defaults, get_prompt_safe

MODEL = os.getenv("ORCHESTRATOR_MODEL", "gemini-2.5-pro")

# Seed default prompt into Redis (only if key does not exist)
seed_defaults({"prompt:orchestrator": ORCHESTRATOR_INSTRUCTION})
_instruction = get_prompt_safe("orchestrator", ORCHESTRATOR_INSTRUCTION)

root_agent = Agent(
    name="trading_orchestrator",
    model=MODEL,
    description="주식 자동매매 시스템 오케스트레이터 - 5개 전문 에이전트를 동시에 조회하여 종합 분석 및 매매 결정",
    instruction=_instruction,
    tools=[analyze_all_agents],
)
