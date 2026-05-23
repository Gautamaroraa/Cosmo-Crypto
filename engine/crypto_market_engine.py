"""
COSMO CRYPTO - Market Engine
Uses multiple Binance endpoints with fallbacks for GitHub Actions compatibility.
"""

import requests
import json
import os
import time
from datetime import datetime, timezone

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
MARKET_OUT = os.path.join(DATA_DIR, 'market_data.json')

COINS = {
    'L1':     ['SOLUSDT','BNBUSDT','XRPUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','ATOMUSDT','APTUSDT','SUIUSDT','TIAUSDT'],
    'DeFi':   ['LINKUSDT','UNIUSDT','AAVEUSDT','MKRUSDT','SNXUSDT'],
    'L2':     ['MATICUSDT','ARBUSDT','OPUSDT','STRKUSDT'],
    'Infra':  ['INJUSDT','SEIUSDT','RUNEUSDT','FETUSDT'],
    'Meme':   ['DOGEUSDT','SHIBUSDT','PEPEUSDT','FLOKIUSDT'],
    'Gaming': ['AXSUSDT','SANDUSDT','MANAUSDT','IMXUSDT'],
}

ALL_COINS  = [c for coins in COINS.values() for c in coins]
SECTOR_MAP = {coin: sector for sector, coins in COINS.items() for coin in coins}

# ── Multiple base URLs — fallback chain ───────────────────────────────────
BINANCE_BASES = [
    'https://api.binance.com',
    'https://api1.binance.com',
    'https://api2.binance.com',
    'https://api3.binance.com',
]
BINANCE_FUTURES_BASES = [
    'https://fapi.binance.com',
]

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
})

def safe_get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f"   ⚠ Rate limited — sleeping 15s")
                time.sleep(15)
            elif r.status_code == 451:
                return None  # Geo-restricted, try next base
            else:
                print(f"   ⚠ HTTP {r.status_code} for {url}")
        except Exception as e:
            if i == retries - 1:
                print(f"   ⚠ {url}: {e}")
            time.sleep(2)
    return None

def safe_get_with_fallback(path, params=None, bases=None):
    """Try multiple base URLs."""
    bases = bases or BINANCE_BASES
    for base in bases:
        result = safe_get(f"{base}{path}", params)
        if result is not None:
            return result
    return None

# ── Fetch all tickers (batch) ─────────────────────────────────────────────

def fetch_all_tickers():
    data = safe_get_with_fallback('/api/v3/ticker/24hr')
    if not data:
        print("   ⚠ Could not fetch tickers from any Binance endpoint")
        return {}
    print(f"   ✅ Got {len(data)} tickers")
    return {d['symbol']: d for d in data if isinstance(d, dict)}

def fetch_all_funding_rates():
    for base in BINANCE_FUTURES_BASES:
        data = safe_get(f"{base}/fapi/v1/premiumIndex")
        if data:
            return {d['symbol']: d for d in data if isinstance(d, dict)}
    return {}

# ── OHLCV ─────────────────────────────────────────────────────────────────

def fetch_ohlcv(symbol, limit=60):
    data = safe_get_with_fallback('/api/v3/klines',
                                  {'symbol': symbol, 'interval': '1d', 'limit': limit})
    if not data:
        return None
    closes  = [float(k[4]) for k in data]
    volumes = [float(k[5]) for k in data]
    return closes, volumes

# ── Technical Indicators ──────────────────────────────────────────────────

def ema(prices, period):
    if not prices: return 0
    k, e = 2/(period+1), prices[0]
    for p in prices[1:]: e = p*k + e*(1-k)
    return e

def rsi(closes, period=14):
    if len(closes) < period+1: return 50
    d = [closes[i]-closes[i-1] for i in range(1, len(closes))]
    g = sum(x for x in d[-period:] if x > 0) / period
    l = sum(-x for x in d[-period:] if x < 0) / period
    return round(100-(100/(1+g/l)), 2) if l else 100

