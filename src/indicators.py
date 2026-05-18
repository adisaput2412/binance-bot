"""
indicators.py — calculates SMA and RSI from Binance kline (candlestick) data.

No external libraries needed — pure Python math.
"""

import logging
import time
from binance.client import Client

logger = logging.getLogger(__name__)


def get_closing_prices(client: Client, symbol: str, interval: str,
                       limit: int = 100, retries: int = 3) -> list[float]:
    """
    Fetches the last `limit` closing prices for a symbol and interval.
    Retries on timeout — testnet can be slow.

    interval options: Client.KLINE_INTERVAL_1MINUTE, _5MINUTE, _15MINUTE, _1HOUR, etc.
    """
    for attempt in range(1, retries + 1):
        try:
            klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
            closes = [float(k[4]) for k in klines]  # index 4 = close price
            return closes
        except Exception as e:
            logger.warning(f"Kline fetch attempt {attempt}/{retries} failed for {symbol}: {e}")
            if attempt < retries:
                time.sleep(5)

    logger.error(f"Failed to fetch klines for {symbol} after {retries} attempts — skipping tick")
    return []


def sma(prices: list[float], period: int) -> float | None:
    """
    Simple Moving Average over the last `period` prices.
    Returns None if not enough data.
    """
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def rsi(prices: list[float], period: int = 14) -> float | None:
    """
    Relative Strength Index over the last `period` prices.
    Returns a value between 0–100. Returns None if not enough data.

    > 70 = overbought (consider selling)
    < 30 = oversold   (consider buying)
    """
    if len(prices) < period + 1:
        return None

    closes = prices[-(period + 1):]
    gains, losses = [], []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0  # no losses = max overbought

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def get_indicators(client: Client, symbol: str, interval: str,
                   sma_short: int = 9, sma_long: int = 21,
                   rsi_period: int = 14) -> dict:
    """
    Fetches klines and returns a dict of current indicator values.

    Returns:
        {
            'close':     float,   # latest closing price
            'sma_short': float,   # short SMA (e.g. 9-period)
            'sma_long':  float,   # long SMA  (e.g. 21-period)
            'rsi':       float,   # RSI value (0–100)
        }
    Returns empty dict if data fetch fails.
    """
    limit = max(sma_long, rsi_period) + 10  # a bit of buffer
    prices = get_closing_prices(client, symbol, interval, limit=limit)

    if not prices:
        return {}

    short = sma(prices, sma_short)
    long_ = sma(prices, sma_long)
    rsi_val = rsi(prices, rsi_period)

    if any(v is None for v in [short, long_, rsi_val]):
        logger.warning("Not enough data to calculate indicators yet — waiting for more candles")
        return {}

    return {
        "close":     prices[-1],
        "sma_short": round(short, 4),
        "sma_long":  round(long_, 4),
        "rsi":       rsi_val,
    }
