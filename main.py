"""
main.py — Binance Bot Core entry point.

Starts a web dashboard at http://localhost:5000 then runs the trading loop.

Before running:
  1. Fill in .env with testnet keys (see env-template.env.txt)
  2. pip install -r requirements.txt
  3. python main.py
  4. Open http://localhost:5000 in your browser
"""

import logging
import time
import threading

from src.client import get_client, check_connection
from src.indicators import get_indicators
from src.strategy import get_signal
from src.risk import RiskManager
from src.performance import PerformanceTracker
from src.trader import Trader
from src.data import get_account_balance
from src.state import bot_state
from src.sentiment import get_sentiment
import src.notifier as notifier
from dashboard.app import run_dashboard
from src.config import (
    USE_TESTNET,
    TRADE_SYMBOL,
    TRADE_INTERVAL,
    FETCH_INTERVAL,
    SMA_SHORT,
    SMA_LONG,
    RSI_PERIOD,
    STOP_LOSS_PCT,
    MAX_SESSION_LOSS_PCT,
)

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _update_sentiment_state(s: dict) -> None:
    if not s:
        return
    bot_state.update(
        sentiment_verdict=s.get("verdict", "NEUTRAL"),
        sentiment_fg_value=s.get("fg_value"),
        sentiment_fg_label=s.get("fg_label"),
        sentiment_news=s.get("headlines", []),
        sentiment_updated=s.get("updated_at"),
    )


def get_usdt_balance(client) -> float:
    balances = get_account_balance(client)
    for b in balances:
        if b["asset"] == "USDT":
            return float(b["free"])
    return 0.0


def main():
    mode = "TESTNET" if USE_TESTNET else "LIVE"
    logger.info(f"=== Binance Bot Core starting ({mode}) ===")
    logger.info(f"Symbol: {TRADE_SYMBOL}  |  Interval: {TRADE_INTERVAL}  |  Tick: every {FETCH_INTERVAL}s")
    logger.info(f"Strategy : SMA({SMA_SHORT}/{SMA_LONG}) crossover + RSI({RSI_PERIOD}) filter")
    logger.info(f"Risk     : stop-loss={STOP_LOSS_PCT}%  |  max session loss={MAX_SESSION_LOSS_PCT}%")

    # ── Start dashboard in background thread ──────────────────────
    dash_thread = threading.Thread(
        target=run_dashboard,
        kwargs={"host": "0.0.0.0", "port": 5000},
        daemon=True,
    )
    dash_thread.start()
    logger.info("Dashboard running at http://localhost:5000")

    # ── Seed initial state ────────────────────────────────────────
    bot_state.update(
        status="starting",
        mode=mode,
        symbol=TRADE_SYMBOL,
        interval=TRADE_INTERVAL,
    )

    # ── Connect ───────────────────────────────────────────────────
    client = get_client()
    if not check_connection(client):
        logger.error("Could not connect to Binance. Check your API keys and network.")
        bot_state.update(status="stopped")
        return

    # ── Set up risk + performance ─────────────────────────────────
    risk        = RiskManager()
    performance = PerformanceTracker()
    trader      = Trader(client, TRADE_SYMBOL, risk, performance)

    starting_usdt = get_usdt_balance(client)
    risk.set_session_balance(starting_usdt)

    bot_state.update(
        status="running",
        starting_balance=starting_usdt,
        current_balance=starting_usdt,
    )

    notifier.notify_bot_start(TRADE_SYMBOL, TRADE_INTERVAL, mode)

    prev_indicators  = None
    current_sentiment = None
    sentiment_ticks   = 0
    SENTIMENT_EVERY   = 90   # refresh sentiment every 90 ticks × 10s = 15 minutes

    # Fetch sentiment once on startup
    logger.info("Fetching initial sentiment...")
    current_sentiment = get_sentiment()
    _update_sentiment_state(current_sentiment)

    logger.info("Bot is live — open http://localhost:5000 — Ctrl+C to stop\n")

    try:
        while True:
            # Refresh sentiment every 15 minutes
            sentiment_ticks += 1
            if sentiment_ticks >= SENTIMENT_EVERY:
                current_sentiment = get_sentiment()
                _update_sentiment_state(current_sentiment)
                sentiment_ticks = 0

            indicators = get_indicators(
                client,
                symbol=TRADE_SYMBOL,
                interval=TRADE_INTERVAL,
                sma_short=SMA_SHORT,
                sma_long=SMA_LONG,
                rsi_period=RSI_PERIOD,
            )

            if indicators:
                current_price = indicators["close"]

                usdt_now = get_usdt_balance(client)
                risk.update_balance(usdt_now)

                # Update dashboard state every tick
                bot_state.update(
                    price=current_price,
                    sma_short=indicators["sma_short"],
                    sma_long=indicators["sma_long"],
                    rsi=indicators["rsi"],
                    current_balance=usdt_now,
                    total_pnl=performance.total_pnl,
                    wins=performance.wins,
                    losses=performance.losses,
                )

                if not risk.is_session_limit_hit():
                    signal = get_signal(indicators, prev_indicators, current_sentiment)
                    bot_state.update(last_signal=signal)
                    trader.tick(signal, current_price)
                else:
                    bot_state.update(status="halted")
                    notifier.notify_session_halted(MAX_SESSION_LOSS_PCT)

                prev_indicators = indicators

            time.sleep(FETCH_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\nBot stopped by user.")
        bot_state.update(status="stopped")
        trader.summary()
        notifier.notify_bot_stop(
            pnl=performance.total_pnl,
            trades=len(performance.trades),
        )


if __name__ == "__main__":
    main()
