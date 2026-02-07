"""
Kiwoom REST API Client
키움증권 REST API 연동 클라이언트
Based on TRADING_SYSTEM_SPEC.md Section 5.1

Note: 키움 REST API는 2025년 3월 출시.
실제 API 엔드포인트와 파라미터는 공식 문서에서 확인 필요.
"""
import time
import logging
import requests
from shared.config import settings

logger = logging.getLogger(__name__)


class KiwoomRESTClient:
    """키움증권 REST API 클라이언트"""

    # NOTE: 실제 키움 REST API URL은 공식 문서 참조
    # 아래는 한국투자증권 API 형식을 참조한 예시
    BASE_URL = "https://openapi.kiwoom.com"
    MOCK_URL = "https://mockapi.kiwoom.com"

    def __init__(self):
        self.app_key = settings.KIWOOM_APP_KEY
        self.app_secret = settings.KIWOOM_APP_SECRET
        self.account_no = settings.KIWOOM_ACCOUNT_NO
        self.is_mock = settings.KIWOOM_IS_MOCK
        self.token = None
        self.token_expires_at = 0

        self.base_url = self.MOCK_URL if self.is_mock else self.BASE_URL

    def _ensure_token(self):
        """OAuth 토큰 발급/갱신"""
        if self.token and time.time() < self.token_expires_at:
            return

        if not self.app_key or not self.app_secret:
            logger.warning("Kiwoom API credentials not configured")
            return

        try:
            resp = requests.post(
                f"{self.base_url}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data.get("access_token")
            self.token_expires_at = time.time() + data.get("expires_in", 86400) - 60
            logger.info("Kiwoom API token refreshed")
        except Exception as e:
            logger.error(f"Failed to get Kiwoom API token: {e}")

    def _headers(self, tr_id: str) -> dict:
        """공통 헤더 생성"""
        self._ensure_token()
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.token}" if self.token else "",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

    # ── 국내 주식 ──

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
        # 모의투자/실전투자 TR_ID 구분
        if order_type == "BUY":
            tr_id = "VTTC0802U" if self.is_mock else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if self.is_mock else "TTTC0801U"

        body = {
            "CANO": self.account_no[:8] if len(self.account_no) >= 8 else self.account_no,
            "ACNT_PRDT_CD": self.account_no[8:] if len(self.account_no) > 8 else "01",
            "PDNO": ticker,
            "ORD_DVSN": "00",  # 00: 지정가, 01: 시장가
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }

        try:
            resp = requests.post(
                f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash",
                headers=self._headers(tr_id),
                json=body,
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"error": str(e)}

    # ── 해외(미국) 주식 ──

    def order_us_stock(
        self,
        ticker: str,
        qty: int,
        price: float,
        order_type: str = "BUY",
        exchange: str = "NASD",
    ) -> dict:
        """미국 주식 주문

        Args:
            ticker: 티커 심볼 (예: AAPL)
            qty: 주문 수량
            price: 주문 가격 (USD)
            order_type: "BUY" 또는 "SELL"
            exchange: 거래소 (NASD, NYSE, AMEX)

        Returns:
            dict: API 응답
        """
        if order_type == "BUY":
            tr_id = "VTTT1002U" if self.is_mock else "JTTT1002U"
        else:
            tr_id = "VTTT1006U" if self.is_mock else "JTTT1006U"

        body = {
            "CANO": self.account_no[:8] if len(self.account_no) >= 8 else self.account_no,
            "ACNT_PRDT_CD": self.account_no[8:] if len(self.account_no) > 8 else "01",
            "OVRS_EXCG_CD": exchange,
            "PDNO": ticker,
            "ORD_DVSN": "00",
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": str(price),
        }

        try:
            resp = requests.post(
                f"{self.base_url}/uapi/overseas-stock/v1/trading/order",
                headers=self._headers(tr_id),
                json=body,
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"US order failed: {e}")
            return {"error": str(e)}

    # ── 조회 ──

    def get_balance(self) -> dict:
        """계좌 잔고 조회"""
        params = {
            "CANO": self.account_no[:8] if len(self.account_no) >= 8 else self.account_no,
            "ACNT_PRDT_CD": self.account_no[8:] if len(self.account_no) > 8 else "01",
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
        }

        tr_id = "VTTC8434R" if self.is_mock else "TTTC8434R"

        try:
            resp = requests.get(
                f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=self._headers(tr_id),
                params=params,
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Balance query failed: {e}")
            return {"error": str(e)}

    def get_current_price_kr(self, ticker: str) -> dict:
        """국내 주식 현재가 조회"""
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }

        try:
            resp = requests.get(
                f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=self._headers("FHKST01010100"),
                params=params,
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Price query failed: {e}")
            return {"error": str(e)}
