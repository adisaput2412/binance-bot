"""
notifier.py — sends Telegram messages when the bot does something important.

Setup (one-time):
  1. Open Telegram → search @BotFather → send /newbot → follow prompts
     You'll get a token like: 7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  2. Start a chat with your new bot (click Start)
  3. Get your chat ID: visit this URL in your browser —
       https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     Look for "chat": {"id": 123456789} — that number is your TELEGRAM_CHAT_ID
  4. Add both to your .env file

If TELEGRAM_TOKEN is not set, notifications are silently skipped (bot still works).
"""

import logging
import requests
from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send(message: str) -> None:
    """
    Sends a Telegram message. Silently skips if token/chat_id not configured.
    Non-blocking — failures are logged but never crash the bot.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = TELEGRAM_API.format(token=TELEGRAM_TOKEN)
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=5,
        )
        if not resp.ok:
            logger.warning(f"Telegram send failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Telegram error (non-fatal): {e}")


# ── Pre-built message templates ────────────────────────────────────

def notify_bot_start(symbol: str, interval: str, mode: str) -> None:
    send(
        f"<b>Bot started</b>\n"
        f"Symbol: {symbol} | Interval: {interval} | Mode: {mode}"
    )


def notify_bot_stop(pnl: float, trades: int) -> None:
    sign = "+" if pnl >= 0 else ""
    send(
        f"<b>Bot stopped</b>\n"
        f"Session P&amp;L: <b>{sign}{pnl:.4f} USDT</b> | Trades: {trades}"
    )


def notify_buy(symbol: str, price: float, quantity: float) -> None:
    send(
        f"<b>BUY executed</b>\n"
        f"{quantity} {symbol} @ {price:,.4f} USDT"
    )


def notify_sell(symbol: str, price: float, quantity: float, pnl: float) -> None:
    sign  = "+" if pnl >= 0 else ""
    emoji = "green" if pnl >= 0 else "red"
    label = "PROFIT" if pnl >= 0 else "LOSS"
    send(
        f"<b>SELL executed — {label}</b>\n"
        f"{quantity} {symbol} @ {price:,.4f} USDT\n"
        f"Trade P&amp;L: <b>{sign}{pnl:.4f} USDT</b>"
    )


def notify_stop_loss(symbol: str, entry: float, current: float, drop_pct: float) -> None:
    send(
        f"<b>STOP-LOSS triggered</b>\n"
        f"{symbol} — entry={entry:,.4f} | now={current:,.4f} | drop={drop_pct:.2f}%"
    )


def notify_session_halted(loss_pct: float) -> None:
    send(
        f"<b>Trading halted — session loss limit hit</b>\n"
        f"Total loss: {loss_pct:.2f}% — restart the bot to resume"
    )
