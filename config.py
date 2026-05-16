# ─── config.py ───────────────────────────────────────────────
# Binance Testnet API keys — get from: https://testnet.binancefuture.com
# Register → API Management → Create Key

API_KEY    = "i7FDT8uRU3cK2ib6mt0Nz4mQZesgRSBlg9LIwectiocer9dzWfa6yUiwMzvkhslp"
API_SECRET = "QERzLALrtyF1kfz1TtQl3FcYHDALkdYPYqIZbaX96sBjFq0QP646fH7xEtUFPQlG"

# ─── Mode ────────────────────────────────────────────────────
TESTNET = True   # True = demo, False = real money

# ─── Risk Settings ───────────────────────────────────────────
MAX_TRADES_OPEN   = 10       # max concurrent positions
RISK_PER_TRADE    = 0.02     # 2% of balance per trade
LEVERAGE          = 5        # default leverage
SL_PERCENT        = 0.025    # 2.5% stop loss
TP_PERCENT        = 0.05     # 5% take profit (1:2 R:R)

# ─── Strategy Settings ───────────────────────────────────────
RSI_PERIOD        = 14
RSI_OVERSOLD      = 30       # long signal
RSI_OVERBOUGHT    = 70       # short signal
EMA_FAST          = 9
EMA_SLOW          = 21
VOLUME_MULTIPLIER = 1.5      # volume must be 1.5x avg to confirm signal

# ─── Scan Settings ───────────────────────────────────────────
SCAN_INTERVAL     = 60       # seconds between scans
TIMEFRAME         = "15m"    # candle timeframe
TOP_PAIRS         = 20       # scan top 20 USDT pairs by volume

# ─── Telegram Notifications (optional) ───────────────────────
TELEGRAM_TOKEN  = ""         # leave blank to disable
TELEGRAM_CHAT_ID = ""
