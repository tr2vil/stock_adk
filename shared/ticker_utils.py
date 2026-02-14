"""
Shared Ticker Utilities - 종목명/티커 변환 유틸리티
미국/한국 주식 종목명을 yfinance 티커로 변환
"""
import re
import yfinance as yf


# 주요 미국 종목 한글명 → 티커 매핑
_US_NAME_MAP = {
    # Big Tech
    "애플": "AAPL",
    "마이크로소프트": "MSFT",
    "구글": "GOOGL",
    "알파벳": "GOOGL",
    "아마존": "AMZN",
    "메타": "META",
    "페이스북": "META",
    "엔비디아": "NVDA",
    "테슬라": "TSLA",
    "넷플릭스": "NFLX",
    # Semiconductors
    "인텔": "INTC",
    "AMD": "AMD",
    "퀄컴": "QCOM",
    "브로드컴": "AVGO",
    "마이크론": "MU",
    "텍사스인스트루먼트": "TXN",
    "ASML": "ASML",
    "TSMC": "TSM",
    "대만반도체": "TSM",
    # Finance
    "JP모건": "JPM",
    "골드만삭스": "GS",
    "뱅크오브아메리카": "BAC",
    "웰스파고": "WFC",
    "씨티그룹": "C",
    "비자": "V",
    "마스터카드": "MA",
    "페이팔": "PYPL",
    "버크셔해서웨이": "BRK-B",
    # Healthcare
    "존슨앤존슨": "JNJ",
    "화이자": "PFE",
    "모더나": "MRNA",
    "유나이티드헬스": "UNH",
    "애브비": "ABBV",
    "일라이릴리": "LLY",
    "머크": "MRK",
    # Consumer
    "코카콜라": "KO",
    "펩시코": "PEP",
    "맥도날드": "MCD",
    "나이키": "NKE",
    "스타벅스": "SBUX",
    "월마트": "WMT",
    "코스트코": "COST",
    "홈디포": "HD",
    "프록터앤갬블": "PG",
    # Industrial
    "보잉": "BA",
    "캐터필러": "CAT",
    "록히드마틴": "LMT",
    "3M": "MMM",
    "GE": "GE",
    "허니웰": "HON",
    # Energy
    "엑손모빌": "XOM",
    "셰브론": "CVX",
    # EV & Energy
    "리비안": "RIVN",
    "루시드": "LCID",
    # Entertainment
    "디즈니": "DIS",
    "워너브라더스": "WBD",
    # Others
    "세일즈포스": "CRM",
    "어도비": "ADBE",
    "오라클": "ORCL",
    "시스코": "CSCO",
    "IBM": "IBM",
    "팔란티어": "PLTR",
    "스노우플레이크": "SNOW",
    "줌": "ZM",
    "쇼피파이": "SHOP",
    "스퀘어": "SQ",
    "블록": "SQ",
    "로빈후드": "HOOD",
    "코인베이스": "COIN",
    "크라우드스트라이크": "CRWD",
    "옥타": "OKTA",
    "도큐사인": "DOCU",
    "스포티파이": "SPOT",
    "에어비앤비": "ABNB",
    "우버": "UBER",
    "리프트": "LYFT",
    "도어대시": "DASH",
}

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


def lookup_us_ticker(company_name: str) -> str | None:
    """미국 주식 회사명으로 티커를 조회합니다.

    Args:
        company_name: 회사명 (한글 또는 영문)

    Returns:
        str: 티커 심볼 (예: "AAPL"). 찾지 못하면 None.
    """
    cleaned = company_name.strip()

    # 이미 티커 형식인 경우 (대문자 알파벳 1-5자)
    if re.match(r"^[A-Z]{1,5}(-[A-Z])?$", cleaned.upper()):
        return cleaned.upper()

    # 한글 → 티커 매핑 확인
    if cleaned in _US_NAME_MAP:
        return _US_NAME_MAP[cleaned]

    # yfinance Search로 검색
    try:
        search = yf.Search(cleaned, max_results=5)
        for quote in search.quotes:
            symbol = quote.get("symbol", "")
            exchange = quote.get("exchange", "")
            # 미국 거래소 확인 (NYSE, NASDAQ 등)
            if exchange in ["NMS", "NYQ", "NGM", "NCM", "NAS", "NYSE", "NASDAQ"]:
                return symbol
            # .KS/.KQ가 아닌 경우 미국 주식으로 간주
            if not symbol.endswith((".KS", ".KQ", ".T", ".HK", ".L")):
                return symbol
    except Exception:
        pass

    return None


def lookup_kr_ticker(company_name: str) -> str | None:
    """한국 주식 회사명으로 티커를 조회합니다.

    Args:
        company_name: 회사명 (한글) 또는 6자리 종목코드

    Returns:
        str: yfinance 티커 심볼 (예: "005930.KS"). 찾지 못하면 None.
    """
    cleaned = company_name.strip()

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

    return None


def _clean_query(query: str) -> str:
    """입력에서 한국어 동사/조사 등 불필요한 접미사를 제거합니다."""
    cleaned = query.strip()
    # 한국어 동작어/접미사 제거 (뒤에서부터)
    suffixes = [
        "분석해줘", "분석해주세요", "분석해", "분석하기", "분석",
        "알려줘", "알려주세요", "조회해줘", "조회해", "조회",
        "검색해줘", "검색해", "검색", "찾아줘", "찾아",
        "보여줘", "보여주세요",
    ]
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)].strip()
            break
    return cleaned


