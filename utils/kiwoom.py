import os
import httpx
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class KiwoomClient:
    def __init__(self, use_mock=True):
        self.app_key = os.getenv("KIWOOM_APP_KEY")
        self.secret_key = os.getenv("KIWOOM_SECRET_KEY")
        # Use Mock API by default for safety
        self.base_url = "https://mockapi.kiwoom.com" if use_mock else "https://api.kiwoom.com"
        self.access_token = None
        self.token_expiry = None

    async def _ensure_token(self):
        """액세스 토큰이 유효한지 확인하고 필요시 갱신합니다."""
        if self.access_token and self.token_expiry and self.token_expiry > datetime.now():
            return self.access_token

        if not self.app_key or not self.secret_key:
            logger.error("KIWOOM_APP_KEY or KIWOOM_SECRET_KEY is missing")
            return None

        url = f"{self.base_url}/v1/auth/token"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecretkey": self.secret_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                self.access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))
                # 만료 1분 전을 목표로 설정
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info("Successfully obtained Kiwoom access token")
                return self.access_token
            except Exception as e:
                logger.error(f"Failed to get Kiwoom token: {e}")
                return None

    async def call_tr(self, tr_id: str, params: dict):
        """Generic TR(Transaction Request) 호출 유틸리티"""
        token = await self._ensure_token()
        if not token:
            return {"error": "Authentication failed"}

        url = f"{self.base_url}/v1/tr/details"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "tr_id": tr_id
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=params, timeout=15.0)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Kiwoom TR ({tr_id}) Error: {e}")
                return {"error": str(e)}

    async def get_account_balance(self, account_no: str):
        """계좌 잔고 조회 (OPW00018)"""
        params = {
            "account": account_no,
            "pw": "", # Open API RE에서는 보통 공백
            "pw_id": "",
            "ext": "0"
        }
        return await self.call_tr("opw00018", params)

# Global Instance
kiwoom_client = KiwoomClient(use_mock=True)
