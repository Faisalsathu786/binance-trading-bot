# 🤖 Binance Futures Auto Trading Bot

## Setup (5 minutes)

### Step 1 — Testnet Account
1. Go to: https://testnet.binancefuture.com
2. Register / Login
3. API Management → Create API Key
4. Copy Key + Secret → paste in `config.py`

### Step 2 — Install
```bash
pip install -r requirements.txt
```

### Step 3 — Configure
Edit `config.py`:
```python
API_KEY    = "your_key_here"
API_SECRET = "your_secret_here"
TESTNET    = True   # keep True for demo!
```

### Step 4 — Run
```bash
python bot.py
```

---

## Strategy
- **RSI** — oversold (<30) = long signal, overbought (>70) = short
- **EMA Crossover** — 9 EMA crosses 21 EMA = trend confirmation  
- **Volume** — must be 1.5x average = no fakeouts

## Risk Management
- Max 10 trades open at once
- 2% balance risk per trade
- Auto SL (2.5%) + TP (5%) on every trade
- 1:2 Risk:Reward ratio

## Switch to Live
When happy with results:
1. Change in `config.py`:
   ```python
   TESTNET = False
   API_KEY = "your_REAL_api_key"
   ```
2. That's it — same bot, real money

## Files
- `bot.py` — main bot
- `config.py` — all settings
- `bot.log` — trade log
