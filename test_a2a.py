"""
A2A Integration Test - News Analysis Agent

뉴스 분석 에이전트의 A2A 서버를 시작한 후,
RemoteA2aAgent를 통해 원격으로 통신하는 테스트.

사용법:
    1. 먼저 A2A 서버 실행:
       python -m agents.news_analysis.a2a_server

    2. 이 테스트 실행:
       python test_a2a.py
"""
import asyncio

from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

A2A_AGENT_URL = "http://localhost:8001"


async def test_a2a_flow():
    print("=" * 60)
    print("A2A Integration Test")
    print("=" * 60)

    # 1. RemoteA2aAgent로 원격 뉴스 에이전트 연결
    print("\n[1] Connecting to remote News Analysis Agent...")
    remote_news_agent = RemoteA2aAgent(
        name="news_analysis_agent",
        description="Remote agent that analyzes stock news for KR/US markets.",
        agent_card=f"{A2A_AGENT_URL}/.well-known/agent.json",
    )
    print(f"    Connected to {A2A_AGENT_URL}")

    # 2. Orchestrator 에이전트 생성 (remote agent를 sub_agent로)
    print("[2] Creating orchestrator with remote sub-agent...")
    orchestrator = Agent(
        name="orchestrator",
        model="gemini-2.5-flash",
        instruction=(
            "You coordinate stock analysis tasks. "
            "Delegate all news analysis requests to news_analysis_agent."
        ),
        sub_agents=[remote_news_agent],
    )

    # 3. 테스트 쿼리 실행
    runner = InMemoryRunner(agent=orchestrator, app_name="a2a_test")

    queries = [
        "현대차 주식 뉴스 분석해줘",
        "Analyze TSLA stock news",
    ]

    for query in queries:
        print(f"\n[3] Query: '{query}'")
        user_message = types.Content(
            role="user",
            parts=[types.Part(text=query)],
        )

        final_response = ""
        async for event in runner.run_async(
            user_id="test_user",
            session_id=f"test_{query[:10]}",
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = event.content.parts[0].text

        if final_response:
            print(f"    Response (first 200 chars): {final_response[:200]}...")
            print("    [OK]")
        else:
            print("    [WARN] Empty response")

    print("\n" + "=" * 60)
    print("A2A Integration Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_a2a_flow())
