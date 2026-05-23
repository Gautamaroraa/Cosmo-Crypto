"""
COSMO CRYPTO - Market Engine
Fetches OHLCV, funding rates, OI from Binance public API.
Uses batch endpoints to minimize API calls and avoid rate limiting.
"""

import requests
import json
import os
import time
from datetime import datetime, timezone

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
MARKET_OUT = os.path.join(DATA_DIR, 'market_data.json')

COINS = {
    'L1':     ['SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'ATOMUSDT', 'APTUSDT', 'SUIUSDT', 'TIAUSDT'],
    'DeFi':   ['LINKUSDT', 'UNIUSDT', 'AAVEUSDT', 'MKRUSDT', 'SNXUSDT'],
    'L2':     ['MATICUSDT', 'ARBUSDT', 'OPUSDT', 'STRKUSDT'],
    'Infra':  ['INJUSDT', 'SEIUSDT', 'RUNEUSDT', 'FETUSDT'],
    'Meme':   ['DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT'],
    'Gaming': ['AXSUSDT', 'SANDUSDT', 'MANAUSDT', 'IMXUSDT'],
}

ALL_COINS  = [c for coins in COINS.values() for c in coins]
SECTOR_MAP = {coin: sector for sector, coins in COINS.items() for coin in coins}

BINANCE_BASE    = 'https://api.binance.com'
BINANCE_FUTURES = 'https://fapi.binance.com'

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0'})

def safe_get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f"   ⚠ Rate limited — sleeping 10s")
                time.sleep(10)
            elif r.status_code == 451:
                print(f"   ⚠ Geo-restricted endpoint")
                return None
        except Exception as e:
            if i == retries - 1:
                print(f"   ⚠ {url}: {e}")
            time.sleep(2)
    return None

# ── BATCH fetch all 24h tickers at once ──────────────────────────────────

def fetch_all_tickers():
    """
    Single API call returns ALL spot tickers.
    This is the key optimization — one call instead of 30.
    """
    data = safe_get(f"{BINANCE_BASE}/api/v3/ticker/24hr")
    if not data:
        return {}
    return {d['symbol']: d for d in data if isinstance(d, dict)}

def fetch_all_futures_tickers():
    """Single call for all futures tickers."""
    data = safe_get(f"{BINANCE_FUTURES}/fapi/v1/ticker/24hr")
    if not data:
        return {}
    return {d['symbol']: d for d in data if isinstance(d, dict)}

def fetch_all_funding_rates():
    """Single call for all current funding rates."""
    data = safe_get(f"{BINANCE_FUTURES}/fapi/v1/premiumIndex")
    if not data:
        return {}
    return {d['symbol']: d for d in data if isinstance(d, dict)}

def fetch_all_open_interest():
    """Fetch OI for our coin list — one call per coin but with delay."""
    oi_map = {}
    for symbol in ALL_COINS:
        data = safe_get(f"{BINANCE_FUTURES}/fapi/v1/openInterest", {'symbol': symbol})
        if data:
            oi_map[symbol] = float(data.get('openInterest', 0))
        time.sleep(0.15)
    return oi_map

# ── OHLCV for technicals ─────────────────────────────────────────────────

def fetch_ohlcv(symbol, interval='1d', limit=60):
    data = safe_get(f"{BINANCE_BASE}/api/v3/klines",
                    {'symbol': symbol, 'interval': interval, 'limit': limit})
    if not data:
        return None
    closes  = [float(k[4]) for k in data]
    volumes = [float(k[5]) for k in data]
    return closes, volumes

# ── Technical Indicators ─────────────────────────────────────────────────

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
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_momentum(closes, period=10):
    if len(closes) <= period: return 0
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
    if trend == 'Strong Uptrend':    score += 15
    elif trend == 'Recovery':         score += 8
    elif trend == 'Pullback':         score -= 5
    elif trend == 'Strong Downtrend': score -= 15
    if vol_signal == 'Volume Spike':  score += 10
    elif vol_signal == 'High Volume': score += 5
    return max(0, min(100, score))

