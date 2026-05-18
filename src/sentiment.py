"""
sentiment.py — free market sentiment analysis, no API keys needed.

Sources:
  1. Fear & Greed Index (alternative.me) — single score 0–100
  2. Google News RSS — recent BTC/crypto/regulation headlines
     scored with bullish/bearish keywords

Returns a sentiment verdict: BULLISH, BEARISH, or NEUTRAL
which the strategy uses as an extra filter before trading.
"""

import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Keyword lists for news scoring ────────────────────────────────

BULLISH_WORDS = [
    "surge", "rally", "bullish", "breakout", "adoption", "approve", "approval",
    "legal", "etf", "institutional", "buy", "growth", "record", "high",
    "upgrade", "partnership", "launch", "positive", "optimistic", "recover",
    "rebound", "gain", "profit", "pump", "moon", "support", "accumulate",
    "hodl", "regulation clarity", "sec approve", "mainstream",
]

BEARISH_WORDS = [
    "crash", "ban", "bearish", "dump", "hack", "scam", "fraud", "lawsuit",
    "regulate", "crackdown", "restrict", "prohibit", "illegal", "fine",
    "penalty", "collapse", "fear", "sell", "plunge", "drop", "fall",
    "warning", "risk", "bubble", "ponzi", "money laundering", "arrest",
    "shutdown", "delist", "exploit", "vulnerability", "sec sue", "loss",
]

# ── Fear & Greed Index ─────────────────────────────────────────────

def get_fear_greed() -> dict:
    """
    Fetches the current Fear & Greed Index from alternative.me.
    Returns dict with 'value' (0-100) and 'label' (e.g. 'Extreme Fear').
    Returns None on failure.

    Scale:
      0–24   = Extreme Fear  (market very scared — potential buy opportunity)
      25–49  = Fear
      50–74  = Greed
      75–100 = Extreme Greed (market overheated — be careful buying)
    """
    try:
        resp = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            timeout=10,
        )
        data = resp.json()["data"][0]
        result = {
            "value":     int(data["value"]),
            "label":     data["value_classification"],
            "timestamp": data["timestamp"],
        }
        logger.info(f"Fear & Greed: {result['value']} ({result['label']})")
        return result
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return None


# ── Google News RSS ───────────────────────────────────────────────

def get_news_headlines(query: str = "bitcoin crypto regulation", limit: int = 10) -> list[str]:
    """
    Fetches recent headlines from Google News RSS feed.
    No API key needed.
    """
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(resp.content)
        headlines = []
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "")
            if title:
                headlines.append(title.lower())
        logger.info(f"Fetched {len(headlines)} headlines from Google News")
        return headlines
    except Exception as e:
        logger.warning(f"Google News fetch failed: {e}")
        return []


def score_headlines(headlines: list[str]) -> int:
    """
    Scores headlines using bullish/bearish keyword matching.
    Returns net score: positive = bullish, negative = bearish, 0 = neutral.
    """
    score = 0
    for headline in headlines:
        for word in BULLISH_WORDS:
            if word in headline:
                score += 1
        for word in BEARISH_WORDS:
            if word in headline:
                score -= 1
    return score


# ── Combined sentiment ────────────────────────────────────────────

def get_sentiment() -> dict:
    """
    Combines Fear & Greed Index + Google News to produce an overall sentiment.

    Returns:
        {
            'verdict':    'BULLISH' | 'BEARISH' | 'NEUTRAL',
            'fg_value':   int (0–100),
            'fg_label':   str,
            'news_score': int,
            'headlines':  list[str],
            'updated_at': str,
        }
    """
    fg = get_fear_greed()
    headlines = get_news_headlines("bitcoin crypto SEC regulation government")
    news_score = score_headlines(headlines)

    fg_value = fg["value"] if fg else 50   # default to neutral if fetch fails
    fg_label = fg["label"] if fg else "Unknown"

    # Combine: F&G weighted more than news keywords
    # F&G: <35 = bearish signal, >65 = bullish signal
    fg_vote = 0
    if fg_value <= 25:
        fg_vote = -2   # Extreme Fear
    elif fg_value <= 45:
        fg_vote = -1   # Fear
    elif fg_value >= 75:
        fg_vote = 2    # Extreme Greed
    elif fg_value >= 55:
        fg_vote = 1    # Greed

    total = fg_vote + (1 if news_score > 2 else -1 if news_score < -2 else 0)

    if total >= 2:
        verdict = "BULLISH"
    elif total <= -2:
        verdict = "BEARISH"
    else:
        verdict = "NEUTRAL"

    result = {
        "verdict":    verdict,
        "fg_value":   fg_value,
        "fg_label":   fg_label,
        "news_score": news_score,
        "headlines":  headlines[:5],   # top 5 for display
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    logger.info(
        f"Sentiment: {verdict} | F&G={fg_value} ({fg_label}) | "
        f"News score={news_score}"
    )
    return result
