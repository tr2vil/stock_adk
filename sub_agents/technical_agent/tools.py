"""
Technical Agent Tools - 차트 기술적 분석 도구
pandas-ta를 사용한 기술적 지표 계산
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


async def analyze_technical(ticker: str, market: str = "US") -> dict:
    """차트 기술적 분석을 수행합니다.

    종목의 가격 데이터를 수집하고 주요 기술적 지표를 계산합니다.
    RSI, MACD, 이동평균선, 볼린저 밴드 등을 분석하여 매매 신호를 제공합니다.

    Args:
        ticker: 종목코드 (예: "AAPL", "005930.KS")
        market: "US" 또는 "KR"

    Returns:
        dict: 기술적 분석 결과. technical_signal, trend_direction,
              key_levels, rsi, macd, patterns, confidence 포함.
    """
    try:
        # 티커 심볼 처리
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            if ticker.isdigit() and len(ticker) == 6:
                ticker = f"{ticker}.KS"

        # 가격 데이터 수집 (1년 일봉)
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty:
            return {
                "status": "error",
                "ticker": ticker,
                "market": market,
                "error": f"가격 데이터를 찾을 수 없습니다: {ticker}",
            }

        # 기본 가격 정보
        current_price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price

        # 간단한 기술적 지표 계산 (pandas-ta 없이 기본 계산)
        # SMA 계산
        sma_20 = float(hist["Close"].tail(20).mean())
        sma_50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else None
        sma_200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else None

        # RSI 계산 (14일)
        delta = hist["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float(100 - (100 / (1 + rs.iloc[-1]))) if not loss.iloc[-1] == 0 else 50.0

        # 추세 판단
        if sma_50 and sma_200:
            if current_price > sma_50 > sma_200:
                trend = "up"
            elif current_price < sma_50 < sma_200:
                trend = "down"
            else:
                trend = "neutral"
        else:
            trend = "neutral"

        # 매매 신호 판단
        if rsi < 30 and current_price > sma_20:
            signal = "strong_buy"
            confidence = 0.8
        elif rsi < 40 and current_price > sma_20:
            signal = "buy"
            confidence = 0.6
        elif rsi > 70 and current_price < sma_20:
            signal = "strong_sell"
            confidence = 0.8
        elif rsi > 60 and current_price < sma_20:
            signal = "sell"
            confidence = 0.6
        else:
            signal = "hold"
            confidence = 0.5

        # 지지/저항 레벨 (최근 고점/저점 기반)
        recent_high = float(hist["High"].tail(20).max())
        recent_low = float(hist["Low"].tail(20).min())

        return {
            "status": "success",
            "ticker": ticker,
            "market": market,
            "current_price": current_price,
            "prev_close": prev_close,
            "change_pct": round((current_price - prev_close) / prev_close * 100, 2),
            "technical_signal": signal,
            "trend_direction": trend,
            "key_levels": {
                "support": [round(recent_low, 2)],
                "resistance": [round(recent_high, 2)],
            },
            "indicators": {
                "rsi_14": round(rsi, 2),
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2) if sma_50 else None,
                "sma_200": round(sma_200, 2) if sma_200 else None,
            },
            "patterns": [],  # TODO: 패턴 인식 구현
            "confidence": confidence,
        }

    except Exception as e:
        return {
            "status": "error",
            "ticker": ticker,
            "market": market,
            "error": str(e),
        }


async def detect_patterns(ticker: str, market: str = "US") -> dict:
    """캔들스틱 패턴을 감지합니다.

    종목의 최근 가격 데이터를 분석하여 주요 캔들스틱 패턴을 식별합니다.

    Args:
        ticker: 종목코드 (예: "AAPL", "005930.KS")
        market: "US" 또는 "KR"

    Returns:
        dict: 감지된 패턴 목록. patterns, pattern_signals 포함.
    """
    # TODO: TA-Lib 또는 pandas-ta로 패턴 인식 구현
    return {
        "status": "stub",
        "ticker": ticker,
        "market": market,
        "message": "Pattern detection not yet implemented",
        "patterns": [],
        "pattern_signals": [],
    }
