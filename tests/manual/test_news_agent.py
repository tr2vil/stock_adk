"""
News Analysis Agent - ADK 로컬 테스트 스크립트

사용법:
    python tests/manual/test_news_agent.py                    # 기본 테스트 (삼성전자)
    python tests/manual/test_news_agent.py 현대차              # 한국 종목
    python tests/manual/test_news_agent.py AAPL               # 미국 종목
    python tests/manual/test_news_agent.py "SK하이닉스" TSLA   # 복수 종목
"""
import os
import sys
import asyncio

# tests/manual/ 에서 실행해도 프로젝트 루트 패키지를 import 할 수 있도록
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from sub_agents.news_agent.agent import root_agent


async def test_agent(query: str):
    """ADK Runner로 에이전트 테스트"""
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="stock_news_test", user_id="test_user",
    )
    runner = Runner(
        agent=root_agent,
        app_name="stock_news_test",
        session_service=session_service,
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=query)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text

    print("\n[Agent Response]")
    print(final_response)
    print("=" * 60)
    return final_response


async def test_tool_directly():
    """도구 함수 직접 테스트 (에이전트 없이)"""
    from sub_agents.news_agent.tools import (
        fetch_korean_stock_news,
        fetch_us_stock_news,
    )

    print("\n--- Tool Direct Test: Korean News ---")
    kr_result = await fetch_korean_stock_news("삼성전자")
    print(f"Status: {kr_result['status']}, Count: {kr_result.get('news_count', 0)}")
    for item in kr_result.get("news_items", [])[:3]:
        print(f"  - {item['title']}")

    print("\n--- Tool Direct Test: US News ---")
    us_result = await fetch_us_stock_news("AAPL")
    print(f"Status: {us_result['status']}, Count: {us_result.get('news_count', 0)}")
    for item in us_result.get("news_items", [])[:3]:
        print(f"  - {item['title']}")


async def main():
    args = sys.argv[1:]

    # 도구 직접 테스트
    print("[1] Testing tools directly...")
    await test_tool_directly()

    # 에이전트 테스트
    print("\n[2] Testing ADK Agent...")
    if args:
        for stock in args:
            query = f"{stock} 주식 뉴스 분석해줘"
            await test_agent(query)
    else:
        await test_agent("삼성전자 주식 뉴스 분석해줘")


if __name__ == "__main__":
    asyncio.run(main())
