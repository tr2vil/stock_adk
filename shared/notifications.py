"""Telegram 알림 (send 전용, httpx 기반).

설계서 8장 HiL/매매일지/전략제안 발송을 담당한다. TELEGRAM_BOT_TOKEN/CHAT_ID 가
없으면 **graceful no-op**(로그만) 하여 키 없이도 전체 시스템이 동작·테스트된다.

버튼 콜백(승인/거부) 처리는 별도 봇 컨슈머(long-polling/webhook) 또는 REST
엔드포인트(/api/evolution/approve|reject)로 처리한다. 본 모듈은 발송만 책임진다.
"""
from __future__ import annotations

import httpx

from shared.config import settings
from shared.logger import get_logger

logger = get_logger("shared.notifications")

_API = "https://api.telegram.org/bot{token}/{method}"


def telegram_enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


async def send_message(text: str, reply_markup: dict | None = None) -> dict:
    """Telegram 메시지 발송. 미설정 시 no-op."""
    if not telegram_enabled():
        logger.info("telegram_noop", preview=text[:80])
        return {"status": "disabled"}

    url = _API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendMessage")
    payload: dict = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        return {"status": "sent"}
    except Exception as e:  # 알림 실패가 매매/진화를 막지 않도록
        logger.warning("telegram_send_failed", error=str(e))
        return {"status": "error", "error": str(e)}


def _approval_keyboard(approve_cb: str, reject_cb: str) -> dict:
    """인라인 승인/거부 버튼."""
    return {
        "inline_keyboard": [[
            {"text": "✅ 승인", "callback_data": approve_cb},
            {"text": "❌ 거부", "callback_data": reject_cb},
        ]]
    }


async def send_strategy_proposal(pid: str, summary: str) -> dict:
    """전략 진화 제안 + 승인/거부 버튼."""
    return await send_message(
        summary,
        reply_markup=_approval_keyboard(f"evo_approve_{pid}", f"evo_reject_{pid}"),
    )


async def send_hil_order(order_id: str, summary: str) -> dict:
    """주문 HiL 승인 요청 + 버튼."""
    return await send_message(
        summary,
        reply_markup=_approval_keyboard(f"order_approve_{order_id}", f"order_reject_{order_id}"),
    )
