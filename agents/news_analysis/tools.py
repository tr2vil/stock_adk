"""
News Analysis Tools - ADK Agent Tools
한국/미국 주식 뉴스 수집을 위한 도구 함수
"""
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup


async def fetch_korean_stock_news(stock_name: str) -> dict:
    """네이버 뉴스에서 한국 주식 종목의 최신 뉴스를 수집합니다.

    한국 주식 종목명(예: 삼성전자, 현대차, SK하이닉스)으로 검색하여
    최근 뉴스 기사 제목, 링크, 요약을 반환합니다.

    Args:
        stock_name: 한국 주식 종목명 (예: 삼성전자, 현대차, LG에너지솔루션)

    Returns:
        dict: 수집 결과. status, stock_name, market, news_items 포함.
    """
    encoded_query = urllib.parse.quote(f"{stock_name} 주식")
    url = f"https://m.search.naver.com/search.naver?where=m_news&query={encoded_query}&sm=mtb_opt&sort=1"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers, timeout=15.0)
            if response.status_code != 200:
                return {
                    "status": "error",
                    "stock_name": stock_name,
                    "market": "KR",
                    "error": f"HTTP {response.status_code}",
                    "news_items": [],
                }

            soup = BeautifulSoup(response.text, "html.parser")
            news_items = []

            # 전략 1: 뉴스 제목 링크를 직접 탐색 (가장 정확)
            title_links = soup.select("a.news_tit")
            if title_links:
                for a_tag in title_links:
                    title = a_tag.get_text(strip=True)
                    href = a_tag.get("href", "")
                    if title and href.startswith("http"):
                        parent = a_tag.find_parent(
                            class_=["news_wrap", "bx", "news_area"]
                        )
                        desc = ""
                        if parent:
                            desc_el = parent.select_one(
                                ".news_dsc, .api_txt_lines, .dsc_wrap"
                            )
                            if desc_el:
                                desc = desc_el.get_text(strip=True)[:200]
                        news_items.append({
                            "title": title,
                            "link": href,
                            "description": desc or title,
                        })
                    if len(news_items) >= 7:
                        break

            # 전략 2: 외부 링크를 가진 뉴스 컨테이너 탐색
            if not news_items:
                seen_urls = set()
                skip_domains = [
                    "media.naver.com", "naver.com/search",
                    "search.naver.com", "naver.com/channel",
                ]
                skip_texts = [
                    "관련도순", "최신순", "전체", "옵션", "기간",
                    "언론사 선정", "구독하세요", "네이버 메인",
                ]
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "")
                    text = a_tag.get_text(strip=True)
                    if (
                        href.startswith("http")
                        and href not in seen_urls
                        and not any(d in href for d in skip_domains)
                        and len(text) > 15
                        and not any(s in text for s in skip_texts)
                    ):
                        seen_urls.add(href)
                        news_items.append({
                            "title": text[:150],
                            "link": href,
                            "description": text[:200],
                        })
                    if len(news_items) >= 7:
                        break

            return {
                "status": "success",
                "stock_name": stock_name,
                "market": "KR",
                "news_count": len(news_items),
                "news_items": news_items,
            }

        except Exception as e:
            return {
                "status": "error",
                "stock_name": stock_name,
                "market": "KR",
                "error": str(e),
                "news_items": [],
            }


async def fetch_us_stock_news(stock_name: str) -> dict:
    """Fetches recent US stock news from Google News RSS feed.

    Use this tool when the user asks about US stocks or uses
    English stock names/tickers like AAPL, TSLA, NVIDIA, MSFT, etc.

    Args:
        stock_name: US stock name or ticker symbol (e.g., AAPL, Tesla, NVIDIA, MSFT)

    Returns:
        dict: Collection result with status, stock_name, market, and news_items.
    """
    encoded_query = urllib.parse.quote(f"{stock_name} stock")
    url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers, timeout=15.0)
            if response.status_code != 200:
                return {
                    "status": "error",
                    "stock_name": stock_name,
                    "market": "US",
                    "error": f"HTTP {response.status_code}",
                    "news_items": [],
                }

            root = ET.fromstring(response.text)
            news_items = []

            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    pub_date_el = item.find("pubDate")
                    description_el = item.find("description")

                    if title_el is not None and title_el.text:
                        # description에서 HTML 태그 제거
                        desc_text = ""
                        if description_el is not None and description_el.text:
                            desc_soup = BeautifulSoup(
                                description_el.text, "html.parser"
                            )
                            desc_text = desc_soup.get_text(strip=True)[:200]

                        news_items.append({
                            "title": title_el.text,
                            "link": link_el.text if link_el is not None else "",
                            "published": pub_date_el.text if pub_date_el is not None else "",
                            "description": desc_text,
                        })

                    if len(news_items) >= 7:
                        break

            return {
                "status": "success",
                "stock_name": stock_name,
                "market": "US",
                "news_count": len(news_items),
                "news_items": news_items,
            }

        except Exception as e:
            return {
                "status": "error",
                "stock_name": stock_name,
                "market": "US",
                "error": str(e),
                "news_items": [],
            }