def momentum(closes, period=10):
    if len(closes) <= period: return 0
    return round(((closes[-1]/closes[-period])-1)*100, 2)

def trend(close, e20, e50):
    if close > e20 > e50:  return 'Strong Uptrend'
    elif close > e20:       return 'Recovery'
    elif close < e20 < e50: return 'Strong Downtrend'
    elif close < e20:       return 'Pullback'
    return 'Sideways'

def tech_score(r, m, tr, vs):
    s = 50
    if 50<=r<=65: s+=15
    elif 40<=r<50: s+=5
    elif r>70: s-=10
    elif r<30: s-=15
    if m>10: s+=12
    elif m>5: s+=8
    elif m>2: s+=4
    elif m<-10: s-=12
    elif m<-5: s-=8
    elif m<-2: s-=4
    if tr=='Strong Uptrend': s+=15
    elif tr=='Recovery': s+=8
    elif tr=='Pullback': s-=5
    elif tr=='Strong Downtrend': s-=15
    if vs=='Volume Spike': s+=10
    elif vs=='High Volume': s+=5
    return max(0, min(100, s))

# ── Process single coin ───────────────────────────────────────────────────

def process_coin(symbol, all_tickers, all_funding):
    t = all_tickers.get(symbol)
    if not t:
        return None

    price      = float(t.get('lastPrice', 0))
    change_pct = round(float(t.get('priceChangePercent', 0)), 2)
    volume_usd = round(float(t.get('quoteVolume', 0)), 0)

    if price == 0:
        return None

    ohlcv = fetch_ohlcv(symbol)
    time.sleep(0.15)
    if not ohlcv:
        return None

    closes, volumes = ohlcv
    e9  = ema(closes, 9)
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    r   = rsi(closes)
    m   = momentum(closes)

    avg_v = sum(volumes[-20:])/20 if len(volumes)>=20 else volumes[-1]
    vr    = volumes[-1]/avg_v if avg_v > 0 else 1
    vs    = 'Volume Spike' if vr>=2 else 'High Volume' if vr>=1.5 else 'Normal Volume' if vr>=0.8 else 'Low Volume'
    tr    = trend(price, e20, e50)
    ts    = tech_score(r, m, tr, vs)

    # Funding
    f = all_funding.get(symbol)
    funding = None
    if f:
        rate = round(float(f.get('lastFundingRate', 0))*100, 4)
        funding = {
            'rate': rate,
            'annualized': round(rate*3*365, 1),
            'sentiment': 'Long Heavy' if rate>0.05 else 'Short Heavy' if rate<-0.05 else 'Neutral'
        }

    return {
        'symbol':          symbol,
        'name':            symbol.replace('USDT',''),
        'sector':          SECTOR_MAP.get(symbol, 'Other'),
        'price':           round(price, 6),
        'change_pct':      change_pct,
        'volume_usd':      volume_usd,
        'ema9':            round(e9, 6),
        'ema20':           round(e20, 6),
        'ema50':           round(e50, 6),
        'rsi':             r,
        'momentum':        m,
        'trend':           tr,
        'volume_signal':   vs,
        'vol_ratio':       round(vr, 2),
        'technical_score': ts,
        'funding_rate':    funding,
        'open_interest':   None,
        'ls_ratio':        None,
    }

def score_sector(coins):
    if not coins: return 0
    avg   = sum(c['technical_score'] for c in coins) / len(coins)
    bull  = sum(1 for c in coins if c['change_pct'] > 0) / len(coins)
    vb    = min(sum(1 for c in coins if c['volume_signal'] in ['Volume Spike','High Volume'])*3, 15)
    return round(min(100, avg*0.6 + bull*30 + vb), 1)

# ── Main ──────────────────────────────────────────────────────────────────

