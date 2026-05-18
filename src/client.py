"""
client.py — creates and returns a Binance client.
Automatically uses testnet if USE_TESTNET=true in your .env.
"""

import logging
import time
from binance.client import Client
from src.config import API_KEY, API_SECRET, USE_TESTNET

logger = logging.getLogger(__name__)

# Testnet can be slow — give it a generous timeout
REQUEST_TIMEOUT = 30   # seconds


def get_client() -> Client:
    """
    Returns an authenticated Binance client with extended timeout.
    Points to testnet if USE_TESTNET is true.
    """
    if not API_KEY or not API_SECRET:
        raise ValueError(
            "Missing API keys. Copy env-template.txt to .env and fill in your testnet keys.\n"
            "Get them at: https://testnet.binance.vision/"
        )

    client = Client(
        API_KEY,
        API_SECRET,
        testnet=USE_TESTNET,
        requests_params={"timeout": REQUEST_TIMEOUT},
    )

    mode = "TESTNET" if USE_TESTNET else "LIVE"
    logger.info(f"Binance client connected ({mode}) — timeout={REQUEST_TIMEOUT}s")

    return client


def check_connection(client: Client, retries: int = 3) -> bool:
    """
    Pings Binance to confirm the connection is working.
    Retries up to `retries` times before giving up.
    """
    for attempt in range(1, retries + 1):
        try:
            client.ping()
            server_time = client.get_server_time()
            logger.info(f"Connection OK — server time: {server_time['serverTime']}")
            return True
        except Exception as e:
            logger.warning(f"Connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(3)

    logger.error("Could not connect to Binance after all retries.")
    return False
