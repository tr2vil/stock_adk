"""
Order Manager - 매매 의사결정을 실제 주문으로 변환하고 관리
Based on TRADING_SYSTEM_SPEC.md Section 5.2
"""
import logging
from shared.models import TradeDecision
from shared.config import settings
from .kiwoom_rest import KiwoomRESTClient

logger = logging.getLogger(__name__)


class OrderManager:
    """매매 의사결정을 실제 주문으로 변환하고 관리합니다."""

    def __init__(self, dry_run: bool = None):
        """
        Args:
            dry_run: True면 주문 미실행 (로그만). None이면 설정에서 가져옴.
        """
        self.client = KiwoomRESTClient()
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.daily_trade_count = 0
        self.max_daily_trades = settings.MAX_DAILY_TRADES

    def reset_daily_count(self):
        """일일 거래 카운트 초기화 (매일 장 시작 시 호출)"""
        self.daily_trade_count = 0

    def execute(self, decision: TradeDecision) -> dict:
        """TradeDecision을 받아 주문을 실행합니다.

        Args:
            decision: 매매 의사결정 객체

        Returns:
            dict: 실행 결과
        """
        # HOLD인 경우 주문 없음
        if decision.action == "HOLD":
            logger.info(f"[HOLD] {decision.ticker} - 관망")
            return {
                "status": "hold",
                "ticker": decision.ticker,
                "message": "No action taken",
            }

        # 일일 거래 횟수 제한 체크
        if self.daily_trade_count >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.max_daily_trades}")
            return {
                "status": "limit_reached",
                "ticker": decision.ticker,
                "message": f"Daily trade limit ({self.max_daily_trades}) reached",
            }

        # 수량 체크
        if decision.quantity <= 0:
            logger.warning(f"Invalid quantity: {decision.quantity}")
            return {
                "status": "invalid",
                "ticker": decision.ticker,
                "message": "Quantity must be positive",
            }

        # Dry run 모드
        if self.dry_run:
            logger.info(
                f"[DRY RUN] {decision.action} {decision.ticker} "
                f"x{decision.quantity} @ {decision.target_price}"
            )
            self._save_trade_log(decision, status="dry_run")
            return {
                "status": "dry_run",
                "ticker": decision.ticker,
                "action": decision.action,
                "quantity": decision.quantity,
                "price": decision.target_price,
                "message": "Dry run - order not executed",
            }

        # 실제 주문 실행
        try:
            if decision.market.value == "KR":
                result = self.client.order_kr_stock(
                    ticker=decision.ticker,
                    qty=decision.quantity,
                    price=int(decision.target_price),
                    order_type=decision.action,
                )
            else:  # US
                result = self.client.order_us_stock(
                    ticker=decision.ticker,
                    qty=decision.quantity,
                    price=decision.target_price,
                    order_type=decision.action,
                )

            self.daily_trade_count += 1
            self._save_trade_log(decision, status="executed", result=result)

            # 알림 전송
            self._send_notification(decision)

            logger.info(f"[EXECUTED] {decision.action} {decision.ticker}")
            return {
                "status": "executed",
                "ticker": decision.ticker,
                "action": decision.action,
                "quantity": decision.quantity,
                "result": result,
            }

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            self._save_trade_log(decision, status="failed", error=str(e))
            return {
                "status": "failed",
                "ticker": decision.ticker,
                "error": str(e),
            }

    def _save_trade_log(
        self,
        decision: TradeDecision,
        status: str,
        result: dict = None,
        error: str = None,
    ):
        """거래 로그를 저장합니다.

        TODO: 실제 구현 시 PostgreSQL에 저장
        """
        log_entry = {
            "ticker": decision.ticker,
            "market": decision.market.value,
            "action": decision.action,
            "quantity": decision.quantity,
            "price": decision.target_price,
            "stop_loss": decision.stop_loss,
            "take_profit": decision.take_profit,
            "final_score": decision.final_score,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": decision.timestamp.isoformat(),
        }
        logger.info(f"Trade log: {log_entry}")

    def _send_notification(self, decision: TradeDecision):
        """알림을 전송합니다.

        TODO: 실제 구현 시 Telegram/Slack 연동
        """
        message = (
            f"🔔 {decision.action} {decision.ticker}\n"
            f"수량: {decision.quantity}\n"
            f"가격: {decision.target_price}\n"
            f"손절: {decision.stop_loss}\n"
            f"익절: {decision.take_profit}\n"
            f"점수: {decision.final_score:.3f}\n"
            f"근거: {decision.reasoning}"
        )
        logger.info(f"Notification: {message}")
