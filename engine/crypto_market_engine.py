"""
COSMO CRYPTO - Market Engine
Delta Exchange India public API.
Confirmed symbol format: SOLUSD, DOGEUSD, 1000PEPEUSD etc.
"""

import requests
import json
import os
import time
from datetime import datetime, timezone

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
MARKET_OUT = os.path.join(DATA_DIR, 'market_data.json')
BASE_URL   = 'https://api.india.delta.exchange'

# ── Coin universe — exact Delta Exchange USD perpetual symbols ────────────
COINS = {
    'L1':     [('SOL','SOLUSD'),('BNB','BNBUSD'),('XRP','XRPUSD'),('ADA','ADAUSD'),
               ('AVAX','AVAXUSD'),('DOT','DOTUSD'),('ATOM','ATOMUSD'),('APT','APTUSD'),
               ('SUI','SUIUSD'),('TIA','TIAUSD')],
    'DeFi':   [('LINK','LINKUSD'),('UNI','UNIUSD'),('AAVE','AAVEUSD'),('LDO','LDOUSD'),('ENA','ENAUSD')],
    'L2':     [('POL','POLUSD'),('ARB','ARBUSD'),('OP','OPUSD'),('STRK','STRKUSD')],
    'Infra':  [('INJ','INJUSD'),('SEI','SEIUSD'),('RUNE','RUNEUSD'),('TAO','TAOUSD')],
    'Meme':   [('DOGE','DOGEUSD'),('1000SHIB','1000SHIBUSD'),('1000PEPE','1000PEPEUSD'),('1000FLOKI','1000FLOKIUSD')],
    'Gaming': [('AXS','AXSUSD'),('SAND','SANDUSD'),('MANA','MANAUSD'),('IMX','IMXUSD')],
}

# Flat maps
NAME_TO_SYMBOL = {name: sym for coins in COINS.values() for name, sym in coins}
SYMBOL_TO_NAME = {sym: name for name, sym in NAME_TO_SYMBOL.items()}
SECTOR_MAP     = {name: sector for sector, coins in COINS.items() for name, sym in coins}
DISPLAY_NAME   = {name: name.replace('1000','') for name, sym in NAME_TO_SYMBOL.items()}

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})

def safe_get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            print(f"   HTTP {r.status_code}: {url}")
        except Exception as e:
            if i == retries - 1:
                print(f"   ⚠ {e}")
            time.sleep(2)
    return None

def fetch_all_tickers():
    data = safe_get(f"{BASE_URL}/v2/tickers")
    if not data or not data.get('success'):
        return {}
    tickers = data.get('result', [])
    ticker_map = {t.get('symbol',''): t for t in tickers}
    print(f"   ✅ {len(ticker_map)} tickers from Delta Exchange")
    return ticker_map

def fetch_ohlcv(symbol, limit=60):
    end_time   = int(datetime.now(timezone.utc).timestamp())
    start_time = end_time - (limit * 86400)
    data = safe_get(f"{BASE_URL}/v2/history/candles", {
        'resolution': '1d', 'symbol': symbol,
        'start': start_time, 'end': end_time,
    })
    if not data or not data.get('success'):
        return None
    candles = data.get('result', [])
    if len(candles) < 5:
        return None
    closes  = [float(c.get('close', 0)) for c in candles]
    volumes = [float(c.get('volume', 0)) for c in candles]
    return closes, volumes

def fetch_funding_rate(symbol):
    data = safe_get(f"{BASE_URL}/v2/tickers/{symbol}")
    if not data or not data.get('success'):
        return None
    result = data.get('result', {})
    rate   = float(result.get('funding_rate', 0)) * 100
    if rate == 0:
        return None
    return {
        'rate':       round(rate, 4),
        'annualized': round(rate * 3 * 365, 1),
        'sentiment':  'Long Heavy' if rate>0.05 else 'Short Heavy' if rate<-0.05 else 'Neutral',
    }

def ema(prices, period):
    if not prices: return 0
    k, e = 2/(period+1), prices[0]
    for p in prices[1:]: e = p*k + e*(1-k)
    return e

def rsi_calc(closes, period=14):
    if len(closes) < period+1: return 50
    d = [closes[i]-closes[i-1] for i in range(1, len(closes))]
    g = sum(x for x in d[-period:] if x > 0) / period
    l = sum(-x for x in d[-period:] if x < 0) / period
    return round(100-(100/(1+g/l)), 2) if l else 100

def momentum_calc(closes, period=10):
    if len(closes) <= period: return 0
    return round(((closes[-1]/closes[-period])-1)*100, 2)

def trend_label(close, e20, e50):
    if close > e20 > e50:   return 'Strong Uptrend'
    elif close > e20:        return 'Recovery'
    elif close < e20 < e50:  return 'Strong Downtrend'
    elif close < e20:        return 'Pullback'
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

