import os
import json
from typing import Dict, Any
from utils.kiwoom import kiwoom_client

class AccountManagementAgent:
    def __init__(self):
        self.name = "AccountManagementAgent"

    async def run(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        계좌 관리 에이전트 실행
        action: 'balance' | 'holdings' | 'list'
        """
        if action == "balance" or action == "holdings":
            # 계좌 번호를 가져오거나 기본 계좌 사용
            # 실제로는 유저 세션이나 DB에서 가져와야 함. 여기서는 Mock 계좌 사용 권장.
            account_no = os.getenv("KIWOOM_ACCOUNT_NO", "8145123411")

            result = await kiwoom_client.get_account_balance(account_no)

            if "error" in result:
                return {
                    "status": "error",
                    "message": f"계좌 정보를 가져오는데 실패했습니다: {result['error']}"
                }

            # A2UI_CARD 형식으로 변환할 데이터 정리
            # OPW00018 결과 기반 (실제 데이터 구조에 맞춰 가공 필요)
            summary = result.get("output", {}).get("summary", {})
            holdings = result.get("output", {}).get("list", [])

            return {
                "status": "success",
                "summary": {
                    "total_asset": summary.get("total_asset", 0),
                    "total_profit": summary.get("total_profit", 0),
                    "profit_rate": summary.get("profit_rate", 0),
                    "cash": summary.get("cash", 0)
                },
                "holdings": holdings[:10] # 상위 10개만 표시
            }

        return {
            "status": "unknown_action",
            "message": f"알 수 없는 요청입니다: {action}"
        }
