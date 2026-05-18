"""
data.py — fetches live price data from Binance.
"""

import logging
from binance.client import Client
from src.config import WATCH_PAIRS

logger = logging.getLogger(__name__)


def get_price(client: Client, symbol: str) -> float | None:
    """
    Returns the latest price for a trading pair (e.g. 'BTCUSDT').
    Returns None if the request fails.
    """
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker["price"])
        logger.debug(f"{symbol}: {price}")
        return price
    except Exception as e:
        logger.error(f"Failed to get price for {symbol}: {e}")
        return None


def get_all_prices(client: Client) -> dict[str, float]:
    """
    Returns a dict of current prices for all pairs in WATCH_PAIRS.
    e.g. {'BTCUSDT': 68000.5, 'ETHUSDT': 3500.2, ...}
    """
    prices = {}
    for symbol in WATCH_PAIRS:
        price = get_price(client, symbol)
        if price is not None:
            prices[symbol] = price
    return prices


def get_account_balance(client: Client) -> list[dict]:
    """
    Returns non-zero balances from your testnet account.
    """
    try:
        account = client.get_account()
        balances = [
            b for b in account["balances"]
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        ]
        return balances
    except Exception as e:
        logger.error(f"Failed to get account balance: {e}")
        return []
