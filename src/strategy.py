"""
strategy.py — generates BUY / SELL / HOLD signals.

Uses a combined SMA crossover + RSI filter:
  BUY  — short SMA crosses above long SMA  AND  RSI < 60  (not overbought)
  SELL — short SMA crosses below long SMA  AND  RSI > 40  (not oversold)
  HOLD — signals don't agree, or no crossover

Requiring BOTH indicators to agree dramatically reduces false signals.
"""

import logging

logger = logging.getLogger(__name__)

# Signal constants
BUY  = "BUY"
SELL = "SELL"
HOLD = "HOLD"

# RSI thresholds for confirmation
RSI_OVERBOUGHT = 70   # avoid buying when already overbought
RSI_OVERSOLD   = 30   # avoid selling when already oversold


def get_signal(indicators: dict, prev_indicators: dict | None) -> str:
    """
    Compares current and previous indicator readings to detect a crossover.

    Args:
        indicators:      current period's indicator dict from indicators.get_indicators()
        prev_indicators: previous period's indicator dict (or None on first run)

    Returns:
        "BUY", "SELL", or "HOLD"
    """
    if not indicators:
        logger.warning("No indicator data — holding")
        return HOLD

    if not prev_indicators:
        logger.info("No previous candle yet — holding (need at least 2 candles)")
        return HOLD

    curr_short = indicators["sma_short"]
    curr_long  = indicators["sma_long"]
    prev_short = prev_indicators["sma_short"]
    prev_long  = prev_indicators["sma_long"]
    curr_rsi   = indicators["rsi"]
    curr_close = indicators["close"]

    # Detect crossover direction
    was_below = prev_short <= prev_long
    now_above = curr_short > curr_long

    was_above = prev_short >= prev_long
    now_below = curr_short < curr_long

    signal = HOLD

    if was_below and now_above:
        # Short SMA crossed above long → bullish crossover
        if curr_rsi < RSI_OVERBOUGHT:
            signal = BUY
            logger.info(
                f"BUY signal  | price={curr_close:,.4f}  "
                f"SMA({curr_short:.4f}) > SMA({curr_long:.4f})  RSI={curr_rsi}"
            )
        else:
            logger.info(
                f"Crossover up but RSI={curr_rsi} too overbought — holding"
            )

    elif was_above and now_below:
        # Short SMA crossed below long → bearish crossover
        if curr_rsi > RSI_OVERSOLD:
            signal = SELL
            logger.info(
                f"SELL signal | price={curr_close:,.4f}  "
                f"SMA({curr_short:.4f}) < SMA({curr_long:.4f})  RSI={curr_rsi}"
            )
        else:
            logger.info(
                f"Crossover down but RSI={curr_rsi} too oversold — holding"
            )

    else:
        logger.debug(
            f"HOLD | price={curr_close:,.4f}  "
            f"SMA_short={curr_short:.4f}  SMA_long={curr_long:.4f}  RSI={curr_rsi}"
        )

    return signal
