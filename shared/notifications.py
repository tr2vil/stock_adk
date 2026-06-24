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


async def send_daily_report(report_date: str, trades: list[dict], open_positions: list[dict]) -> dict:
    """US 장 마감 후 일일 매매 결산 리포트 발송.

    Args:
        report_date: "2026-06-24" 형식 날짜
        trades:   오늘 체결된 거래 목록 (trade_log 레코드)
        open_positions: 현재 오픈 포지션 목록 [{symbol, entry_price, current_price, qty, signal_state}]
    """
    lines = [f"📊 일일 매매 결과 — {report_date} (US 시장)"]

    # ── 체결 내역 ──
    if trades:
        lines.append("")
        lines.append("── 오늘 거래 내역 ──────────────────")
        for t in trades:
            side = t.get("side", "")
            ticker = t.get("ticker", "")
            qty = t.get("quantity") or 0
            price = t.get("price") or 0
            rr = t.get("return_rate")
            action = t.get("signal", side.upper())

            if side == "buy":
                lines.append(f"🟢 {ticker}  매수 {qty}주 @${price:.2f}")
            else:
                rr_str = f"  ({rr * 100:+.1f}%)" if rr is not None else ""
                pnl = (price - (t.get("entry_price") or price)) * qty
                pnl_str = f"  {pnl:+.2f}" if t.get("entry_price") else ""
                label = "1차익절" if action == "SELL_HALF" else "전량청산"
                lines.append(f"🔴 {ticker}  {label} {qty}주 @${price:.2f}{rr_str}{pnl_str}")
    else:
        lines.append("")
        lines.append("── 오늘 거래 없음 ──────────────────")

    # ── 오픈 포지션 ──
    realized_pnl = 0.0
    unrealized_pnl = 0.0

    for t in trades:
        if t.get("side") == "sell" and t.get("entry_price") and t.get("price") and t.get("quantity"):
            realized_pnl += (t["price"] - t["entry_price"]) * t["quantity"]

    if open_positions:
        lines.append("")
        lines.append("── 오픈 포지션 ─────────────────────")
        for pos in open_positions:
            sym = pos.get("symbol", "")
            ep = pos.get("entry_price") or 0
            cp = pos.get("current_price") or 0
            qty = pos.get("qty") or 0
            state = pos.get("signal_state", "")
            unreal = (cp - ep) * qty if ep and cp and qty else 0
            unrealized_pnl += unreal
            sign = "+" if unreal >= 0 else ""
            lines.append(f"📌 {sym}  {qty}주 | 진입 ${ep:.2f} | 종가 ${cp:.2f} ({sign}${unreal:.2f} 미실현)")
    else:
        # 신호 대기 종목
        pass

    # 신호 대기 (IDLE/QUEUED)
    waiting = [p for p in open_positions if "IDLE" in p.get("signal_state", "") or "QUEUE" in p.get("signal_state", "")]
    if waiting:
        lines.append("")
        lines.append("── 신호 대기 ───────────────────────")
        for p in waiting:
            state_label = {
                "IDLE": "대기 중",
                "M1_QUEUED_RSI_LOW": "RSI 50 돌파 대기",
                "M1_QUEUED_RSI_HIGH": "눌림목 대기",
                "M2_DIVERGENCE": "데드크로스 대기",
                "M2_COOLDOWN": "골든크로스 재전환 대기",
            }.get(p.get("signal_state", ""), p.get("signal_state", ""))
            lines.append(f"⏳ {p.get('symbol')}  {state_label}")

    # ── 요약 ──
    lines.append("")
    lines.append("── 요약 ────────────────────────────")
    r_sign = "+" if realized_pnl >= 0 else ""
    u_sign = "+" if unrealized_pnl >= 0 else ""
    total = realized_pnl + unrealized_pnl
    t_sign = "+" if total >= 0 else ""
    lines.append(f"실현 손익   {r_sign}${realized_pnl:.2f}")
    lines.append(f"미실현 손익 {u_sign}${unrealized_pnl:.2f}")
    lines.append("─────────────────────────────")
    lines.append(f"총 평가     {t_sign}${total:.2f}")

    return await send_message("\n".join(lines))
