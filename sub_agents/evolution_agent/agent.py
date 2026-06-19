"""
Evolution Agent - Google ADK Implementation (자가진화 핵심 신규 Agent)

매매 성과 통계 + 현재 전략을 입력받아 strategy.yaml 파라미터 조정안을 JSON으로 제안한다.
도구 없이 텍스트→JSON 추론만 수행하는 경량 단발 LLM (extract_agent와 동일 패턴).
가드레일 재검증은 shared.quant.guardrails 에서 결정론적으로 수행된다.
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
from .prompt import EVOLUTION_INSTRUCTION
from shared.redis_client import seed_defaults, get_prompt_safe
from shared.model_factory import resolve_model

MODEL = os.getenv("EVOLUTION_AGENT_MODEL", "gemini-2.5-flash")

seed_defaults({"prompt:evolution_agent": EVOLUTION_INSTRUCTION})
_instruction = get_prompt_safe("evolution_agent", EVOLUTION_INSTRUCTION)

root_agent = Agent(
    name="evolution_agent",
    model=resolve_model(MODEL),
    description="매매 성과를 분석해 퀀트 전략 파라미터 개선안을 제안하는 자가진화 에이전트",
    instruction=_instruction,
)
