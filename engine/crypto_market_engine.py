"""
COSMO CRYPTO - Market Engine
Fetches OHLCV, funding rates, OI, liquidations from Binance public API.
No API key required.
"""

import requests
import json
import os
import time
from datetime import datetime, timezone
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR    = os.path.join(os.path.dirname(__file__), '..', 'data')
MARKET_OUT  = os.path.join(DATA_DIR, 'market_data.json')

# ── Coin Universe ─────────────────────────────────────────────────────────
COINS = {
    'L1': ['SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'ATOMUSDT', 'APTUSDT', 'SUIUSDT', 'TIAUSDT'],
    'DeFi': ['LINKUSDT', 'UNIUSDT', 'AAVEUSDT', 'MKRUSDT', 'SNXUSDT'],
    'L2': ['MATICUSDT', 'ARBUSDT', 'OPUSDT', 'STRKUSDT'],
    'Infra': ['INJUSDT', 'SEIUSDT', 'RUNEUSDT', 'FETUSDT'],
    'Meme': ['DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT'],
    'Gaming': ['AXSUSDT', 'SANDUSDT', 'MANAUSDT', 'IMXUSDT'],
}

ALL_COINS = [c for coins in COINS.values() for c in coins]

SECTOR_MAP = {coin: sector for sector, coins in COINS.items() for coin in coins}

BINANCE_BASE    = 'https://api.binance.com'
BINANCE_FUTURES = 'https://fapi.binance.com'

# ── Helpers ───────────────────────────────────────────────────────────────

def safe_get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            if i == retries - 1:
                print(f"   ⚠ Failed {url}: {e}")
    return None

# ── Technical Indicators ──────────────────────────────────────────────────

def calculate_ema(prices, period):
    if len(prices) < period:
        return prices[-1] if prices else 0
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs  = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_momentum(closes, period=10):
    if len(closes) <= period:
        return 0
    return round(((closes[-1] / closes[-period]) - 1) * 100, 2)

def get_trend(close, ema20, ema50):
    if close > ema20 > ema50:   return 'Strong Uptrend'
    elif close > ema20:          return 'Recovery'
    elif close < ema20 < ema50:  return 'Strong Downtrend'
    elif close < ema20:          return 'Pullback'
    return 'Sideways'

def calculate_technical_score(rsi, momentum, trend, vol_signal):
    score = 50
    if 50 <= rsi <= 65:    score += 15
    elif 40 <= rsi < 50:   score += 5
    elif rsi > 70:         score -= 10
    elif rsi < 30:         score -= 15
    if momentum > 10:      score += 12
    elif momentum > 5:     score += 8
    elif momentum > 2:     score += 4
    elif momentum < -10:   score -= 12
    elif momentum < -5:    score -= 8
    elif momentum < -2:    score -= 4
    if trend == 'Strong Uptrend':   score += 15
    elif trend == 'Recovery':        score += 8
    elif trend == 'Pullback':        score -= 5
    elif trend == 'Strong Downtrend': score -= 15
    if vol_signal == 'Volume Spike': score += 10
    elif vol_signal == 'High Volume': score += 5
    return max(0, min(100, score))

# ── Fetch OHLCV ───────────────────────────────────────────────────────────

def fetch_ohlcv(symbol, interval='1d', limit=60):
    url    = f"{BINANCE_BASE}/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    data   = safe_get(url, params)
    if not data:
        return None
    closes  = [float(k[4]) for k in data]
    volumes = [float(k[5]) for k in data]
    highs   = [float(k[2]) for k in data]
    lows    = [float(k[3]) for k in data]
    return closes, volumes, highs, lows

# ── Fetch 24h Ticker ──────────────────────────────────────────────────────

def fetch_24h_ticker(symbol):
    url  = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    data = safe_get(url, {'symbol': symbol})
    if not data:
        return None
    return {
        'price':      float(data.get('lastPrice', 0)),
        'change_pct': float(data.get('priceChangePercent', 0)),
        'volume_usd': float(data.get('quoteVolume', 0)),
        'high_24h':   float(data.get('highPrice', 0)),
        'low_24h':    float(data.get('lowPrice', 0)),
    }

# ── Fetch Funding Rate ────────────────────────────────────────────────────

def fetch_funding_rate(symbol):
    url  = f"{BINANCE_FUTURES}/fapi/v1/fundingRate"
    data = safe_get(url, {'symbol': symbol, 'limit': 1})
    if not data or not isinstance(data, list):
        return None
    latest = data[-1]
    rate   = float(latest.get('fundingRate', 0)) * 100
    return {
        'rate':      round(rate, 4),
        'sentiment': 'Long Heavy' if rate > 0.05 else 'Short Heavy' if rate < -0.05 else 'Neutral',
    }

# ── Fetch Open Interest ───────────────────────────────────────────────────

def fetch_open_interest(symbol):
    url  = f"{BINANCE_FUTURES}/fapi/v1/openInterest"
    data = safe_get(url, {'symbol': symbol})
    if not data:
        return None
    return {
        'oi':        float(data.get('openInterest', 0)),
        'oi_usd':    float(data.get('openInterest', 0)),
    }

# ── Fetch Liquidations (24h) ──────────────────────────────────────────────

def fetch_liquidation_stats(symbol):
    """Approximates liquidation pressure from long/short ratio."""
    url  = f"{BINANCE_FUTURES}/futures/data/globalLongShortAccountRatio"
    data = safe_get(url, {'symbol': symbol, 'period': '1d', 'limit': 1})
    if not data or not isinstance(data, list):
        return None
    latest = data[-1] if data else {}
    ls_ratio = float(latest.get('longShortRatio', 1))
    return {
        'long_pct':   round(float(latest.get('longAccount', 0.5)) * 100, 1),
        'short_pct':  round(float(latest.get('shortAccount', 0.5)) * 100, 1),
        'ls_ratio':   round(ls_ratio, 3),
        'sentiment':  'Long Dominated' if ls_ratio > 1.2 else 'Short Dominated' if ls_ratio < 0.8 else 'Balanced',
    }

# ── Process Single Coin ───────────────────────────────────────────────────

def process_coin(symbol):
    ticker = fetch_24h_ticker(symbol)
    if not ticker:
        return None

    ohlcv = fetch_ohlcv(symbol)
    if not ohlcv:
        return None

    closes, volumes, highs, lows = ohlcv
    current_price = ticker['price']

    # Technicals
    ema9  = calculate_ema(closes, 9)
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    rsi   = calculate_rsi(closes)
    mom   = calculate_momentum(closes, 10)

    avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
    cur_vol = volumes[-1]
    vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1
    vol_signal = 'Volume Spike' if vol_ratio >= 2 else 'High Volume' if vol_ratio >= 1.5 else 'Normal Volume' if vol_ratio >= 0.8 else 'Low Volume'

    trend      = get_trend(current_price, ema20, ema50)
    tech_score = calculate_technical_score(rsi, mom, trend, vol_signal)

    # ATH distance (52-week approx from 365 daily candles)
    ath_approx = max(closes[-365:]) if len(closes) >= 365 else max(closes)
    pct_from_ath = round(((current_price - ath_approx) / ath_approx) * 100, 2)

    # Futures data
    funding = fetch_funding_rate(symbol)
    oi      = fetch_open_interest(symbol)
    ls      = fetch_liquidation_stats(symbol)

    time.sleep(0.1)  # Rate limit respect

    return {
        'symbol':         symbol,
        'name':           symbol.replace('USDT', ''),
        'sector':         SECTOR_MAP.get(symbol, 'Other'),
        'price':          round(current_price, 6),
        'change_pct':     ticker['change_pct'],
        'volume_usd':     round(ticker['volume_usd'], 0),
        'high_24h':       ticker['high_24h'],
        'low_24h':        ticker['low_24h'],
        'ema9':           round(ema9, 6),
        'ema20':          round(ema20, 6),
        'ema50':          round(ema50, 6),
        'rsi':            rsi,
        'momentum':       mom,
        'trend':          trend,
        'volume_signal':  vol_signal,
        'vol_ratio':      round(vol_ratio, 2),
        'pct_from_ath':   pct_from_ath,
        'technical_score': tech_score,
        'funding_rate':   funding,
        'open_interest':  oi,
        'ls_ratio':       ls,
    }

# ── Sector Scoring ────────────────────────────────────────────────────────

def score_sector(coins_data):
    if not coins_data:
        return 0
    scores   = [c['technical_score'] for c in coins_data]
    avg      = sum(scores) / len(scores)
    bull_r   = sum(1 for c in coins_data if c['change_pct'] > 0) / len(coins_data)
    vb_bonus = min(sum(1 for c in coins_data if c['volume_signal'] in ['Volume Spike', 'High Volume']) * 3, 15)
    return round(min(100, avg * 0.6 + bull_r * 30 + vb_bonus), 1)

# ── Market Dominance ──────────────────────────────────────────────────────

def fetch_market_overview():
    url  = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    data = safe_get(url)
    if not data:
        return {}
    usdt_pairs = [d for d in data if d['symbol'].endswith('USDT') and not d['symbol'].endswith('DOWNUSDT')]
    advancing  = sum(1 for d in usdt_pairs if float(d['priceChangePercent']) > 0)
    declining  = sum(1 for d in usdt_pairs if float(d['priceChangePercent']) < 0)
    total      = len(usdt_pairs)
    breadth    = round((advancing / total) * 100, 1) if total > 0 else 50

    # BTC dominance proxy — BTC volume vs total
    btc = next((d for d in data if d['symbol'] == 'BTCUSDT'), None)
    btc_vol = float(btc['quoteVolume']) if btc else 0
    total_vol = sum(float(d['quoteVolume']) for d in usdt_pairs[:100])
    btc_dom = round((btc_vol / total_vol) * 100, 1) if total_vol > 0 else 0

    return {
        'total_pairs':   total,
        'advancing':     advancing,
        'declining':     declining,
        'breadth_ratio': breadth,
        'btc_dominance_proxy': btc_dom,
    }

# ── Fetch BTC + ETH as reference ──────────────────────────────────────────

def fetch_reference_coins():
    refs = {}
    for sym in ['BTCUSDT', 'ETHUSDT']:
        t = fetch_24h_ticker(sym)
        f = fetch_funding_rate(sym)
        if t:
            refs[sym.replace('USDT','')] = {
                'price':       t['price'],
                'change_pct':  t['change_pct'],
                'funding':     f,
            }
    return refs

# ── Main Market Engine ────────────────────────────────────────────────────

def run_market_engine():
    print("📈 Crypto Market Engine starting...")
    now = datetime.now(timezone.utc)

    # Market overview
    print("   Fetching market overview...")
    overview = fetch_market_overview()

    # Reference coins
    print("   Fetching BTC/ETH reference...")
    reference = fetch_reference_coins()

    # Market direction from breadth
    breadth = overview.get('breadth_ratio', 50)
    market_direction = 'Bullish' if breadth >= 60 else 'Bearish' if breadth <= 40 else 'Neutral'

    # Process all coins
    all_coins_data = []
    sector_results = {}

    for sector, coins in COINS.items():
        print(f"   Processing {sector}...")
        sector_coins = []
        for symbol in coins:
            data = process_coin(symbol)
            if data:
                sector_coins.append(data)
                all_coins_data.append(data)

        sector_score = score_sector(sector_coins)
        top3 = sorted(sector_coins, key=lambda x: x['technical_score'], reverse=True)[:3]
        sector_results[sector] = {
            'score':       sector_score,
            'coin_count':  len(sector_coins),
            'top_coins':   [c['name'] for c in top3],
            'avg_rsi':     round(sum(c['rsi'] for c in sector_coins) / len(sector_coins), 1) if sector_coins else 0,
            'bullish_count': sum(1 for c in sector_coins if c['change_pct'] > 0),
            'bearish_count': sum(1 for c in sector_coins if c['change_pct'] <= 0),
        }

    # Rank sectors
    sectors_ranked = sorted(sector_results.items(), key=lambda x: x[1]['score'], reverse=True)

    # Volatility
    changes = [abs(c['change_pct']) for c in all_coins_data]
    avg_vol = sum(changes) / len(changes) if changes else 0
    volatility_bias = 'High' if avg_vol > 5 else 'Medium' if avg_vol > 2 else 'Low'

    output = {
        'date':             now.strftime('%Y-%m-%d'),
        'generated_at':     now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'market_direction': market_direction,
        'volatility_bias':  volatility_bias,
        'breadth':          overview,
        'reference':        reference,
        'sectors_ranked':   [{'name': n, **d} for n, d in sectors_ranked],
        'all_coins':        all_coins_data,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Crypto Market Engine complete")
    print(f"   Direction  : {market_direction}")
    print(f"   Breadth    : {breadth}%")
    print(f"   Volatility : {volatility_bias}")
    print(f"   Coins      : {len(all_coins_data)}")
    for name, data in sectors_ranked[:3]:
        print(f"   {name:12} Score: {data['score']}")

    return output

if __name__ == '__main__':
    run_market_engine()
