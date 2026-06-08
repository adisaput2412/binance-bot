"""
trader.py — places market orders, enforces risk rules, and tracks performance.

Flow for each tick:
  1. If in position → check stop-loss → force-sell if triggered
  2. If signal is BUY/SELL → check risk gate → place order → record in performance
  3. Every trade is saved to trade_history.json so it survives restarts.
"""

import logging
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.strategy import BUY, SELL, HOLD
from src.risk import RiskManager
from src.performance import PerformanceTracker
from src.config import USE_TESTNET, STOP_LOSS_PCT, TAKE_PROFIT_PCT
from src.state import bot_state
import src.notifier as notifier
import src.trade_log as trade_log

logger = logging.getLogger(__name__)

IN_POSITION  = "IN_POSITION"
OUT_POSITION = "OUT_POSITION"


class Trader:
    def __init__(self, client: Client, symbol: str, quantity: float,
                 risk: RiskManager, performance: PerformanceTracker):
        self.client      = client
        self.symbol      = symbol
        self.quantity    = quantity   # per-pair trade size
        self.risk        = risk
        self.performance = performance
        self.position    = OUT_POSITION
        self.entry_price: float = 0.0

    def tick(self, signal: str, current_price: float) -> None:
        # 1. Stop-loss check
        if self.position == IN_POSITION:
            if self.risk.is_stop_loss_triggered(self.entry_price, current_price):
                logger.warning(f"[{self.symbol}] Stop-loss triggered")
                drop_pct = ((self.entry_price - current_price) / self.entry_price) * 100
                notifier.notify_stop_loss(self.symbol, self.entry_price, current_price, drop_pct)
                self._place_order(Client.SIDE_SELL, current_price, reason="STOP-LOSS")
                return

        # 1b. Take-profit check
        if self.position == IN_POSITION and self.entry_price > 0:
            rise_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            if rise_pct >= TAKE_PROFIT_PCT:
                logger.info(f"[{self.symbol}] Take-profit triggered (+{rise_pct:.2f}%)")
                self._place_order(Client.SIDE_SELL, current_price, reason="TAKE-PROFIT")
                return

        # 2. Session loss guard
        if not self.risk.can_trade():
            bot_state.update_pair(self.symbol, status="halted")
            return

        # 3. Strategy signal
        if signal == BUY and self.position == OUT_POSITION:
            self._place_order(Client.SIDE_BUY, current_price, reason="SIGNAL")
        elif signal == SELL and self.position == IN_POSITION:
            self._place_order(Client.SIDE_SELL, current_price, reason="SIGNAL")
        elif signal == BUY and self.position == IN_POSITION:
            logger.debug(f"[{self.symbol}] BUY signal but already in position")
        elif signal == SELL and self.position == OUT_POSITION:
            logger.debug(f"[{self.symbol}] SELL signal but no position to sell")

    def _place_order(self, side: str, price: float, reason: str = "") -> None:
        mode = "TESTNET" if USE_TESTNET else "LIVE"
        tag  = f"[{reason}]" if reason else ""

        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=self.quantity,
            )
            order_id = str(order.get("orderId", ""))
            status   = order.get("status", "")
            ts       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            logger.info(
                f"[{mode}]{tag} {side} {self.quantity} {self.symbol} "
                f"@ ~{price:,.4f} | order_id={order_id} status={status}"
            )

            if side == Client.SIDE_BUY:
                self.position    = IN_POSITION
                self.entry_price = price
                self.performance.record_buy(price, self.quantity, order_id)
                notifier.notify_buy(self.symbol, price, self.quantity)
                bot_state.update_pair(self.symbol, in_position=True, entry_price=price)

                record = {
                    "symbol": self.symbol, "timestamp": ts,
                    "side": "BUY", "price": price,
                    "quantity": self.quantity, "pnl": None,
                    "reason": reason, "order_id": order_id,
                }
                bot_state.add_trade(record)
                trade_log.append_trade(record)   # ← persist to disk

            else:
                self.performance.record_sell(price, self.quantity, order_id)
                trade_pnl = self.performance.trades[-1].pnl if self.performance.trades else 0.0
                notifier.notify_sell(self.symbol, price, self.quantity, trade_pnl)
                self.position    = OUT_POSITION
                self.entry_price = 0.0
                bot_state.update_pair(
                    self.symbol,
                    in_position=False, entry_price=None,
                    total_pnl=self.performance.total_pnl,
                    wins=self.performance.wins,
                    losses=self.performance.losses,
                )
                record = {
                    "symbol": self.symbol, "timestamp": ts,
                    "side": "SELL", "price": price,
                    "quantity": self.quantity, "pnl": trade_pnl,
                    "reason": reason, "order_id": order_id,
                }
                bot_state.add_trade(record)
                trade_log.append_trade(record)   # ← persist to disk

        except BinanceAPIException as e:
            logger.error(f"Order failed ({side} {self.symbol}): {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error placing order on {self.symbol}: {e}")

    def summary(self) -> None:
        self.performance.summary()
        self.risk.session_summary()
