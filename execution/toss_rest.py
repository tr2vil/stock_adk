"""
Toss Securities Open API Client
토스증권 Open API 연동 클라이언트

API 문서: https://developers.tossinvest.com/docs
- Base URL: https://openapi.tossinvest.com
- 인증: OAuth 2.0 Client Credentials (form-urlencoded)
- KR/US 단일 엔드포인트(`/api/v1/orders`)로 통합, TR_ID 개념 없음
- 모든 숫자 필드는 문자열(string)
- 실시간 시세(WebSocket) 미지원, REST only

KiwoomRESTClient와 동일한 public 인터페이스를 유지하여 OrderManager 변경을 최소화한다.
"""
import time
import uuid
import logging
import requests
from shared.config import settings

logger = logging.getLogger(__name__)


class TossRESTClient:
    """토스증권 Open API 클라이언트"""

    BASE_URL = "https://openapi.tossinvest.com"

    def __init__(self):
        self.client_id = settings.TOSS_API_KEY
        self.client_secret = settings.TOSS_SECRET_KEY
        self.base_url = self.BASE_URL

        self.token = None
        self.token_expires_at = 0

        # X-Tossinvest-Account 헤더값. 설정에 없으면 /api/v1/accounts에서 자동 조회.
        self._account_seq = settings.TOSS_ACCOUNT_SEQ or None

    # ── 인증 ──

    def _ensure_token(self):
        """OAuth 토큰 발급/갱신 (client_credentials, form-urlencoded)"""
        if self.token and time.time() < self.token_expires_at:
            return

        if not self.client_id or not self.client_secret:
            logger.warning("Toss API credentials not configured (TOSS_API_KEY/TOSS_SECRET_KEY)")
            return

        try:
            resp = requests.post(
                f"{self.base_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data.get("access_token")
            # expires_in(초) 만료 60초 전을 갱신 시점으로
            self.token_expires_at = time.time() + data.get("expires_in", 86400) - 60
            logger.info("Toss API token refreshed")
        except Exception as e:
            logger.error(f"Failed to get Toss API token: {e}")

    def _headers(self, with_account: bool = False) -> dict:
        """공통 헤더 생성

        Args:
            with_account: True면 X-Tossinvest-Account 헤더 포함 (주문/잔고용)
        """
        self._ensure_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}" if self.token else "",
        }
        if with_account:
            account_seq = self._ensure_account_seq()
            if account_seq:
                headers["X-Tossinvest-Account"] = str(account_seq)
        return headers

    def _ensure_account_seq(self):
        """accountSeq 확보. 설정값이 없으면 /api/v1/accounts 첫 계좌를 사용."""
        if self._account_seq:
            return self._account_seq

        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/accounts",
                headers={"Authorization": f"Bearer {self.token}" if self.token else ""},
                timeout=10,
            )
            resp.raise_for_status()
            accounts = resp.json().get("result", [])
            if not accounts:
                logger.error("No Toss accounts found")
                return None
            self._account_seq = str(accounts[0].get("accountSeq"))
            logger.info(f"Toss accountSeq resolved: {self._account_seq}")
            return self._account_seq
        except Exception as e:
            logger.error(f"Failed to resolve Toss accountSeq: {e}")
            return None

    # ── 주문 ──

    def _create_order(
        self,
        symbol: str,
        qty: int,
        price: float,
        order_type: str = "BUY",
        order_kind: str = "LIMIT",
    ) -> dict:
        """주문 생성 (KR/US 공통). POST /api/v1/orders

        Args:
            symbol: 종목코드(KR 6자리) 또는 티커(US)
            qty: 주문 수량
            price: 주문 가격 (LIMIT일 때 사용)
            order_type: "BUY" 또는 "SELL"
            order_kind: "LIMIT"(지정가) 또는 "MARKET"(시장가)

        Returns:
            dict: API 응답 ({"result": {"orderId": ...}} 또는 {"error": ...})
        """
        side = "BUY" if order_type.upper() == "BUY" else "SELL"

        body = {
            "clientOrderId": uuid.uuid4().hex,  # 멱등키: 네트워크 재시도 시 중복주문 방지
            "symbol": symbol,
            "side": side,
            "orderType": order_kind,
            "quantity": str(qty),
        }
        # 지정가일 때만 price 포함
        if order_kind == "LIMIT":
            body["price"] = str(price)

        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/orders",
                headers=self._headers(with_account=True),
                json=body,
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Toss order failed: {e}")
            return {"error": str(e)}

    def order_kr_stock(
        self,
        ticker: str,
        qty: int,
        price: int,
        order_type: str = "BUY",
    ) -> dict:
        """국내 주식 주문 (지정가)

        Args:
            ticker: 종목코드 (6자리)
            qty: 주문 수량
            price: 주문 가격
            order_type: "BUY" 또는 "SELL"

        Returns:
            dict: API 응답
        """
        return self._create_order(symbol=ticker, qty=qty, price=price, order_type=order_type)

    def order_us_stock(
        self,
        ticker: str,
        qty: int,
        price: float,
        order_type: str = "BUY",
        exchange: str = None,
    ) -> dict:
        """미국 주식 주문

        토스 API는 KR/US를 단일 엔드포인트로 처리하며 거래소 코드가 불필요하다.
        (exchange 인자는 KiwoomRESTClient 인터페이스 호환용으로만 유지)

        Args:
            ticker: 티커 심볼 (예: AAPL)
            qty: 주문 수량
            price: 주문 가격 (USD)
            order_type: "BUY" 또는 "SELL"
            exchange: (미사용) 인터페이스 호환용

        Returns:
            dict: API 응답
        """
        return self._create_order(symbol=ticker, qty=qty, price=price, order_type=order_type)

    # ── 조회 ──

    def get_balance(self) -> dict:
        """계좌 잔고/보유종목 조회. GET /api/v1/holdings

        토스 API가 간헐적으로 빈 응답을 주므로 1회 재시도한다.
        """
        last_error = ""
        for attempt in range(2):
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v1/holdings",
                    headers=self._headers(with_account=True),
                    timeout=10,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Toss balance query attempt {attempt} failed: {e}")
                time.sleep(0.5)
        logger.error(f"Toss balance query failed: {last_error}")
        return {"error": last_error}

    def get_current_price_kr(self, ticker: str) -> dict:
        """국내/해외 주식 현재가 조회. GET /api/v1/prices

        Args:
            ticker: 종목코드(KR 6자리) 또는 티커(US)

        Returns:
            dict: API 응답 ({"result": [{"symbol", "lastPrice", "currency", ...}]})
        """
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/prices",
                headers=self._headers(),
                params={"symbols": ticker},
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Toss price query failed: {e}")
            return {"error": str(e)}

    def get_prices(self, symbols: list[str]) -> dict:
        """복수 종목 현재가 조회. GET /api/v1/prices (최대 200개, 콤마 구분)

        Args:
            symbols: 종목코드/티커 리스트

        Returns:
            dict: API 응답 ({"result": [{"symbol", "lastPrice", "currency", ...}]})
        """
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/prices",
                headers=self._headers(),
                params={"symbols": ",".join(symbols)},
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Toss prices query failed: {e}")
            return {"error": str(e)}

    def get_candles(self, symbol: str, interval: str = "1d", count: int = 60) -> dict:
        """캔들(차트) 데이터 조회. GET /api/v1/candles

        Args:
            symbol: 종목코드(KR 6자리) 또는 티커(US)
            interval: 캔들 간격 (예: "1d" 일봉, "1m" 분봉)
            count: 캔들 개수

        Returns:
            dict: API 응답 ({"result": {"candles": [{"timestamp", "openPrice",
                  "highPrice", "lowPrice", "closePrice", "volume", "currency"}]}})
        """
        # 토스 캔들 API는 간헐적으로 빈 응답을 줄 때가 있어 1회 재시도한다.
        last_error = ""
        for attempt in range(2):
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v1/candles",
                    headers=self._headers(),
                    params={"symbol": symbol, "interval": interval, "count": str(count)},
                    timeout=10,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Toss candles query attempt {attempt} failed: {e}")
                time.sleep(0.5)
        logger.error(f"Toss candles query failed: {last_error}")
        return {"error": last_error}
