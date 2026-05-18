"""
backtest.py — Historical backtest for the SMA + RSI strategy.

Fetches 3 months of 5m candles from Binance public API (no API keys needed)
and simulates the same strategy the live bot uses.

Usage:
    python backtest.py
    python backtest.py --days 90          # default
    python backtest.py --days 30          # shorter range
    python backtest.py --symbol BTCUSDT   # single pair only

Output:
    - Per-pair report in the terminal
    - trades_SYMBOL.csv saved to backtest_results/
    - backtest_summary.txt saved to backtest_results/
"""

import argparse
import csv
import os
import requests
from datetime import datetime, timedelta

# ── Try to import dependencies ────────────────────────────────────────
try:
    from binance.client import Client
except ImportError:
    print("ERROR: python-binance not installed. Run: pip install python-binance")
    raise

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Run: pip install pandas")
    raise

# ── Load config ───────────────────────────────────────────────────────
from src.config import TRADE_PAIRS, SMA_SHORT, SMA_LONG, RSI_PERIOD, STOP_LOSS_PCT

OUTPUT_DIR = "backtest_results"
INTERVAL   = "5m"
FEE_RATE   = 0.001   # 0.1% per trade (Binance standard)

# ── Binance public client (no keys needed for historical klines) ───────
client = Client("", "")


# ═══════════════════════════════════════════════════════════════════════
# Data fetching
# ═══════════════════════════════════════════════════════════════════════

def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    start = (datetime.now() - timedelta(days=days)).strftime("%d %b, %Y")
    print(f"  Fetching {symbol} {interval} candles from {start}...")
    klines = client.get_historical_klines(symbol, interval, start)
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df["close"]     = df["close"].astype(float)
    df["high"]      = df["high"].astype(float)
    df["low"]       = df["low"].astype(float)
    df["open"]      = df["open"].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    print(f"  ✓ {len(df):,} candles loaded")
    return df


# ═══════════════════════════════════════════════════════════════════════
# Indicators
# ═══════════════════════════════════════════════════════════════════════

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # SMA
    df["sma_short"] = df["close"].rolling(SMA_SHORT).mean()
    df["sma_long"]  = df["close"].rolling(SMA_LONG).mean()

    # RSI (Wilder's smoothing)
    delta    = df["close"].diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/RSI_PERIOD, min_periods=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/RSI_PERIOD, min_periods=RSI_PERIOD, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-10)
    df["rsi"] = 100 - (100 / (1 + rs))

    return df


# ═══════════════════════════════════════════════════════════════════════
# Signal logic (mirrors src/strategy.py — no sentiment in backtest)
# ═══════════════════════════════════════════════════════════════════════

def get_signal(row, prev_row) -> str:
    if prev_row is None:
        return "HOLD"

    cross_up   = row["sma_short"] > row["sma_long"]  and prev_row["sma_short"] <= prev_row["sma_long"]
    cross_down = row["sma_short"] < row["sma_long"]  and prev_row["sma_short"] >= prev_row["sma_long"]

    if cross_up   and row["rsi"] < 70:
        return "BUY"
    if cross_down and row["rsi"] > 30:
        return "SELL"
    return "HOLD"


# ═══════════════════════════════════════════════════════════════════════
# Backtest engine
# ═══════════════════════════════════════════════════════════════════════

