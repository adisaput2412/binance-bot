"""
strategy.py — generates BUY / SELL / HOLD signals.

Uses a combined SMA crossover + RSI filter + Sentiment guard:
  BUY  — short SMA crosses above long SMA  AND  RSI < 70  AND  sentiment != BEARISH
  SELL — short SMA crosses below long SMA  AND  RSI > 30  AND  sentiment != BULLISH
  HOLD — signals don't agree, crossover blocked by sentiment, or no crossover

Sentiment is refreshed every 15 minutes in main.py (Fear & Greed + Google News).
"""

import logging

logger = logging.getLogger(__name__)

# Signal constants
BUY  = "BUY"
SELL = "SELL"
HOLD = "HOLD"

# RSI thresholds for confirmation
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30


def get_signal(indicators: dict, prev_indicators: dict | None,
               sentiment: dict | None = None) -> str:
    """
    Compares current and previous indicator readings to detect a crossover,
    then applies sentiment as a final gate before firing the signal.

    Args:
        indicators:      current period's indicator dict
        prev_indicators: previous period's indicator dict (or None on first run)
        sentiment:       dict from sentiment.get_sentiment() or None (ignored if None)

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

    verdict = sentiment.get("verdict", "NEUTRAL") if sentiment else "NEUTRAL"
    fg_value = sentiment.get("fg_value", 50) if sentiment else 50
    fg_label = sentiment.get("fg_label", "Unknown") if sentiment else "Unknown"

    # Detect crossover direction
    was_below = prev_short <= prev_long
    now_above = curr_short > curr_long
    was_above = prev_short >= prev_long
    now_below = curr_short < curr_long

    signal = HOLD

    if was_below and now_above:
        # Bullish crossover
        if curr_rsi >= RSI_OVERBOUGHT:
            logger.info(f"Crossover up but RSI={curr_rsi} overbought — holding")

        elif verdict == "BEARISH":
            logger.info(
                f"Crossover up blocked — sentiment BEARISH "
                f"(F&G={fg_value} {fg_label}) — holding"
            )

        else:
            signal = BUY
            logger.info(
                f"BUY signal  | price={curr_close:,.4f}  "
                f"SMA({curr_short:.4f})>SMA({curr_long:.4f})  "
                f"RSI={curr_rsi}  Sentiment={verdict} (F&G={fg_value})"
            )

    elif was_above and now_below:
        # Bearish crossover
        if curr_rsi <= RSI_OVERSOLD:
            logger.info(f"Crossover down but RSI={curr_rsi} oversold — holding")

        elif verdict == "BULLISH":
            logger.info(
                f"Crossover down blocked — sentiment BULLISH "
                f"(F&G={fg_value} {fg_label}) — holding"
            )

        else:
            signal = SELL
            logger.info(
                f"SELL signal | price={curr_close:,.4f}  "
                f"SMA({curr_short:.4f})<SMA({curr_long:.4f})  "
                f"RSI={curr_rsi}  Sentiment={verdict} (F&G={fg_value})"
            )

    else:
        logger.debug(
            f"HOLD | price={curr_close:,.4f}  "
            f"SMA_s={curr_short:.4f}  SMA_l={curr_long:.4f}  "
            f"RSI={curr_rsi}  Sentiment={verdict}"
        )

    return signal
