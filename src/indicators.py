"""
indicators.py — calculates SMA, RSI, and ADX from Binance kline (candlestick) data.

No external libraries needed — pure Python math.
"""

import logging
import time
from binance.client import Client

logger = logging.getLogger(__name__)


def get_klines_ohlc(client: Client, symbol: str, interval: str,
                    limit: int = 100, retries: int = 3) -> dict:
    """
    Fetches the last `limit` candles for a symbol/interval as parallel
    high/low/close lists. Retries on timeout — testnet can be slow.

    interval options: Client.KLINE_INTERVAL_1MINUTE, _5MINUTE, _15MINUTE, _1HOUR, etc.
    """
    for attempt in range(1, retries + 1):
        try:
            klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
            return {
                "high":  [float(k[2]) for k in klines],
                "low":   [float(k[3]) for k in klines],
                "close": [float(k[4]) for k in klines],
            }
        except Exception as e:
            logger.warning(f"Kline fetch attempt {attempt}/{retries} failed for {symbol}: {e}")
            if attempt < retries:
                time.sleep(5)

    logger.error(f"Failed to fetch klines for {symbol} after {retries} attempts — skipping tick")
    return {"high": [], "low": [], "close": []}


def get_closing_prices(client: Client, symbol: str, interval: str,
                       limit: int = 100, retries: int = 3) -> list[float]:
    """Back-compat wrapper — closes only."""
    return get_klines_ohlc(client, symbol, interval, limit, retries)["close"]


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


def _ewm(values: list[float], alpha: float) -> list[float]:
    """Exponential smoothing with adjust=False semantics (matches Wilder's method
    when alpha = 1/period) — kept dependency-free to mirror pandas .ewm() used
    in backtest.py so live and backtest ADX values line up."""
    result = [values[0]]
    for v in values[1:]:
        result.append(result[-1] * (1 - alpha) + v * alpha)
    return result


def adx(highs: list[float], lows: list[float], closes: list[float],
       period: int = 14) -> float | None:
    """
    Average Directional Index — measures trend STRENGTH (not direction).
    Used as a chop filter: below ~20 the market is ranging and SMA
    crossovers tend to whipsaw; above ~25 a real trend is underway.

    Returns a value 0-100, or None if not enough data.
    """
    n = len(closes)
    if n < period + 2:
        return None

    trs, plus_dms, minus_dms = [], [], []
    for i in range(1, n):
        high, low, prev_close = highs[i], lows[i], closes[i - 1]
        prev_high, prev_low = highs[i - 1], lows[i - 1]

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

        up_move   = high - prev_high
        down_move = prev_low - low
        plus_dm  = up_move   if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        plus_dms.append(plus_dm)
        minus_dms.append(minus_dm)

    alpha = 1 / period
    tr_s       = _ewm(trs, alpha)
    plus_dm_s  = _ewm(plus_dms, alpha)
    minus_dm_s = _ewm(minus_dms, alpha)

    dx_values = []
    for tr_v, pdm_v, mdm_v in zip(tr_s, plus_dm_s, minus_dm_s):
        if tr_v == 0:
            dx_values.append(0.0)
            continue
        plus_di  = 100 * pdm_v / tr_v
        minus_di = 100 * mdm_v / tr_v
        di_sum   = plus_di + minus_di
        dx_values.append(100 * abs(plus_di - minus_di) / di_sum if di_sum else 0.0)

    if len(dx_values) < period:
        return None

    adx_series = _ewm(dx_values, alpha)
    return round(adx_series[-1], 2)


def get_indicators(client: Client, symbol: str, interval: str,
                   sma_short: int = 9, sma_long: int = 21,
                   rsi_period: int = 14, adx_period: int = 14) -> dict:
    """
    Fetches klines and returns a dict of current indicator values.

    Returns:
        {
            'close':     float,   # latest closing price
            'sma_short': float,   # short SMA (e.g. 9-period)
            'sma_long':  float,   # long SMA  (e.g. 21-period)
            'rsi':       float,   # RSI value (0–100)
            'adx':       float,   # trend-strength filter (0–100)
        }
    Returns empty dict if data fetch fails.
    """
    limit = max(sma_long, rsi_period, adx_period * 2) + 10  # a bit of buffer
    ohlc = get_klines_ohlc(client, symbol, interval, limit=limit)
    closes = ohlc["close"]

    if not closes:
        return {}

    short   = sma(closes, sma_short)
    long_   = sma(closes, sma_long)
    rsi_val = rsi(closes, rsi_period)
    adx_val = adx(ohlc["high"], ohlc["low"], closes, adx_period)

    if any(v is None for v in [short, long_, rsi_val, adx_val]):
        logger.warning("Not enough data to calculate indicators yet — waiting for more candles")
        return {}

    return {
        "close":     closes[-1],
        "sma_short": round(short, 4),
        "sma_long":  round(long_, 4),
        "rsi":       rsi_val,
        "adx":       adx_val,
    }
