import os
import datetime
from typing import List, Dict
import vertexai
from vertexai.generative_models import GenerativeModel
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

class NewsAnalysisAgent:
    def __init__(self):
        # Initialization is handled by the orchestrator or utility
        self.model = GenerativeModel("gemini-2.5-flash")
        print(f"Agent initialized with model: {self.model._model_name}")

    async def fetch_news(self, stock_name: str) -> List[Dict]:
        """네이버 뉴스 검색을 통해 지정된 종목의 최근 뉴스를 수집합니다."""
        # 실제 환경에서는 더 정교한 뉴스 API나 라이브러리를 사용하지만,
        # 데모를 위해 네이버 뉴스 검색결과를 스크래핑하는 예시입니다.
        import urllib.parse
        encoded_query = urllib.parse.quote(stock_name + " 주식")
        # Use mobile version which is often easier to scrape
        url = f"https://m.search.naver.com/search.naver?where=m_news&query={encoded_query}&sm=mtb_opt&sort=1"

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            print(f"Requesting URL: {url}")
            response = await client.get(url, headers=headers)
            print(f"Response status: {response.status_code}, Length: {len(response.text)}")
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []

            # 1. Try common containers
            containers = soup.select(".news_item") or soup.select("li.bx") or soup.select(".bx")
            if containers:
                for i, item in enumerate(containers):
                    if any(ad in str(item) for ad in ['ad_head', 'sp_ad']): continue

                    # Search for any link with reasonable length
                    links = item.find_all("a")
                    for a in links:
                        text = a.get_text(strip=True)
                        href = a.get('href', '')
                        if len(text) > 15 and href.startswith('http'):
                            news_items.append({
                                "title": text,
                                "link": href,
                                "description": item.get_text(strip=True)[:100]
                            })
                            print(f"Extracted: {text[:20]}...")
                            break
                    if len(news_items) >= 10: break

            # 2. LLM Fallback: If still nothing, let Gemini try to parse
            if not news_items:
                print("Manual scraping failed. Attempting LLM fallback...")
                llm_prompt = f"다음 HTML에서 주요 뉴스 제목과 링크를 5개만 추출해 JSON 배열로 응답해줘. [{{'title': '...', 'link': '...', 'description': '...'}}, ...]\n\nHTML:\n{response.text[:15000]}"
                try:
                    llm_res = self.model.generate_content(llm_prompt)
                    res_text = llm_res.text
                    if "```json" in res_text:
                        res_text = res_text.split("```json")[1].split("```")[0].strip()
                    elif "[" in res_text:
                        res_text = res_text[res_text.find("["):res_text.rfind("]")+1]

                    import json
                    news_items = json.loads(res_text)
                    print(f"LLM extracted {len(news_items)} items.")
                except Exception as e:
                    print(f"LLM Fallback Error: {e}")

        print(f"Total news_items: {len(news_items)}")
        return news_items

    async def analyze_and_summarize(self, stock_name: str, news_list: List[Dict]) -> Dict:
        """수집된 뉴스 중 중요한 내용을 선별하고 요약합니다."""
        print(f"Analyzing {len(news_list)} news items for {stock_name}...")
        if not news_list:
            return {"summary": "최근 1주일간 수집된 뉴스가 없습니다.", "important_news": []}

        news_text = "\n".join([f"- 제목: {n['title']}\n  내용: {n['description']}" for n in news_list])

        prompt = f"""
        당신은 전문 주식 분석가입니다.
        다음은 최근 1주일간의 '{stock_name}' 관련 뉴스 목록입니다.

        {news_text}

        위 뉴스들 중에서 투자자가 반드시 알아야 할 '중요한 뉴스' 3가지를 선정하고,
        전체적인 흐름을 요약해 주세요.

        응답은 반드시 다음 JSON 형식을 따라주세요:
        {{
          "summary": "전체적인 뉴스 요약 문구",
          "important_news": [
            {{
              "title": "뉴스 제목",
              "reason": "선정 이유 및 주요 내용 요약"
            }}
          ],
          "sentiment": "긍정/중립/부정 중 하나"
        }}
        """

        print("Sending prompt to Gemini...")
        response = self.model.generate_content(prompt)
        print("Received response from Gemini.")
        try:
            # JSON만 추출 (Gemini가 마크다운 등의 텍스트를 섞어 보낼 수 있으므로)
            import json
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            return {
                "summary": "요약 중 오류가 발생했습니다.",
                "important_news": [],
                "error": str(e)
            }

    async def run(self, stock_name: str):
        """에이전트 실행 메인 로직"""
        news = await self.fetch_news(stock_name)
        analysis = await self.analyze_and_summarize(stock_name, news)
        return analysis
