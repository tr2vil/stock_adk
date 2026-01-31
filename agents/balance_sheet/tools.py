"""
Balance Sheet Agent Tools - 재무제표 수집 도구
yfinance를 사용하여 한국/미국 주식의 재무제표 데이터 수집
"""
import math
import re
import yfinance as yf


# 주요 한국 종목 한글명 → 영문 검색어 매핑 (yfinance Search용)
_KR_NAME_MAP = {
    "삼성전자": "Samsung Electronics",
    "SK하이닉스": "SK Hynix",
    "현대차": "Hyundai Motor",
    "현대자동차": "Hyundai Motor",
    "LG에너지솔루션": "LG Energy Solution",
    "기아": "Kia Corp",
    "셀트리온": "Celltrion",
    "KB금융": "KB Financial",
    "신한지주": "Shinhan Financial",
    "포스코홀딩스": "POSCO Holdings",
    "NAVER": "Naver Corp",
    "네이버": "Naver Corp",
    "카카오": "Kakao Corp",
    "LG전자": "LG Electronics",
    "삼성SDI": "Samsung SDI",
    "삼성바이오로직스": "Samsung Biologics",
    "현대모비스": "Hyundai Mobis",
    "한국전력": "Korea Electric Power",
    "SK이노베이션": "SK Innovation",
    "삼성물산": "Samsung C&T",
    "SK텔레콤": "SK Telecom",
    "KT": "KT Corp",
    "하나금융지주": "Hana Financial",
    "우리금융지주": "Woori Financial",
    "LG화학": "LG Chem",
    "한화에어로스페이스": "Hanwha Aerospace",
    "크래프톤": "Krafton",
    "두산에너빌리티": "Doosan Enerbility",
}


def _resolve_korean_stock_code(stock_name: str) -> str:
    """한국어 종목명을 yfinance 티커(예: 005930.KS)로 변환.

    Returns:
        str: yfinance 티커 심볼. 실패 시 빈 문자열.
    """
    cleaned = stock_name.strip()

    # 이미 코드 형식인 경우 (숫자 6자리)
    if cleaned.isdigit() and len(cleaned) == 6:
        return f"{cleaned}.KS"

    # 이미 yfinance 형식인 경우
    if re.match(r"^\d{6}\.(KS|KQ)$", cleaned):
        return cleaned

    # 매핑에서 영문명 조회 후 yfinance Search
    en_name = _KR_NAME_MAP.get(cleaned, cleaned)
    try:
        search = yf.Search(en_name, max_results=5)
        for quote in search.quotes:
            symbol = quote.get("symbol", "")
            if symbol.endswith((".KS", ".KQ")):
                return symbol
    except Exception:
        pass

    return ""


