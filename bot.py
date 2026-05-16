"""
Binance Futures Auto Trading Bot
- Scans top USDT pairs by volume
- Strategy: RSI + EMA crossover + Volume confirmation
- Max 10 concurrent trades
- Auto SL/TP on every trade
- Testnet safe by default
"""

import time
import logging
from datetime import datetime
from binance.um_futures import UMFutures
from binance.error import ClientError
import pandas as pd
import ta
import requests
from config import *

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── Binance client ──────────────────────────────────────────
if TESTNET:
    client = UMFutures(
        key=API_KEY,
        secret=API_SECRET,
        base_url="https://testnet.binancefuture.com"
    )
    log.info("🧪 TESTNET MODE — no real money")
else:
    client = UMFutures(key=API_KEY, secret=API_SECRET)
    log.info("🔴 LIVE MODE — real money!")

# ─── State ───────────────────────────────────────────────────
open_trades = {}   # { symbol: { side, entry, sl, tp, qty } }

# ─── Telegram notify (optional) ──────────────────────────────
def notify(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
    except Exception:
        pass

# ─── Get account balance ─────────────────────────────────────
def get_balance():
    try:
        account = client.account()
        for asset in account["assets"]:
            if asset["asset"] == "USDT":
                return float(asset["availableBalance"])
    except Exception as e:
        log.error(f"Balance error: {e}")
    return 0.0

# ─── Get top pairs by volume ─────────────────────────────────
def get_top_pairs(n=TOP_PAIRS):
    try:
        tickers = client.ticker_24hr_price_change()
        usdt = [t for t in tickers if t["symbol"].endswith("USDT")
                and not any(x in t["symbol"] for x in ["DOWN", "UP", "BULL", "BEAR"])]
        usdt.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
        return [t["symbol"] for t in usdt[:n]]
    except Exception as e:
        log.error(f"Pairs error: {e}")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# ─── Get OHLCV candles ───────────────────────────────────────
def get_candles(symbol, interval=TIMEFRAME, limit=100):
    try:
        klines = client.klines(symbol, interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_vol","trades","taker_buy","taker_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        log.error(f"Candles error {symbol}: {e}")
        return None

# ─── Calculate indicators ────────────────────────────────────
def get_signal(df):
    """
    Returns: 'LONG', 'SHORT', or None
    Conditions:
      LONG  — RSI < oversold AND EMA fast crosses above slow AND volume spike
      SHORT — RSI > overbought AND EMA fast crosses below slow AND volume spike
    """
    if df is None or len(df) < EMA_SLOW + 5:
        return None

    close  = df["close"]
    volume = df["volume"]

    # RSI
    rsi = ta.momentum.RSIIndicator(close, window=RSI_PERIOD).rsi()

    # EMA
    ema_fast = ta.trend.EMAIndicator(close, window=EMA_FAST).ema_indicator()
    ema_slow = ta.trend.EMAIndicator(close, window=EMA_SLOW).ema_indicator()

    # Volume (compare last candle vs 20-period avg)
    vol_avg  = volume.rolling(20).mean()

    # Latest values
    rsi_now    = rsi.iloc[-1]
    rsi_prev   = rsi.iloc[-2]
    ema_f_now  = ema_fast.iloc[-1]
    ema_f_prev = ema_fast.iloc[-2]
    ema_s_now  = ema_slow.iloc[-1]
    ema_s_prev = ema_slow.iloc[-2]
    vol_now    = volume.iloc[-1]
    vol_avg_now = vol_avg.iloc[-1]

    has_vol = vol_now >= vol_avg_now * VOLUME_MULTIPLIER

    # LONG signal
    if (rsi_now < RSI_OVERSOLD and
        ema_f_prev < ema_s_prev and ema_f_now > ema_s_now and
        has_vol):
        return "LONG"

    # SHORT signal
    if (rsi_now > RSI_OVERBOUGHT and
        ema_f_prev > ema_s_prev and ema_f_now < ema_s_now and
        has_vol):
        return "SHORT"

    return None

# ─── Get symbol precision ────────────────────────────────────
def get_precision(symbol):
    try:
        info = client.exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                qty_prec   = s["quantityPrecision"]
                price_prec = s["pricePrecision"]
                return qty_prec, price_prec
    except Exception as e:
        log.error(f"Precision error: {e}")
    return 3, 2

# ─── Place trade ─────────────────────────────────────────────
def place_trade(symbol, signal, balance):
    if symbol in open_trades:
        return  # already in this symbol

    if len(open_trades) >= MAX_TRADES_OPEN:
        log.info(f"Max trades ({MAX_TRADES_OPEN}) reached, skipping {symbol}")
        return

    try:
        # Set leverage
        client.change_leverage(symbol=symbol, leverage=LEVERAGE)

        # Get current price
        ticker = client.ticker_price(symbol=symbol)
        price  = float(ticker["price"])

        # Calculate quantity
        risk_usdt = balance * RISK_PER_TRADE
        notional  = risk_usdt * LEVERAGE
        qty_prec, price_prec = get_precision(symbol)
        qty = round(notional / price, qty_prec)

        if qty <= 0:
            log.warning(f"Qty too small for {symbol}, skip")
            return

        # SL / TP prices
        if signal == "LONG":
            side    = "BUY"
            sl_price = round(price * (1 - SL_PERCENT), price_prec)
            tp_price = round(price * (1 + TP_PERCENT), price_prec)
            sl_side  = "SELL"
        else:
            side    = "SELL"
            sl_price = round(price * (1 + SL_PERCENT), price_prec)
            tp_price = round(price * (1 - TP_PERCENT), price_prec)
            sl_side  = "BUY"

        # Place market order
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=qty
        )

        order_id = order.get("orderId", "?")
        log.info(f"✅ {signal} {symbol} | qty={qty} | entry≈{price} | SL={sl_price} | TP={tp_price}")

        # Stop Loss
        client.new_order(
            symbol=symbol,
            side=sl_side,
            type="STOP_MARKET",
            stopPrice=str(sl_price),
            closePosition="true",
            timeInForce="GTE_GTC"
        )

        # Take Profit
        client.new_order(
            symbol=symbol,
            side=sl_side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=str(tp_price),
            closePosition="true",
            timeInForce="GTE_GTC"
        )

        open_trades[symbol] = {
            "side": signal, "entry": price,
            "sl": sl_price, "tp": tp_price,
            "qty": qty, "time": datetime.utcnow().isoformat()
        }

        notify(f"🤖 {signal} {symbol}\nEntry: {price}\nSL: {sl_price}\nTP: {tp_price}\nQty: {qty}")

    except ClientError as e:
        log.error(f"Order error {symbol}: {e.error_message}")
    except Exception as e:
        log.error(f"Trade error {symbol}: {e}")

# ─── Check closed positions ──────────────────────────────────
def sync_open_positions():
    """Remove from open_trades if position closed on exchange"""
    try:
        positions = client.get_position_risk()
        active = {p["symbol"] for p in positions if float(p["positionAmt"]) != 0}
        closed = [s for s in list(open_trades.keys()) if s not in active]
        for s in closed:
            trade = open_trades.pop(s)
            log.info(f"📊 Position closed: {s} ({trade['side']})")
            notify(f"📊 Closed: {s} ({trade['side']})")
    except Exception as e:
        log.error(f"Sync error: {e}")

# ─── Main scan loop ──────────────────────────────────────────
def run():
    log.info("=" * 50)
    log.info("🤖 Trading Bot Started")
    log.info(f"Mode: {'TESTNET' if TESTNET else 'LIVE'}")
    log.info(f"Max trades: {MAX_TRADES_OPEN} | Risk/trade: {RISK_PER_TRADE*100}%")
    log.info(f"Strategy: RSI({RSI_PERIOD}) + EMA({EMA_FAST}/{EMA_SLOW}) + Volume")
    log.info("=" * 50)

    scan_count = 0

    while True:
        try:
            scan_count += 1
            log.info(f"\n── Scan #{scan_count} @ {datetime.utcnow().strftime('%H:%M:%S')} UTC ──")

            # Sync closed positions
            sync_open_positions()
            log.info(f"Open trades: {len(open_trades)}/{MAX_TRADES_OPEN} — {list(open_trades.keys())}")

            # Get balance
            balance = get_balance()
            log.info(f"Balance: ${balance:.2f} USDT")

            if balance < 10:
                log.warning("Balance < $10, skipping trade entries")
                time.sleep(SCAN_INTERVAL)
                continue

            # Get top pairs
            pairs = get_top_pairs()
            log.info(f"Scanning {len(pairs)} pairs...")

            # Scan each pair
            for symbol in pairs:
                if symbol in open_trades:
                    continue  # already in trade

                df = get_candles(symbol)
                signal = get_signal(df)

                if signal:
                    log.info(f"🎯 Signal: {signal} on {symbol}")
                    place_trade(symbol, signal, balance)

            log.info(f"Scan done. Sleeping {SCAN_INTERVAL}s...")
            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            log.info("🛑 Bot stopped by user")
            notify("🛑 Bot stopped")
            break
        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run()