# ── Process coins using batched data ─────────────────────────────────────

def process_coin(symbol, ticker_data, funding_data, oi_data):
    ticker = ticker_data.get(symbol)
    if not ticker:
        return None

    price      = float(ticker.get('lastPrice', 0))
    change_pct = float(ticker.get('priceChangePercent', 0))
    volume_usd = float(ticker.get('quoteVolume', 0))
    high_24h   = float(ticker.get('highPrice', 0))
    low_24h    = float(ticker.get('lowPrice', 0))

    # OHLCV for technicals
    ohlcv = fetch_ohlcv(symbol)
    time.sleep(0.1)

    if not ohlcv:
        return None

    closes, volumes = ohlcv
    ema9  = calculate_ema(closes, 9)
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    rsi   = calculate_rsi(closes)
    mom   = calculate_momentum(closes, 10)

    avg_vol    = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
    cur_vol    = volumes[-1]
    vol_ratio  = cur_vol / avg_vol if avg_vol > 0 else 1
    vol_signal = 'Volume Spike' if vol_ratio >= 2 else 'High Volume' if vol_ratio >= 1.5 else 'Normal Volume' if vol_ratio >= 0.8 else 'Low Volume'

    trend      = get_trend(price, ema20, ema50)
    tech_score = calculate_technical_score(rsi, mom, trend, vol_signal)

    # Funding from batch data
    funding_raw = funding_data.get(symbol)
    funding = None
    if funding_raw:
        rate = round(float(funding_raw.get('lastFundingRate', 0)) * 100, 4)
        annual = round(rate * 3 * 365, 1)
        sentiment = 'Strongly Long Heavy' if rate > 0.1 else \
                    'Long Heavy' if rate > 0.05 else \
                    'Slightly Long' if rate > 0.01 else \
                    'Short Heavy' if rate < -0.05 else \
                    'Slightly Short' if rate < -0.01 else 'Neutral'
        funding = {'rate': rate, 'annualized': annual, 'sentiment': sentiment}

    # OI from batch data
    oi_coins = oi_data.get(symbol, 0)
    oi_usd   = round(oi_coins * price, 0) if price > 0 else 0
    oi = {'oi_coins': round(oi_coins, 2), 'oi_usd': oi_usd} if oi_coins else None

    return {
        'symbol':          symbol,
        'name':            symbol.replace('USDT', ''),
        'sector':          SECTOR_MAP.get(symbol, 'Other'),
        'price':           round(price, 6),
        'change_pct':      round(change_pct, 2),
        'volume_usd':      round(volume_usd, 0),
        'high_24h':        round(high_24h, 6),
        'low_24h':         round(low_24h, 6),
        'ema9':            round(ema9, 6),
        'ema20':           round(ema20, 6),
        'ema50':           round(ema50, 6),
        'rsi':             rsi,
        'momentum':        mom,
        'trend':           trend,
        'volume_signal':   vol_signal,
        'vol_ratio':       round(vol_ratio, 2),
        'technical_score': tech_score,
        'funding_rate':    funding,
        'open_interest':   oi,
        'ls_ratio':        None,
    }

def score_sector(coins_data):
    if not coins_data: return 0
    scores  = [c['technical_score'] for c in coins_data]
    avg     = sum(scores) / len(scores)
    bull_r  = sum(1 for c in coins_data if c['change_pct'] > 0) / len(coins_data)
    vb      = min(sum(1 for c in coins_data if c['volume_signal'] in ['Volume Spike', 'High Volume']) * 3, 15)
    return round(min(100, avg * 0.6 + bull_r * 30 + vb), 1)

