"""
performance.py — tracks P&L for every trade this session.

Records entry and exit prices, calculates profit/loss per trade,
and prints a clean summary when the bot stops.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    side: str          # "BUY" or "SELL"
    price: float
    quantity: float
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    order_id: str = ""
    pnl: float = 0.0   # filled in when the position closes


class PerformanceTracker:
    def __init__(self):
        self.trades: list[Trade] = []
        self.open_trade: Trade | None = None    # the BUY we're currently holding
        self.total_pnl: float = 0.0
        self.wins: int = 0
        self.losses: int = 0

    def record_buy(self, price: float, quantity: float, order_id: str = "") -> None:
        """Call when a BUY order is placed."""
        self.open_trade = Trade(
            side="BUY",
            price=price,
            quantity=quantity,
            order_id=order_id,
        )
        self.trades.append(self.open_trade)
        logger.info(f"[PERF] Opened position — BUY {quantity} @ {price:,.4f}")

    def record_sell(self, price: float, quantity: float, order_id: str = "") -> None:
        """
        Call when a SELL order is placed.
        Calculates P&L against the open BUY position.
        """
        sell = Trade(
            side="SELL",
            price=price,
            quantity=quantity,
            order_id=order_id,
        )
        self.trades.append(sell)

        if self.open_trade:
            gross_pnl = (price - self.open_trade.price) * quantity
            # rough fee estimate: 0.1% per side = 0.2% round-trip on testnet
            fee_est = (self.open_trade.price + price) * quantity * 0.001
            net_pnl = gross_pnl - fee_est

            sell.pnl = net_pnl
            self.total_pnl += net_pnl

            if net_pnl >= 0:
                self.wins += 1
                logger.info(
                    f"[PERF] Closed position — SELL @ {price:,.4f}  "
                    f"P&L=+{net_pnl:,.4f} USDT  (fee est: {fee_est:,.4f})"
                )
            else:
                self.losses += 1
                logger.info(
                    f"[PERF] Closed position — SELL @ {price:,.4f}  "
                    f"P&L={net_pnl:,.4f} USDT  (fee est: {fee_est:,.4f})"
                )

            self.open_trade = None
        else:
            logger.warning("[PERF] SELL recorded but no open BUY found — P&L not calculated")

    def summary(self) -> None:
        """Prints a full session summary."""
        total_trades = self.wins + self.losses
        win_rate = (self.wins / total_trades * 100) if total_trades > 0 else 0

        logger.info("=" * 55)
        logger.info("  SESSION PERFORMANCE SUMMARY")
        logger.info("=" * 55)
        logger.info(f"  Total trades  : {total_trades} ({self.wins}W / {self.losses}L)")
        logger.info(f"  Win rate      : {win_rate:.1f}%")
        pnl_sign = "+" if self.total_pnl >= 0 else ""
        logger.info(f"  Net P&L       : {pnl_sign}{self.total_pnl:,.4f} USDT (est. after fees)")

        if self.open_trade:
            logger.info(f"  Open position : BUY @ {self.open_trade.price:,.4f} (not yet closed)")

        logger.info("-" * 55)
        for t in self.trades:
            sign = "+" if t.pnl >= 0 else ""
            pnl_str = f"  P&L: {sign}{t.pnl:,.4f}" if t.side == "SELL" else ""
            logger.info(f"  {t.timestamp}  {t.side:4s}  {t.quantity} @ {t.price:,.4f}{pnl_str}")
        logger.info("=" * 55)