def run_backtest(symbol: str, df: pd.DataFrame, quantity: float,
                 initial_balance: float = 10_000.0) -> dict:

    rows       = df.dropna(subset=["sma_short", "sma_long", "rsi"]).reset_index(drop=True)
    in_pos     = False
    entry_price = 0.0
    balance    = initial_balance
    trades     = []
    equity_curve = [initial_balance]

    for i in range(1, len(rows)):
        row      = rows.iloc[i]
        prev_row = rows.iloc[i - 1]
        price    = row["close"]

        # ── Stop-loss ──────────────────────────────────────────────
        if in_pos:
            drop_pct = (entry_price - price) / entry_price * 100
            if drop_pct >= STOP_LOSS_PCT:
                fee = price * quantity * FEE_RATE
                pnl = (price - entry_price) * quantity - fee
                balance += pnl
                trades.append({
                    "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M"),
                    "side": "SELL", "reason": "STOP-LOSS",
                    "price": price, "quantity": quantity,
                    "pnl": round(pnl, 4),
                })
                in_pos = False
                entry_price = 0.0
                equity_curve.append(balance)
                continue

        # ── Strategy signal ────────────────────────────────────────
        signal = get_signal(row, prev_row)

        if signal == "BUY" and not in_pos:
            fee = price * quantity * FEE_RATE
            balance -= fee
            entry_price = price
            in_pos = True
            trades.append({
                "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "side": "BUY", "reason": "SIGNAL",
                "price": price, "quantity": quantity,
                "pnl": None,
            })

        elif signal == "SELL" and in_pos:
            fee = price * quantity * FEE_RATE
            pnl = (price - entry_price) * quantity - fee
            balance += pnl
            trades.append({
                "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "side": "SELL", "reason": "SIGNAL",
                "price": price, "quantity": quantity,
                "pnl": round(pnl, 4),
            })
            in_pos = False
            entry_price = 0.0
            equity_curve.append(balance)

    # Close open position at end of data
    if in_pos:
        price = rows.iloc[-1]["close"]
        fee   = price * quantity * FEE_RATE
        pnl   = (price - entry_price) * quantity - fee
        balance += pnl
        trades.append({
            "timestamp": rows.iloc[-1]["timestamp"].strftime("%Y-%m-%d %H:%M"),
            "side": "SELL", "reason": "END-OF-DATA",
            "price": price, "quantity": quantity,
            "pnl": round(pnl, 4),
        })
        equity_curve.append(balance)

    # ── Stats ──────────────────────────────────────────────────────
    sell_trades = [t for t in trades if t["side"] == "SELL" and t["pnl"] is not None]
    wins        = [t for t in sell_trades if t["pnl"] > 0]
    losses      = [t for t in sell_trades if t["pnl"] <= 0]
    total_pnl   = sum(t["pnl"] for t in sell_trades)
    win_rate    = len(wins) / len(sell_trades) * 100 if sell_trades else 0.0
    best_trade  = max((t["pnl"] for t in sell_trades), default=0.0)
    worst_trade = min((t["pnl"] for t in sell_trades), default=0.0)

    # Max drawdown
    peak = initial_balance
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    return {
        "symbol":          symbol,
        "total_trades":    len(sell_trades),
        "wins":            len(wins),
        "losses":          len(losses),
        "win_rate":        win_rate,
        "total_pnl":       round(total_pnl, 4),
        "best_trade":      round(best_trade, 4),
        "worst_trade":     round(worst_trade, 4),
        "max_drawdown_pct": round(max_dd, 2),
        "initial_balance": initial_balance,
        "final_balance":   round(balance, 2),
        "return_pct":      round((balance - initial_balance) / initial_balance * 100, 2),
        "trades":          trades,
        "equity_curve":    equity_curve,
    }


# ═══════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════

def print_result(r: dict) -> None:
    pnl_sign  = "+" if r["total_pnl"] >= 0 else ""
    ret_sign  = "+" if r["return_pct"] >= 0 else ""
    verdict   = "✅ PROFITABLE" if r["total_pnl"] > 0 else "❌ LOSING"

    print(f"""
  ┌─────────────────────────────────────────────┐
  │  {r['symbol']:<43}│
  ├─────────────────────────────────────────────┤
  │  Result      {verdict:<31}│
  │  Total P&L   {pnl_sign}{r['total_pnl']:.4f} USDT{'':<22}│
  │  Return      {ret_sign}{r['return_pct']:.2f}%{'':<30}│
  │  Trades      {r['total_trades']:<32}│
  │  Win rate    {r['win_rate']:.1f}%  ({r['wins']}W / {r['losses']}L){'':<17}│
  │  Best trade  +{r['best_trade']:.4f} USDT{'':<22}│
  │  Worst trade {r['worst_trade']:.4f} USDT{'':<22}│
  │  Max draw    -{r['max_drawdown_pct']:.2f}%{'':<29}│
  └─────────────────────────────────────────────┘""")


def save_trades_csv(r: dict) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"trades_{r['symbol']}.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp","side","reason","price","quantity","pnl"])
        writer.writeheader()
        writer.writerows(r["trades"])
    return path


# ═══════════════════════════════════════════════════════════════════════
# Telegram
# ═══════════════════════════════════════════════════════════════════════