def run_market_engine():
    print("📈 Crypto Market Engine starting...")
    now = datetime.now(timezone.utc)

    print("   Fetching all tickers...")
    all_tickers = fetch_all_tickers()
    time.sleep(1)

    print("   Fetching funding rates...")
    all_funding = fetch_all_funding_rates()
    time.sleep(0.5)

    if not all_tickers:
        print("   ⚠ No ticker data — saving empty output")
        output = {
            'date': now.strftime('%Y-%m-%d'),
            'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'market_direction': 'Neutral', 'volatility_bias': 'Low',
            'breadth': {'total_pairs':0,'advancing':0,'declining':0,'breadth_ratio':50,'btc_dominance_proxy':0},
            'reference': {}, 'sectors_ranked': [], 'all_coins': [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(MARKET_OUT, 'w') as f:
            json.dump(output, f, indent=2)
        return output

    # Market breadth
    usdt = {k:v for k,v in all_tickers.items() if k.endswith('USDT') and 'DOWN' not in k}
    adv  = sum(1 for d in usdt.values() if float(d.get('priceChangePercent',0))>0)
    dec  = sum(1 for d in usdt.values() if float(d.get('priceChangePercent',0))<0)
    tot  = len(usdt)
    br   = round((adv/tot)*100,1) if tot>0 else 50
    direction = 'Bullish' if br>=60 else 'Bearish' if br<=40 else 'Neutral'

    btc_vol   = float(all_tickers.get('BTCUSDT',{}).get('quoteVolume',0))
    total_vol = sum(float(d.get('quoteVolume',0)) for d in list(usdt.values())[:100])
    btc_dom   = round((btc_vol/total_vol)*100,1) if total_vol>0 else 0

    # Reference
    reference = {}
    for sym in ['BTCUSDT','ETHUSDT']:
        t = all_tickers.get(sym)
        f = all_funding.get(sym)
        if t:
            rate = round(float(f.get('lastFundingRate',0))*100,4) if f else 0
            reference[sym.replace('USDT','')] = {
                'price':      round(float(t.get('lastPrice',0)),2),
                'change_pct': round(float(t.get('priceChangePercent',0)),2),
                'funding':    {'rate':rate,'sentiment':'Long Heavy' if rate>0.05 else 'Neutral'} if f else None,
            }

    # Process coins
    all_coins_data = []
    sector_results = {}

    for sector, coins in COINS.items():
        print(f"   {sector}...")
        sc = []
        for symbol in coins:
            data = process_coin(symbol, all_tickers, all_funding)
            if data:
                sc.append(data)
                all_coins_data.append(data)
        ss   = score_sector(sc)
        top3 = sorted(sc, key=lambda x: x['technical_score'], reverse=True)[:3]
        sector_results[sector] = {
            'score': ss, 'coin_count': len(sc),
            'top_coins': [c['name'] for c in top3],
            'avg_rsi': round(sum(c['rsi'] for c in sc)/len(sc),1) if sc else 0,
            'bullish_count': sum(1 for c in sc if c['change_pct']>0),
            'bearish_count': sum(1 for c in sc if c['change_pct']<=0),
        }

    ranked = sorted(sector_results.items(), key=lambda x: x[1]['score'], reverse=True)
    changes = [abs(c['change_pct']) for c in all_coins_data]
    avg_chg = sum(changes)/len(changes) if changes else 0
    vol_bias = 'High' if avg_chg>5 else 'Medium' if avg_chg>2 else 'Low'

    output = {
        'date': now.strftime('%Y-%m-%d'),
        'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'market_direction': direction,
        'volatility_bias': vol_bias,
        'breadth': {'total_pairs':tot,'advancing':adv,'declining':dec,'breadth_ratio':br,'btc_dominance_proxy':btc_dom},
        'reference': reference,
        'sectors_ranked': [{'name':n,**d} for n,d in ranked],
        'all_coins': all_coins_data,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Market Engine done — {len(all_coins_data)} coins, BTC ${reference.get('BTC',{}).get('price','N/A')}")
    return output

if __name__ == '__main__':
    run_market_engine()
