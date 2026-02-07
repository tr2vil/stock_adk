"""
Alerting - Telegram/Slack 알림 모듈
거래 실행, 가격 알림, 시스템 상태 등의 알림 전송
"""
import asyncio
import logging
import httpx
from shared.config import settings

logger = logging.getLogger(__name__)


async def send_telegram_notification(message: str) -> bool:
    """Telegram 알림을 전송합니다.

    Args:
        message: 전송할 메시지

    Returns:
        bool: 전송 성공 여부
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.debug("Telegram credentials not configured")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


async def send_slack_notification(message: str) -> bool:
    """Slack 알림을 전송합니다.

    Args:
        message: 전송할 메시지

    Returns:
        bool: 전송 성공 여부
    """
    if not settings.SLACK_WEBHOOK_URL:
        logger.debug("Slack webhook not configured")
        return False

    payload = {"text": message}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("Slack notification sent")
                return True
            else:
                logger.error(f"Slack API error: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def send_notification(message: str) -> bool:
    """동기 방식으로 알림을 전송합니다.

    Telegram과 Slack 모두 시도하고 하나라도 성공하면 True 반환.

    Args:
        message: 전송할 메시지

    Returns:
        bool: 전송 성공 여부
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _send_all():
        results = await asyncio.gather(
            send_telegram_notification(message),
            send_slack_notification(message),
            return_exceptions=True,
        )
        return any(r is True for r in results)

    return loop.run_until_complete(_send_all())


# Predefined message templates
def format_trade_alert(
    action: str,
    ticker: str,
    quantity: int,
    price: float,
    score: float,
    reasoning: str,
) -> str:
    """거래 알림 메시지 포맷"""
    emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
    return (
        f"{emoji} *{action}* {ticker}\n"
        f"수량: {quantity}\n"
        f"가격: {price:,.2f}\n"
        f"점수: {score:.3f}\n"
        f"근거: {reasoning}"
    )


def format_price_alert(ticker: str, current_price: float, target_price: float, condition: str) -> str:
    """가격 알림 메시지 포맷"""
    emoji = "📈" if condition == "above" else "📉"
    return (
        f"{emoji} *가격 알림* {ticker}\n"
        f"현재가: {current_price:,.2f}\n"
        f"목표가: {target_price:,.2f} ({condition})"
    )


def format_system_alert(level: str, message: str) -> str:
    """시스템 알림 메시지 포맷"""
    emoji_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🚨",
        "critical": "🔥",
    }
    emoji = emoji_map.get(level.lower(), "📢")
    return f"{emoji} *시스템 알림*\n{message}"
