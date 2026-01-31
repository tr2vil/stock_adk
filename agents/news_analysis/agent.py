"""
News Analysis Agent - Google ADK Implementation

한국/미국 주식 종목의 뉴스를 수집하고 분석하여
투자 인사이트를 제공하는 ADK 에이전트.
"""
import os
import json
import tempfile
from .prompt import AGENT_INSTRUCTION
from dotenv import load_dotenv

load_dotenv()

# GOOGLE_KEY 환경변수(JSON 문자열)를 ADK가 인식할 수 있도록
# 임시 파일에 저장하고 GOOGLE_APPLICATION_CREDENTIALS로 설정
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

from .tools import fetch_korean_stock_news, fetch_us_stock_news

MODEL = os.getenv("NEWS_AGENT_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="news_analysis_agent",
    model=MODEL,
    description=(
        "주식 뉴스를 수집하고 분석하여 투자 인사이트를 제공하는 에이전트. "
        "한국(네이버 뉴스) 및 미국(Google News) 주식 모두 지원합니다."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[fetch_korean_stock_news, fetch_us_stock_news],
)
