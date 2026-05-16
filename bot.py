import time
import logging
from datetime import datetime, timezone
from binance.um_futures import UMFutures
from binance.error import ClientError
import pandas as pd
import ta
import requests
from config import *

# ─── Logging ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ─── Client ─────────────────────────────
client = UMFutures(
    key=API_KEY,
    secret=API_SECRET,
    base_url="https://testnet.binancefuture.com" if TESTNET else None
)

log.info("Bot Started")

open_trades = {}

# ─── Balance ─────────────────────────────
def get_balance():
    try:
        acc = client.account()
        for a in acc["assets"]:
            if a["asset"] == "USDT":
                return float(a["availableBalance"])
    except:
        return 0

# ─── Pairs ─────────────────────────────
def get_pairs():
    tickers = client.ticker_24hr_price_change()
    usdt = [t for t in tickers if t["symbol"].endswith("USDT")]
    usdt.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    return [t["symbol"] for t in usdt[:TOP_PAIRS]]

# ─── Candles ─────────────────────────────
def candles(symbol):
    try:
        kl = client.klines(symbol, TIMEFRAME, limit=100)
        df = pd.DataFrame(kl, columns=[
            "t","o","h","l","c","v","ct","qv","n","tb","tq","i"
        ])
        df["c"] = df["c"].astype(float)
        df["v"] = df["v"].astype(float)
        return df
    except:
        return None

# ─── Signal ─────────────────────────────
def signal(df):
    if df is None or len(df) < 30:
        return None

    close = df["c"]
    vol = df["v"]

    rsi = ta.momentum.RSIIndicator(close, RSI_PERIOD).rsi()
    ema9 = ta.trend.EMAIndicator(close, EMA_FAST).ema_indicator()
    ema21 = ta.trend.EMAIndicator(close, EMA_SLOW).ema_indicator()

    rsi_now = rsi.iloc[-1]
    ema_up = ema9.iloc[-1] > ema21.iloc[-1]
    ema_down = ema9.iloc[-1] < ema21.iloc[-1]

    vol_ok = vol.iloc[-1] > vol.rolling(20).mean().iloc[-1] * VOLUME_MULTIPLIER

    if rsi_now < RSI_OVERSOLD and ema_up and vol_ok:
        return "LONG"

    if rsi_now > RSI_OVERBOUGHT and ema_down and vol_ok:
        return "SHORT"

    return None

# ─── Trade ─────────────────────────────
def trade(symbol, sig, balance):
    if symbol in open_trades:
        return

    if len(open_trades) >= MAX_TRADES_OPEN:
        return

    price = float(client.ticker_price(symbol=symbol)["price"])

    risk = balance * RISK_PER_TRADE
    qty = round((risk * LEVERAGE) / price, 3)

    if qty <= 0:
        return

    side = "BUY" if sig == "LONG" else "SELL"

    try:
        client.change_leverage(symbol=symbol, leverage=LEVERAGE)

        client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=qty
        )

        log.info(f"TRADE {sig} {symbol} qty={qty} price={price}")

        open_trades[symbol] = sig

    except ClientError as e:
        log.error(e.error_message)

# ─── Loop ─────────────────────────────
def run():
    while True:
        try:
            balance = get_balance()
            pairs = get_pairs()

            log.info(f"Balance: {balance}")

            for s in pairs:
                df = candles(s)
                sig = signal(df)

                if sig:
                    log.info(f"Signal {sig} {s}")
                    trade(s, sig, balance)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            log.error(e)
            time.sleep(10)

if __name__ == "__main__":
    run()
