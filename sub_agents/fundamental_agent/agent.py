"""
Fundamental Agent - Google ADK Implementation
재무제표 분석 및 밸류에이션 평가 에이전트
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
from .prompt import AGENT_INSTRUCTION
from .tools import fetch_korean_financials, fetch_us_financials
from shared.redis_client import seed_defaults, get_prompt_safe

MODEL = os.getenv("FUNDAMENTAL_AGENT_MODEL", "gemini-2.5-flash")

seed_defaults({"prompt:fundamental_agent": AGENT_INSTRUCTION})
_instruction = get_prompt_safe("fundamental_agent", AGENT_INSTRUCTION)

root_agent = Agent(
    name="fundamental_agent",
    model=MODEL,
    description="재무제표 분석 및 밸류에이션 평가 에이전트",
    instruction=_instruction,
    tools=[fetch_korean_financials, fetch_us_financials],
)
