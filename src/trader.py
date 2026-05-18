"""
trader.py — places market orders, enforces risk rules, and tracks performance.

Flow for each tick:
  1. If in position → check stop-loss → force-sell if triggered
  2. If signal is BUY/SELL → check risk gate → place order → record in performance
"""

import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.strategy import BUY, SELL, HOLD
from src.risk import RiskManager
from src.performance import PerformanceTracker
from src.config import TRADE_QUANTITY, USE_TESTNET, STOP_LOSS_PCT
from src.state import bot_state
import src.notifier as notifier

logger = logging.getLogger(__name__)

IN_POSITION  = "IN_POSITION"
OUT_POSITION = "OUT_POSITION"


class Trader:
    def __init__(self, client: Client, symbol: str,
                 risk: RiskManager, performance: PerformanceTracker):
        self.client      = client
        self.symbol      = symbol
        self.risk        = risk
        self.performance = performance
        self.position    = OUT_POSITION
        self.entry_price: float = 0.0

    def tick(self, signal: str, current_price: float) -> None:
        """
        Called every loop iteration. Handles stop-loss first, then strategy signal.
        """
        # 1. Stop-loss check (only relevant while holding a position)
        if self.position == IN_POSITION:
            if self.risk.is_stop_loss_triggered(self.entry_price, current_price):
                logger.warning("Executing emergency stop-loss sell")
                drop_pct = ((self.entry_price - current_price) / self.entry_price) * 100
                notifier.notify_stop_loss(self.symbol, self.entry_price, current_price, drop_pct)
                self._place_order(Client.SIDE_SELL, current_price, reason="STOP-LOSS")
                return

        # 2. Session loss guard
        if not self.risk.can_trade():
            return

        # 3. Strategy signal
        if signal == BUY and self.position == OUT_POSITION:
            self._place_order(Client.SIDE_BUY, current_price, reason="SIGNAL")

        elif signal == SELL and self.position == IN_POSITION:
            self._place_order(Client.SIDE_SELL, current_price, reason="SIGNAL")

        elif signal == HOLD:
            pass  # nothing to do

        elif signal == BUY and self.position == IN_POSITION:
            logger.debug("BUY signal but already in position — skipping")

        elif signal == SELL and self.position == OUT_POSITION:
            logger.debug("SELL signal but no position to sell — skipping")

    def _place_order(self, side: str, price: float, reason: str = "") -> None:
        mode = "TESTNET" if USE_TESTNET else "LIVE"
        tag  = f"[{reason}]" if reason else ""

        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=TRADE_QUANTITY,
            )

            order_id = str(order.get("orderId", ""))
            status   = order.get("status", "")

            logger.info(
                f"[{mode}]{tag} {side} {TRADE_QUANTITY} {self.symbol} "
                f"@ ~{price:,.4f} | order_id={order_id} status={status}"
            )

            # Update position state
            if side == Client.SIDE_BUY:
                self.position    = IN_POSITION
                self.entry_price = price
                self.performance.record_buy(price, TRADE_QUANTITY, order_id)
                notifier.notify_buy(self.symbol, price, TRADE_QUANTITY)
                bot_state.update(in_position=True, entry_price=price)
                bot_state.add_trade({
                    "timestamp": self.performance.trades[-1].timestamp if self.performance.trades else "",
                    "side": "BUY", "price": price,
                    "quantity": TRADE_QUANTITY, "pnl": None,
                })
            else:
                self.position    = OUT_POSITION
                self.performance.record_sell(price, TRADE_QUANTITY, order_id)
                trade_pnl = self.performance.trades[-1].pnl if self.performance.trades else 0.0
                notifier.notify_sell(self.symbol, price, TRADE_QUANTITY, trade_pnl)
                self.entry_price = 0.0
                bot_state.update(
                    in_position=False, entry_price=None,
                    total_pnl=self.performance.total_pnl,
                    wins=self.performance.wins,
                    losses=self.performance.losses,
                )
                bot_state.add_trade({
                    "timestamp": self.performance.trades[-1].timestamp if self.performance.trades else "",
                    "side": "SELL", "price": price,
                    "quantity": TRADE_QUANTITY, "pnl": trade_pnl,
                })

        except BinanceAPIException as e:
            logger.error(f"Order failed ({side} {self.symbol}): {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error placing order: {e}")

    def summary(self) -> None:
        self.performance.summary()
        self.risk.session_summary()
