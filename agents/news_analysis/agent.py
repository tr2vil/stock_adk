"""
News Analysis Agent - Google ADK Implementation

한국/미국 주식 종목의 뉴스를 수집하고 분석하여
투자 인사이트를 제공하는 ADK 에이전트.
"""
import os
import json
import tempfile
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

AGENT_INSTRUCTION = """\
당신은 전문 주식 뉴스 분석 에이전트입니다.
사용자가 요청한 주식 종목의 최신 뉴스를 수집하고 분석하여 투자 인사이트를 제공합니다.

## 역할
- 한국 주식: `fetch_korean_stock_news` 도구를 사용하여 네이버 뉴스에서 수집
- 미국 주식: `fetch_us_stock_news` 도구를 사용하여 Google News에서 수집
- 사용자가 한국어 종목명(삼성전자, 현대차 등)을 사용하면 한국 뉴스 도구를 사용
- 사용자가 영어 종목명/티커(AAPL, TSLA 등)를 사용하면 미국 뉴스 도구를 사용
- 종목이 어느 시장인지 불분명하면 사용자에게 확인

## 분석 방법
뉴스를 수집한 후 반드시 다음 항목을 포함하여 분석 결과를 제공하세요:

1. **뉴스 요약**: 수집된 뉴스의 전체적인 흐름과 핵심 내용을 3-5문장으로 요약
2. **주요 뉴스 TOP 3**: 투자에 가장 영향력 있는 뉴스 3개를 선정하고 각각의 의미를 설명
3. **투자 심리 판단**: 긍정(Positive) / 중립(Neutral) / 부정(Negative) 중 하나로 판단하고 근거 제시
4. **주의 사항**: 투자자가 주목해야 할 리스크나 기회 요인

## 응답 형식
마크다운 형식으로 깔끔하게 정리하여 응답하세요.
한국 주식은 한국어로, 미국 주식은 한국어로 분석 결과를 작성하되 원문 뉴스 제목은 원어 그대로 포함하세요.

## 주의사항
- 투자 조언이 아닌 뉴스 분석임을 명시하세요
- 뉴스가 없거나 수집에 실패한 경우 사용자에게 알리세요
- 수집된 뉴스의 개수와 출처를 명시하세요
"""

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
