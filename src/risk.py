"""
risk.py — protects the account from blowing up.

Three layers of protection:
  1. Stop-loss     — auto-sell if price drops X% below entry
  2. Session limit — halt trading if total session loss hits X%
  3. Pre-trade check — blocks a new trade if we're already too deep in loss

All thresholds are set in config.py so they're easy to tune.
"""

import logging
from src.config import STOP_LOSS_PCT, MAX_SESSION_LOSS_PCT

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self):
        self.session_start_balance: float | None = None   # set once on startup
        self.current_balance: float | None = None
        self.trading_halted: bool = False

    def set_session_balance(self, balance: float) -> None:
        """Call once at startup with the account's starting USDT balance."""
        self.session_start_balance = balance
        self.current_balance = balance
        logger.info(f"Session starting balance: {balance:,.2f} USDT")

    def update_balance(self, new_balance: float) -> None:
        """Update after each trade so drawdown stays current."""
        self.current_balance = new_balance

    # ── Stop-loss check ──────────────────────────────────────────

    def is_stop_loss_triggered(self, entry_price: float, current_price: float) -> bool:
        """
        Returns True if current price has fallen more than STOP_LOSS_PCT
        below the entry price of the current long position.

        e.g. entry=68000, current=66640, STOP_LOSS_PCT=2.0 → triggered (drop > 2%)
        """
        if entry_price <= 0:
            return False

        drop_pct = ((entry_price - current_price) / entry_price) * 100

        if drop_pct >= STOP_LOSS_PCT:
            logger.warning(
                f"STOP-LOSS triggered — entry={entry_price:,.4f}  "
                f"current={current_price:,.4f}  drop={drop_pct:.2f}%  "
                f"(limit={STOP_LOSS_PCT}%)"
            )
            return True

        return False

    # ── Session drawdown check ───────────────────────────────────

    def is_session_limit_hit(self) -> bool:
        """
        Returns True if total session loss has exceeded MAX_SESSION_LOSS_PCT.
        When triggered, sets trading_halted=True and won't reset until restart.
        """
        if self.trading_halted:
            return True

        if self.session_start_balance is None or self.current_balance is None:
            return False

        loss_pct = (
            (self.session_start_balance - self.current_balance)
            / self.session_start_balance
        ) * 100

        if loss_pct >= MAX_SESSION_LOSS_PCT:
            self.trading_halted = True
            logger.error(
                f"SESSION LOSS LIMIT HIT — started={self.session_start_balance:,.2f}  "
                f"now={self.current_balance:,.2f}  loss={loss_pct:.2f}%  "
                f"(limit={MAX_SESSION_LOSS_PCT}%) — trading halted for this session"
            )
            return True

        return False

    # ── Pre-trade gate ───────────────────────────────────────────

    def can_trade(self) -> bool:
        """
        Returns False if trading should be blocked (session limit hit).
        Call this before executing any order.
        """
        if self.trading_halted:
            logger.warning("Trading is halted — skipping order")
            return False
        return True

    # ── Session summary ──────────────────────────────────────────

    def session_summary(self) -> None:
        if self.session_start_balance is None:
            return
        change = (self.current_balance or 0) - self.session_start_balance
        pct = (change / self.session_start_balance) * 100
        symbol = "+" if change >= 0 else ""
        logger.info(
            f"Risk summary — start={self.session_start_balance:,.2f}  "
            f"end={self.current_balance:,.2f}  "
            f"P&L={symbol}{change:,.2f} USDT ({symbol}{pct:.2f}%)"
        )
