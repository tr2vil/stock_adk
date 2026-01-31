"""
Balance Sheet Agent - Google ADK Implementation

한국/미국 주식 종목의 재무제표를 수집하고 분석하여
단기/중기/장기 투자 적합성을 판단하는 ADK 에이전트.
"""
import os
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()

_google_key = os.getenv("GOOGLE_KEY")
if _google_key and _google_key.strip().startswith("{"):
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        _cred_dir = os.path.join(tempfile.gettempdir(), "stock_adk")
        os.makedirs(_cred_dir, exist_ok=True)
        _cred_path = os.path.join(_cred_dir, "service_account.json")
        with open(_cred_path, "w", encoding="utf-8") as f:
            json.dump(json.loads(_google_key), f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _cred_path

from google.adk.agents import Agent

from .prompt import AGENT_INSTRUCTION
from .tools import fetch_korean_financials, fetch_us_financials

MODEL = os.getenv("BALANCE_SHEET_AGENT_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="balance_sheet_agent",
    model=MODEL,
    description=(
        "주식 종목의 재무제표(대차대조표, 손익계산서, 현금흐름표)를 수집하고 "
        "단기/중기/장기 관점에서 재무 건전성과 투자 적합성을 분석하는 에이전트. "
        "한국(yfinance KRX) 및 미국(yfinance US) 주식 모두 지원합니다."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[fetch_korean_financials, fetch_us_financials],
)
