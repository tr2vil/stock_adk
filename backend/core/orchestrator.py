import os
from typing import List, Dict, Any
import vertexai
from vertexai.generative_models import GenerativeModel
from agents.news_analysis.agent import NewsAnalysisAgent
from utils.vertex_ai_auth import init_vertex_ai
from dotenv import load_dotenv

load_dotenv()

class Orchestrator:
    def __init__(self):
        init_vertex_ai()
        self.model = GenerativeModel("gemini-2.5-flash")
        self.news_agent = NewsAnalysisAgent()

    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """사용자의 질문을 분석하여 적절한 에이전트를 호출합니다."""

        # 1. 인텐트 분석 루틴 (LLM 활용)
        intent_prompt = f"""
        사용자의 질문: "{user_query}"

        위 질문이 다음 중 어떤 작업에 해당하는지 판단하세요:
        - NEWS: 특정 종목의 뉴스 요약 및 분석 요청
        - FINANCIAL: 재무제표 분석 요청
        - PREDICTION: 주가 예측 요청
        - UNKNOWN: 그 외

        대상 종목명(또는 티커)이 있다면 함께 추출하세요.

        JSON 형식으로 응답하세요:
        {{
            "intent": "NEWS | FINANCIAL | PREDICTION | UNKNOWN",
            "stock_name": "종목명 또는 null"
        }}
        """

        response = self.model.generate_content(intent_prompt)
        try:
            import json
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            intent_data = json.loads(content)
        except:
            intent_data = {"intent": "UNKNOWN", "stock_name": None}

        # 2. 인텐트에 따른 에이전트 실행
        if intent_data["intent"] == "NEWS" and intent_data["stock_name"]:
            result = await self.news_agent.run(intent_data["stock_name"])
            return {
                "type": "A2UI_CARD",
                "agent": "NewsAnalysis",
                "stock": intent_data["stock_name"],
                "data": result
            }

        # 기본 응답 (아직 다른 에이전트가 개발되지 않은 경우)
        return {
            "type": "TEXT",
            "message": f"'{user_query}'에 대한 처리를 준비 중입니다. 현재 뉴스 분석 가능합니다. (예: 삼성전자 뉴스 요약해줘)"
        }