# 대소문자 무시 매핑 (영문자 포함 한국 종목명 대응: sk하이닉스 → SK하이닉스)
_US_NAME_MAP_LOWER = {k.lower(): v for k, v in _US_NAME_MAP.items()}
_KR_NAME_MAP_LOWER = {k.lower(): k for k, v in _KR_NAME_MAP.items()}


def lookup_ticker(query: str) -> dict:
    """종목명 또는 티커를 조회하여 정확한 티커 정보를 반환합니다.

    한글 종목명(테슬라, 삼성전자), 영문 회사명(Tesla, Apple),
    또는 티커(AAPL, 005930)를 입력하면 해당 종목의 정보를 반환합니다.

    Args:
        query: 종목명 또는 티커 (예: "테슬라", "Tesla", "TSLA", "삼성전자", "005930")

    Returns:
        dict: 조회 결과. ticker, market, company_name, status 포함.
    """
    cleaned = _clean_query(query)

    # 1. 이미 yfinance 한국 티커 형식인 경우
    if re.match(r"^\d{6}\.(KS|KQ)$", cleaned):
        try:
            stock = yf.Ticker(cleaned)
            info = stock.info
            return {
                "status": "success",
                "ticker": cleaned,
                "market": "KR",
                "company_name": info.get("shortName", info.get("longName", cleaned)),
            }
        except Exception:
            return {"status": "success", "ticker": cleaned, "market": "KR", "company_name": cleaned}

    # 2. 6자리 숫자 (한국 종목코드)
    if cleaned.isdigit() and len(cleaned) == 6:
        ticker = f"{cleaned}.KS"
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if info.get("regularMarketPrice"):
                return {
                    "status": "success",
                    "ticker": ticker,
                    "market": "KR",
                    "company_name": info.get("shortName", info.get("longName", cleaned)),
                }
            # KOSDAQ 시도
            ticker = f"{cleaned}.KQ"
            stock = yf.Ticker(ticker)
            info = stock.info
            if info.get("regularMarketPrice"):
                return {
                    "status": "success",
                    "ticker": ticker,
                    "market": "KR",
                    "company_name": info.get("shortName", info.get("longName", cleaned)),
                }
        except Exception:
            pass
        return {"status": "error", "error": f"종목을 찾을 수 없습니다: {cleaned}"}

    # 3. 대문자 알파벳 (미국 티커)
    if re.match(r"^[A-Z]{1,5}(-[A-Z])?$", cleaned.upper()):
        ticker = cleaned.upper()
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if info.get("regularMarketPrice"):
                return {
                    "status": "success",
                    "ticker": ticker,
                    "market": "US",
                    "company_name": info.get("shortName", info.get("longName", ticker)),
                }
        except Exception:
            pass

    # 4. 한글 미국 종목명 확인 (대소문자 무시)
    us_ticker = _US_NAME_MAP.get(cleaned) or _US_NAME_MAP_LOWER.get(cleaned.lower())
    if us_ticker:
        ticker = us_ticker
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "status": "success",
                "ticker": ticker,
                "market": "US",
                "company_name": info.get("shortName", info.get("longName", cleaned)),
            }
        except Exception:
            return {"status": "success", "ticker": ticker, "market": "US", "company_name": cleaned}

    # 5. 한글 한국 종목명 확인 (대소문자 무시)
    canonical = _KR_NAME_MAP_LOWER.get(cleaned.lower())
    if canonical or cleaned in _KR_NAME_MAP:
        cleaned = canonical or cleaned
        kr_ticker = lookup_kr_ticker(cleaned)
        if kr_ticker:
            try:
                stock = yf.Ticker(kr_ticker)
                info = stock.info
                return {
                    "status": "success",
                    "ticker": kr_ticker,
                    "market": "KR",
                    "company_name": info.get("shortName", info.get("longName", cleaned)),
                }
            except Exception:
                return {"status": "success", "ticker": kr_ticker, "market": "KR", "company_name": cleaned}

    # 6. yfinance Search로 검색 (미국 우선)
    try:
        search = yf.Search(cleaned, max_results=10)
        for quote in search.quotes:
            symbol = quote.get("symbol", "")
            exchange = quote.get("exchange", "")
            short_name = quote.get("shortname", "")

            # 한국 종목
            if symbol.endswith((".KS", ".KQ")):
                return {
                    "status": "success",
                    "ticker": symbol,
                    "market": "KR",
                    "company_name": short_name or cleaned,
                }

            # 미국 종목
            if exchange in ["NMS", "NYQ", "NGM", "NCM", "NAS", "NYSE", "NASDAQ"]:
                return {
                    "status": "success",
                    "ticker": symbol,
                    "market": "US",
                    "company_name": short_name or cleaned,
                }

            # 기타 (미국으로 가정)
            if not symbol.endswith((".T", ".HK", ".L", ".PA", ".DE")):
                return {
                    "status": "success",
                    "ticker": symbol,
                    "market": "US",
                    "company_name": short_name or cleaned,
                }
    except Exception:
        pass

    return {"status": "error", "error": f"종목을 찾을 수 없습니다: {cleaned}"}