def run_market_engine():
    print("📈 Crypto Market Engine starting...")
    now = datetime.now(timezone.utc)

    # ── Batch fetch everything ────────────────────────────────────────────
    print("   Fetching all spot tickers (1 call)...")
    all_tickers = fetch_all_tickers()
    time.sleep(0.5)

    print("   Fetching all funding rates (1 call)...")
    all_funding = fetch_all_funding_rates()
    time.sleep(0.5)

    print("   Fetching open interest...")
    all_oi = fetch_all_open_interest()
    time.sleep(0.5)

    # Market breadth from batch ticker data
    usdt_pairs = {k: v for k, v in all_tickers.items() if k.endswith('USDT') and not k.endswith('DOWNUSDT')}
    advancing  = sum(1 for d in usdt_pairs.values() if float(d.get('priceChangePercent', 0)) > 0)
    declining  = sum(1 for d in usdt_pairs.values() if float(d.get('priceChangePercent', 0)) < 0)
    total      = len(usdt_pairs)
    breadth    = round((advancing / total) * 100, 1) if total > 0 else 50

    # BTC dominance proxy
    btc_vol   = float(all_tickers.get('BTCUSDT', {}).get('quoteVolume', 0))
    total_vol = sum(float(d.get('quoteVolume', 0)) for d in list(usdt_pairs.values())[:100])
    btc_dom   = round((btc_vol / total_vol) * 100, 1) if total_vol > 0 else 0

    market_direction = 'Bullish' if breadth >= 60 else 'Bearish' if breadth <= 40 else 'Neutral'

    # BTC/ETH reference
    reference = {}
    for sym in ['BTCUSDT', 'ETHUSDT']:
        t = all_tickers.get(sym)
        f = all_funding.get(sym)
        if t:
            rate = round(float(f.get('lastFundingRate', 0)) * 100, 4) if f else 0
            reference[sym.replace('USDT', '')] = {
                'price':      round(float(t.get('lastPrice', 0)), 2),
                'change_pct': round(float(t.get('priceChangePercent', 0)), 2),
                'funding':    {'rate': rate, 'sentiment': 'Long Heavy' if rate > 0.05 else 'Neutral'} if f else None,
            }

    # Process all coins
    all_coins_data = []
    sector_results = {}

    for sector, coins in COINS.items():
        print(f"   Processing {sector}...")
        sector_coins = []
        for symbol in coins:
            data = process_coin(symbol, all_tickers, all_funding, all_oi)
            if data:
                sector_coins.append(data)
                all_coins_data.append(data)
            time.sleep(0.2)

        sector_score = score_sector(sector_coins)
        top3 = sorted(sector_coins, key=lambda x: x['technical_score'], reverse=True)[:3]
        sector_results[sector] = {
            'score':         sector_score,
            'coin_count':    len(sector_coins),
            'top_coins':     [c['name'] for c in top3],
            'avg_rsi':       round(sum(c['rsi'] for c in sector_coins) / len(sector_coins), 1) if sector_coins else 0,
            'bullish_count': sum(1 for c in sector_coins if c['change_pct'] > 0),
            'bearish_count': sum(1 for c in sector_coins if c['change_pct'] <= 0),
        }

    sectors_ranked = sorted(sector_results.items(), key=lambda x: x[1]['score'], reverse=True)

    changes        = [abs(c['change_pct']) for c in all_coins_data]
    avg_vol        = sum(changes) / len(changes) if changes else 0
    volatility_bias = 'High' if avg_vol > 5 else 'Medium' if avg_vol > 2 else 'Low'

    output = {
        'date':             now.strftime('%Y-%m-%d'),
        'generated_at':     now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'market_direction': market_direction,
        'volatility_bias':  volatility_bias,
        'breadth': {
            'total_pairs':         total,
            'advancing':           advancing,
            'declining':           declining,
            'breadth_ratio':       breadth,
            'btc_dominance_proxy': btc_dom,
        },
        'reference':      reference,
        'sectors_ranked': [{'name': n, **d} for n, d in sectors_ranked],
        'all_coins':      all_coins_data,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Crypto Market Engine complete")
    print(f"   Direction  : {market_direction}")
    print(f"   Breadth    : {breadth}%")
    print(f"   Coins      : {len(all_coins_data)}")
    for name, data in sectors_ranked[:3]:
        print(f"   {name:10} Score: {data['score']}")

    return output

if __name__ == '__main__':
    run_market_engine()
