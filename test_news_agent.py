"""
뉴스 분석 에이전트 테스트 스크립트

사용법:
    python test_news_agent.py [종목명]

예시:
    python test_news_agent.py 삼성전자
    python test_news_agent.py 현대차
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.news_analysis.agent import NewsAnalysisAgent
from utils.vertex_ai_auth import init_vertex_ai


async def test_news_agent(stock_name: str):
    """뉴스 분석 에이전트 테스트"""
    print("=" * 60)
    print(f"뉴스 분석 에이전트 테스트: {stock_name}")
    print("=" * 60)

    # Vertex AI 초기화
    print("\n[1] Vertex AI 초기화 중...")
    try:
        init_vertex_ai()
        print("✅ Vertex AI 초기화 성공")
    except Exception as e:
        print(f"❌ Vertex AI 초기화 실패: {e}")
        return

    # 에이전트 생성
    print("\n[2] News Analysis Agent 생성 중...")
    try:
        agent = NewsAnalysisAgent()
        print("✅ 에이전트 생성 성공")
    except Exception as e:
        print(f"❌ 에이전트 생성 실패: {e}")
        return

    # 뉴스 수집
    print(f"\n[3] '{stock_name}' 뉴스 수집 중...")
    try:
        news_list = await agent.fetch_news(stock_name)
        print(f"✅ 뉴스 수집 완료: {len(news_list)}개 발견")

        if news_list:
            print("\n수집된 뉴스 샘플:")
            for i, news in enumerate(news_list[:3], 1):
                print(f"  {i}. {news.get('title', 'N/A')[:50]}...")
        else:
            print("⚠️ 수집된 뉴스가 없습니다.")
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        return

    # AI 분석
    print(f"\n[4] AI 분석 중...")
    try:
        analysis = await agent.analyze_and_summarize(stock_name, news_list)
        print("✅ AI 분석 완료")

        print("\n" + "=" * 60)
        print("분석 결과")
        print("=" * 60)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ AI 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print("사용법: python test_news_agent.py [종목명]")
        print("예시: python test_news_agent.py 삼성전자")
        sys.exit(1)

    stock_name = sys.argv[1]

    # 환경 변수 확인
    required_vars = ["GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ 필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        print("   .env 파일을 확인해주세요.")
        sys.exit(1)

    # 비동기 실행
    asyncio.run(test_news_agent(stock_name))


if __name__ == "__main__":
    main()