def process_coin(name, delta_symbol, ticker_map):
    ticker = ticker_map.get(delta_symbol)
    if not ticker:
        return None

    price  = float(ticker.get('close', ticker.get('mark_price', 0)))
    open_p = float(ticker.get('open', price))
    vol    = float(ticker.get('volume', ticker.get('turnover_usd', 0)))

    if price == 0:
        return None

    chg_pct = round(((price - open_p) / open_p) * 100, 2) if open_p > 0 else 0

    # OHLCV
    ohlcv = fetch_ohlcv(delta_symbol)
    time.sleep(0.2)

    if ohlcv and len(ohlcv[0]) >= 10:
        closes, volumes = ohlcv
        e9  = ema(closes, 9)
        e20 = ema(closes, 20) if len(closes)>=20 else ema(closes, len(closes))
        e50 = ema(closes, 50) if len(closes)>=50 else e20
        r   = rsi_calc(closes)
        m   = momentum_calc(closes)
        avg_v = sum(volumes[-20:])/20 if len(volumes)>=20 else (volumes[-1] if volumes else 1)
        cur_v = volumes[-1] if volumes else 0
        vr    = cur_v/avg_v if avg_v > 0 else 1
        vs    = 'Volume Spike' if vr>=2 else 'High Volume' if vr>=1.5 else 'Normal Volume' if vr>=0.8 else 'Low Volume'
        tr    = trend_label(price, e20, e50)
        ts    = tech_score(r, m, tr, vs)
    else:
        e9=e20=e50=price; r=50; m=chg_pct; vs='Normal Volume'; vr=1.0
        tr = 'Recovery' if chg_pct > 0 else 'Pullback'
        ts = tech_score(r, m, tr, vs)

    # Funding
    funding = fetch_funding_rate(delta_symbol)
    time.sleep(0.1)

    display = DISPLAY_NAME.get(name, name)

    return {
        'symbol':          delta_symbol,
        'name':            display,
        'sector':          SECTOR_MAP.get(name, 'Other'),
        'price':           round(price, 6),
        'change_pct':      chg_pct,
        'volume_usd':      round(vol, 0),
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
    avg  = sum(c['technical_score'] for c in coins) / len(coins)
    bull = sum(1 for c in coins if c['change_pct'] > 0) / len(coins)
    vb   = min(sum(1 for c in coins if c['volume_signal'] in ['Volume Spike','High Volume'])*3, 15)
    return round(min(100, avg*0.6 + bull*30 + vb), 1)

def run_market_engine():
    print("📈 Crypto Market Engine (Delta Exchange India) starting...")
    now = datetime.now(timezone.utc)

    print("   Fetching all tickers...")
    ticker_map = fetch_all_tickers()
    time.sleep(0.5)

    if not ticker_map:
        print("   ⚠ No ticker data")
        output = {
            'date': now.strftime('%Y-%m-%d'), 'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'market_direction': 'Neutral', 'volatility_bias': 'Low',
            'breadth': {'total_pairs':0,'advancing':0,'declining':0,'breadth_ratio':50,'btc_dominance_proxy':0},
            'reference': {}, 'sectors_ranked': [], 'all_coins': [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(MARKET_OUT, 'w') as f:
            json.dump(output, f, indent=2)
        return output

    # Breadth from all tickers
    all_t = list(ticker_map.values())
    adv   = sum(1 for t in all_t if float(t.get('change', 0) or 0) > 0)
    dec   = len(all_t) - adv
    br    = round((adv/len(all_t))*100, 1) if all_t else 50
    direction = 'Bullish' if br>=60 else 'Bearish' if br<=40 else 'Neutral'

    # BTC/ETH reference
    reference = {}
    for coin, sym in [('BTC','BTCUSD'),('ETH','ETHUSD')]:
        t = ticker_map.get(sym)
        if t:
            price  = float(t.get('close', t.get('mark_price', 0)))
            open_p = float(t.get('open', price))
            chg    = round(((price-open_p)/open_p)*100, 2) if open_p > 0 else 0
            reference[coin] = {'price': round(price,2), 'change_pct': chg, 'funding': None}

    # Process all coins
    all_coins_data = []
    sector_results = {}

    for sector, coin_pairs in COINS.items():
        print(f"   {sector}...")
        sc = []
        for name, delta_sym in coin_pairs:
            data = process_coin(name, delta_sym, ticker_map)
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

    ranked   = sorted(sector_results.items(), key=lambda x: x[1]['score'], reverse=True)
    changes  = [abs(c['change_pct']) for c in all_coins_data]
    avg_chg  = sum(changes)/len(changes) if changes else 0
    vol_bias = 'High' if avg_chg>5 else 'Medium' if avg_chg>2 else 'Low'

    output = {
        'date': now.strftime('%Y-%m-%d'), 'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'market_direction': direction, 'volatility_bias': vol_bias,
        'breadth': {'total_pairs':len(all_t),'advancing':adv,'declining':dec,'breadth_ratio':br,'btc_dominance_proxy':0},
        'reference': reference,
        'sectors_ranked': [{'name':n,**d} for n,d in ranked],
        'all_coins': all_coins_data,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Done — {len(all_coins_data)} coins")
    print(f"   BTC: ${reference.get('BTC',{}).get('price','N/A')} ({reference.get('BTC',{}).get('change_pct','?')}%)")
    print(f"   ETH: ${reference.get('ETH',{}).get('price','N/A')}")
    print(f"   Direction: {direction} | Breadth: {br}%")
    return output

if __name__ == '__main__':
    run_market_engine()
