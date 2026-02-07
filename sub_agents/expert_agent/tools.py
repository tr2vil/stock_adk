"""
Expert Agent Tools - 전문가 신호 수집 도구
애널리스트 리포트, 기관/외국인 수급, 내부자 거래 데이터 수집
"""
import yfinance as yf
from shared.ticker_utils import lookup_ticker as _lookup_ticker


async def lookup_ticker(query: str) -> dict:
    """종목명 또는 티커를 조회하여 정확한 티커 정보를 반환합니다.

    한글 종목명(테슬라, 삼성전자), 영문 회사명(Tesla, Apple),
    또는 티커(AAPL, 005930)를 입력하면 해당 종목의 정보를 반환합니다.

    다른 도구를 호출하기 전에 이 도구를 먼저 사용하여 정확한 티커를 확인하세요.

    Args:
        query: 종목명 또는 티커 (예: "테슬라", "Tesla", "TSLA", "삼성전자", "005930")

    Returns:
        dict: 조회 결과. ticker, market, company_name 포함.
              예: {"status": "success", "ticker": "TSLA", "market": "US", "company_name": "Tesla, Inc."}
    """
    return _lookup_ticker(query)


async def collect_analyst_ratings(ticker: str, market: str = "US") -> dict:
    """애널리스트 목표가 및 투자의견을 수집합니다.

    증권사 애널리스트들의 컨센서스 투자의견과 목표가 정보를 수집합니다.

    Args:
        ticker: 종목코드 (예: "AAPL", "005930.KS")
        market: "US" 또는 "KR"

    Returns:
        dict: 애널리스트 컨센서스 정보. consensus_rating, target_price_avg,
              target_price_range, analyst_count, recommendations 포함.
    """
    try:
        # 티커 심볼 처리
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            if ticker.isdigit() and len(ticker) == 6:
                ticker = f"{ticker}.KS"

        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return {
                "status": "error",
                "ticker": ticker,
                "market": market,
                "error": f"종목 정보를 찾을 수 없습니다: {ticker}",
            }

        # 애널리스트 추천 정보
        recommendation_key = info.get("recommendationKey", "hold")
        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")
        target_mean = info.get("targetMeanPrice")
        target_median = info.get("targetMedianPrice")
        analyst_count = info.get("numberOfAnalystOpinions", 0)

        # recommendationKey를 SignalStrength로 매핑
        rating_map = {
            "strong_buy": "strong_buy",
            "buy": "buy",
            "hold": "hold",
            "sell": "sell",
            "strong_sell": "strong_sell",
            "underperform": "sell",
            "outperform": "buy",
        }
        consensus_rating = rating_map.get(recommendation_key.lower(), "hold")

        # 신뢰도 계산 (애널리스트 수 기반)
        if analyst_count >= 20:
            confidence = 0.9
        elif analyst_count >= 10:
            confidence = 0.7
        elif analyst_count >= 5:
            confidence = 0.5
        else:
            confidence = 0.3

        return {
            "status": "success",
            "ticker": ticker,
            "market": market,
            "consensus_rating": consensus_rating,
            "recommendation_key": recommendation_key,
            "target_price_avg": target_mean or target_median,
            "target_price_range": [target_low, target_high] if target_low and target_high else None,
            "analyst_count": analyst_count,
            "current_price": info.get("regularMarketPrice"),
            "confidence": confidence,
        }

    except Exception as e:
        return {
            "status": "error",
            "ticker": ticker,
            "market": market,
            "error": str(e),
        }


async def analyze_institutional_flow(ticker: str, market: str = "US") -> dict:
    """기관/외국인 매매 동향을 분석합니다.

    기관투자자와 외국인의 순매수/순매도 동향 및 보유 현황을 분석합니다.

    Args:
        ticker: 종목코드 (예: "AAPL", "005930.KS")
        market: "US" 또는 "KR"

    Returns:
        dict: 기관/외국인 수급 정보. institutional_flow, major_holders,
              insider_ownership 포함.
    """
    try:
        # 티커 심볼 처리
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            if ticker.isdigit() and len(ticker) == 6:
                ticker = f"{ticker}.KS"

        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return {
                "status": "error",
                "ticker": ticker,
                "market": market,
                "error": f"종목 정보를 찾을 수 없습니다: {ticker}",
            }

        # 기관 보유 정보
        held_percent_insiders = info.get("heldPercentInsiders", 0)
        held_percent_institutions = info.get("heldPercentInstitutions", 0)

        # 주요 보유자 정보 시도
        try:
            major_holders = stock.major_holders
            if major_holders is not None and not major_holders.empty:
                major_holders_data = major_holders.to_dict()
            else:
                major_holders_data = {}
        except Exception:
            major_holders_data = {}

        return {
            "status": "success",
            "ticker": ticker,
            "market": market,
            "institutional_flow": 0,  # TODO: 실제 순매수 데이터 구현 필요
            "held_percent_insiders": held_percent_insiders,
            "held_percent_institutions": held_percent_institutions,
            "major_holders": major_holders_data,
            "message": "Note: Detailed flow data requires additional data sources for KR market",
        }

    except Exception as e:
        return {
            "status": "error",
            "ticker": ticker,
            "market": market,
            "error": str(e),
        }


async def check_insider_trading(ticker: str, market: str = "US") -> dict:
    """내부자 거래(대량보유 변동)를 확인합니다.

    임원, 대주주 등 내부자의 최근 매매 내역을 조회합니다.

    Args:
        ticker: 종목코드 (예: "AAPL", "005930.KS")
        market: "US" 또는 "KR"

    Returns:
        dict: 내부자 거래 정보. insider_transactions, recent_activity 포함.
    """
    try:
        # 티커 심볼 처리
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            if ticker.isdigit() and len(ticker) == 6:
                ticker = f"{ticker}.KS"

        stock = yf.Ticker(ticker)

        # 내부자 거래 정보 시도
        try:
            insider_transactions = stock.insider_transactions
            if insider_transactions is not None and not insider_transactions.empty:
                # 최근 10건만 추출
                recent = insider_transactions.head(10)
                transactions = recent.to_dict("records")
            else:
                transactions = []
        except Exception:
            transactions = []

        # 내부자 보유 정보
        try:
            insider_holders = stock.insider_holders
            if insider_holders is not None and not insider_holders.empty:
                holders = insider_holders.to_dict("records")
            else:
                holders = []
        except Exception:
            holders = []

        return {
            "status": "success",
            "ticker": ticker,
            "market": market,
            "insider_transactions": transactions,
            "insider_holders": holders,
            "transaction_count": len(transactions),
            "message": "Note: KR market insider data requires DART API integration",
        }

    except Exception as e:
        return {
            "status": "error",
            "ticker": ticker,
            "market": market,
            "error": str(e),
        }