def send_telegram(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        print("  (Telegram not configured — skipping notification)")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
        print("  📬 Telegram notification sent")
    except Exception as e:
        print(f"  Telegram send failed: {e}")


def build_telegram_message(results: list[dict], days: int) -> str:
    lines = [
        f"📊 *Backtest Results — last {days} days*",
        f"Strategy: SMA({SMA_SHORT}/{SMA_LONG}) + RSI({RSI_PERIOD}) | SL: {STOP_LOSS_PCT}%\n",
    ]
    for r in results:
        verdict = "✅" if r["total_pnl"] >= 0 else "❌"
        sign    = "+" if r["total_pnl"] >= 0 else ""
        lines.append(
            f"{verdict} *{r['symbol']}*\n"
            f"  P&L: `{sign}{r['total_pnl']:.4f} USDT` ({sign}{r['return_pct']:.2f}%)\n"
            f"  Trades: {r['total_trades']} | Win rate: {r['win_rate']:.1f}% ({r['wins']}W/{r['losses']}L)\n"
            f"  Max drawdown: -{r['max_drawdown_pct']:.2f}%"
        )

    if len(results) > 1:
        total_pnl    = sum(r["total_pnl"] for r in results)
        total_trades = sum(r["total_trades"] for r in results)
        total_wins   = sum(r["wins"] for r in results)
        avg_wr       = total_wins / total_trades * 100 if total_trades else 0
        sign = "+" if total_pnl >= 0 else ""
        lines.append(
            f"\n📦 *Combined*\n"
            f"  Total P&L: `{sign}{total_pnl:.4f} USDT`\n"
            f"  Trades: {total_trades} | Avg win rate: {avg_wr:.1f}%\n"
            f"  Best: {max(results, key=lambda r: r['total_pnl'])['symbol']} | "
            f"Worst: {min(results, key=lambda r: r['total_pnl'])['symbol']}"
        )
    return "\n".join(lines)


def save_summary(results: list[dict], days: int) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "backtest_summary.txt")
    lines = [
        f"Binance Bot Backtest Summary",
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Period    : last {days} days",
        f"Strategy  : SMA({SMA_SHORT}/{SMA_LONG}) + RSI({RSI_PERIOD}) | Stop-loss: {STOP_LOSS_PCT}%",
        f"Interval  : {INTERVAL}",
        "",
        f"{'Symbol':<12} {'Trades':>7} {'Win%':>7} {'P&L USDT':>12} {'Return%':>9} {'MaxDD%':>8}",
        "─" * 60,
    ]
    for r in results:
        sign = "+" if r["return_pct"] >= 0 else ""
        lines.append(
            f"{r['symbol']:<12} {r['total_trades']:>7} {r['win_rate']:>6.1f}%"
            f" {r['total_pnl']:>+12.4f} {sign}{r['return_pct']:>8.2f}%"
            f" {r['max_drawdown_pct']:>7.2f}%"
        )
    lines.append("─" * 60)
    total_pnl = sum(r["total_pnl"] for r in results)
    lines.append(f"{'TOTAL':<12} {'':>7} {'':>7} {total_pnl:>+12.4f}")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Backtest the SMA+RSI strategy")
    parser.add_argument("--days",   type=int, default=90,  help="How many days back (default: 90)")
    parser.add_argument("--symbol", type=str, default=None, help="Single symbol, e.g. BTCUSDT")
    args = parser.parse_args()

    pairs = TRADE_PAIRS
    if args.symbol:
        pairs = [p for p in TRADE_PAIRS if p["symbol"] == args.symbol]
        if not pairs:
            print(f"Symbol {args.symbol} not found in TRADE_PAIRS. Check config.py")
            return

    print(f"\n{'═'*52}")
    print(f"  Binance Bot Backtest — last {args.days} days")
    print(f"  Strategy: SMA({SMA_SHORT}/{SMA_LONG}) + RSI({RSI_PERIOD}) | Stop-loss: {STOP_LOSS_PCT}%")
    print(f"  Pairs: {', '.join(p['symbol'] for p in pairs)}")
    print(f"{'═'*52}\n")

    results = []

    for pair in pairs:
        symbol   = pair["symbol"]
        quantity = pair["quantity"]
        print(f"► {symbol}")
        try:
            df = fetch_klines(symbol, INTERVAL, args.days)
            df = add_indicators(df)
            r  = run_backtest(symbol, df, quantity)
            print_result(r)
            csv_path = save_trades_csv(r)
            print(f"  Trades saved → {csv_path}")
            results.append(r)
        except Exception as e:
            print(f"  ERROR backtesting {symbol}: {e}")

    if len(results) > 1:
        print(f"\n{'═'*52}")
        print(f"  COMBINED SUMMARY — all pairs")
        print(f"{'═'*52}")
        total_pnl    = sum(r["total_pnl"] for r in results)
        total_trades = sum(r["total_trades"] for r in results)
        total_wins   = sum(r["wins"] for r in results)
        avg_wr       = total_wins / total_trades * 100 if total_trades else 0
        sign = "+" if total_pnl >= 0 else ""
        print(f"  Total P&L  : {sign}{total_pnl:.4f} USDT")
        print(f"  Total trades: {total_trades}")
        print(f"  Avg win rate: {avg_wr:.1f}%")
        print(f"  Best pair  : {max(results, key=lambda r: r['total_pnl'])['symbol']}")
        print(f"  Worst pair : {min(results, key=lambda r: r['total_pnl'])['symbol']}")

    if results:
        summary_path = save_summary(results, args.days)
        print(f"\n  Full summary saved → {summary_path}")

        # Send to Telegram
        from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
        msg = build_telegram_message(results, args.days)
        send_telegram(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print(f"\n{'═'*52}\n")


if __name__ == "__main__":
    main()