def _safe_float(value) -> float | None:
    """NaN/Inf를 None으로 변환 (JSON 직렬화 안전)."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


# 분석에 핵심적인 항목만 선별 (LLM 토큰 절약)
_KEY_BALANCE_SHEET = [
    "Total Assets", "Total Liabilities Net Minority Interest",
    "Stockholders Equity", "Current Assets", "Current Liabilities",
    "Cash And Cash Equivalents", "Total Debt", "Current Debt",
    "Long Term Debt", "Net Debt", "Inventory",
    "Accounts Receivable", "Accounts Payable",
    "Retained Earnings", "Common Stock Equity",
]
_KEY_INCOME_STMT = [
    "Total Revenue", "Cost Of Revenue", "Gross Profit",
    "Operating Income", "Net Income", "EBITDA",
    "Operating Expense", "Interest Expense",
    "Tax Provision", "Diluted EPS",
]
_KEY_CASH_FLOW = [
    "Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
    "Investing Cash Flow", "Financing Cash Flow",
    "Repurchase Of Capital Stock", "Cash Dividends Paid",
    "Changes In Cash",
]
_KEY_ITEMS = {
    "balance_sheet": _KEY_BALANCE_SHEET,
    "income_statement": _KEY_INCOME_STMT,
    "cash_flow": _KEY_CASH_FLOW,
}


def _dataframe_to_dict(df, statement_type: str = "") -> dict:
    """yfinance DataFrame을 JSON 직렬화 가능한 dict로 변환.

    statement_type이 지정되면 핵심 항목만 추출하여 크기를 줄임.
    """
    if df is None or df.empty:
        return {}

    key_items = _KEY_ITEMS.get(statement_type)
    result = {}
    for col in df.columns:
        date_key = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
        col_data = {}
        for idx, val in df[col].items():
            idx_str = str(idx)
            if key_items and idx_str not in key_items:
                continue
            v = _safe_float(val)
            if v is not None:
                col_data[idx_str] = v
        result[date_key] = col_data
    return result


async def fetch_korean_financials(stock_name: str) -> dict:
    """한국 주식 종목의 재무제표(대차대조표, 손익계산서, 현금흐름표)를 수집합니다.

    한국어 종목명 또는 6자리 종목코드를 입력하면 yfinance를 통해
    연간 및 분기별 재무제표 데이터를 반환합니다.

    Args:
        stock_name: 한국 주식 종목명 또는 코드 (예: 삼성전자, 005930, SK하이닉스)

    Returns:
        dict: 재무제표 데이터. status, ticker, annual, quarterly 포함.
    """
    ticker_symbol = _resolve_korean_stock_code(stock_name)
    if not ticker_symbol:
        return {
            "status": "error",
            "stock_name": stock_name,
            "market": "KR",
            "error": f"종목코드를 찾을 수 없습니다: {stock_name}",
        }

    ticker = yf.Ticker(ticker_symbol)

    # .KS에서 데이터가 없으면 .KQ(코스닥)로 재시도
    bs = ticker.balance_sheet
    if bs is None or bs.empty:
        if ticker_symbol.endswith(".KS"):
            ticker_symbol = ticker_symbol.replace(".KS", ".KQ")
            ticker = yf.Ticker(ticker_symbol)
            bs = ticker.balance_sheet

    try:
        result = {
            "status": "success",
            "stock_name": stock_name,
            "ticker": ticker_symbol,
            "market": "KR",
            "company_name": ticker.info.get("longName", stock_name),
            "sector": ticker.info.get("sector", ""),
            "industry": ticker.info.get("industry", ""),
            "annual": {
                "balance_sheet": _dataframe_to_dict(ticker.balance_sheet, "balance_sheet"),
                "income_statement": _dataframe_to_dict(ticker.income_stmt, "income_statement"),
                "cash_flow": _dataframe_to_dict(ticker.cashflow, "cash_flow"),
            },
            "quarterly": {
                "balance_sheet": _dataframe_to_dict(ticker.quarterly_balance_sheet, "balance_sheet"),
                "income_statement": _dataframe_to_dict(ticker.quarterly_income_stmt, "income_statement"),
                "cash_flow": _dataframe_to_dict(ticker.quarterly_cashflow, "cash_flow"),
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "stock_name": stock_name,
            "ticker": ticker_symbol,
            "market": "KR",
            "error": str(e),
        }

    # 데이터 존재 여부 확인
    if not result["annual"]["balance_sheet"]:
        result["status"] = "partial"
        result["warning"] = "연간 재무제표 데이터가 없거나 제한적입니다."

    return result


async def fetch_us_financials(stock_ticker: str) -> dict:
    """미국 주식 종목의 재무제표(대차대조표, 손익계산서, 현금흐름표)를 수집합니다.

    미국 주식 티커 심볼을 입력하면 yfinance를 통해
    연간 및 분기별 재무제표 데이터를 반환합니다.

    Args:
        stock_ticker: 미국 주식 티커 심볼 (예: AAPL, TSLA, MSFT, NVDA)

    Returns:
        dict: 재무제표 데이터. status, ticker, annual, quarterly 포함.
    """
    ticker_symbol = stock_ticker.upper().strip()
    ticker = yf.Ticker(ticker_symbol)

    try:
        info = ticker.info
        if not info or info.get("regularMarketPrice") is None:
            return {
                "status": "error",
                "stock_name": stock_ticker,
                "ticker": ticker_symbol,
                "market": "US",
                "error": f"티커를 찾을 수 없습니다: {ticker_symbol}",
            }

        return {
            "status": "success",
            "stock_name": info.get("shortName", stock_ticker),
            "ticker": ticker_symbol,
            "market": "US",
            "company_name": info.get("longName", stock_ticker),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "annual": {
                "balance_sheet": _dataframe_to_dict(ticker.balance_sheet, "balance_sheet"),
                "income_statement": _dataframe_to_dict(ticker.income_stmt, "income_statement"),
                "cash_flow": _dataframe_to_dict(ticker.cashflow, "cash_flow"),
            },
            "quarterly": {
                "balance_sheet": _dataframe_to_dict(ticker.quarterly_balance_sheet, "balance_sheet"),
                "income_statement": _dataframe_to_dict(ticker.quarterly_income_stmt, "income_statement"),
                "cash_flow": _dataframe_to_dict(ticker.quarterly_cashflow, "cash_flow"),
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "stock_name": stock_ticker,
            "ticker": ticker_symbol,
            "market": "US",
            "error": str(e),
        }
