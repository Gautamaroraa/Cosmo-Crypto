"""
COSMO CRYPTO - F&O Engine
Delta Exchange India public API.
OI, Funding Rates, Long/Short data — all from Delta tickers.
No API key required.
"""

import requests
import json
import os
import time
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
FNO_OUT  = os.path.join(DATA_DIR, 'fno.json')
BASE_URL = 'https://api.india.delta.exchange'

FNO_COINS = [
    'SOLUSD','BNBUSD','XRPUSD','ADAUSD','AVAXUSD',
    'DOTUSD','LINKUSD','ARBUSD','OPUSD','INJUSD',
    'APTUSD','SUIUSD','DOGEUSD','ATOMUSD','UNIUSD',
    'BTCUSD','ETHUSD',
]

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})

def safe_get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            if i == retries - 1:
                print(f"   ⚠ {e}")
            time.sleep(2)
    return None

def fetch_all_tickers():
    data = safe_get(f"{BASE_URL}/v2/tickers")
    if not data or not data.get('success'):
        return {}
    return {t.get('symbol',''): t for t in data.get('result', [])}

def fetch_single_ticker(symbol):
    data = safe_get(f"{BASE_URL}/v2/tickers/{symbol}")
    if not data or not data.get('success'):
        return None
    return data.get('result', {})

# ── OI Analysis ───────────────────────────────────────────────────────────

def analyze_oi(all_tickers):
    """Top coins by OI, OI change."""
    perps = []
    for sym, t in all_tickers.items():
        if not sym.endswith('USD') or '_' in sym:
            continue
        oi_usd    = float(t.get('oi_value_usd', 0) or 0)
        oi_chg    = float(t.get('oi_change_usd_6h', 0) or 0)
        price     = float(t.get('close', t.get('mark_price', 0)) or 0)
        open_p    = float(t.get('open', price) or price)
        chg_pct   = round(((price-open_p)/open_p)*100, 2) if open_p > 0 else 0
        if oi_usd > 0:
            perps.append({
                'symbol':       sym,
                'name':         sym.replace('USD',''),
                'oi_usd':       round(oi_usd, 0),
                'oi_change_6h': round(oi_chg, 0),
                'price':        round(price, 4),
                'change_pct':   chg_pct,
            })

    perps.sort(key=lambda x: x['oi_usd'], reverse=True)
    top_oi     = perps[:10]
    rising_oi  = sorted([p for p in perps if p['oi_change_6h'] > 0], key=lambda x: x['oi_change_6h'], reverse=True)[:5]
    falling_oi = sorted([p for p in perps if p['oi_change_6h'] < 0], key=lambda x: x['oi_change_6h'])[:5]

    return {
        'top_oi':    top_oi,
        'rising_oi': rising_oi,
        'falling_oi': falling_oi,
    }

# ── Funding Rate Analysis ─────────────────────────────────────────────────

def analyze_funding(all_tickers):
    """Funding rates for all perpetuals."""
    funding_data = []
    for sym, t in all_tickers.items():
        if not sym.endswith('USD') or '_' in sym:
            continue
        rate = float(t.get('funding_rate', 0) or 0) * 100
        if rate == 0:
            continue
        annual = round(rate * 3 * 365, 1)
        sentiment = 'Strongly Long' if rate > 0.1 else \
                    'Long Heavy'    if rate > 0.05 else \
                    'Slightly Long' if rate > 0.01 else \
                    'Short Heavy'   if rate < -0.05 else \
                    'Slightly Short' if rate < -0.01 else 'Neutral'
        signal = 'BEARISH' if rate > 0.1 else 'BULLISH' if rate < -0.05 else 'NEUTRAL'
        funding_data.append({
            'symbol':     sym,
            'name':       sym.replace('USD',''),
            'rate':       round(rate, 4),
            'annualized': annual,
            'sentiment':  sentiment,
            'signal':     signal,
        })

    funding_data.sort(key=lambda x: abs(x['rate']), reverse=True)

    high_funding = [f for f in funding_data if f['rate'] > 0.05]
    neg_funding  = [f for f in funding_data if f['rate'] < -0.02]

    return {
        'all':          funding_data[:20],
        'high_funding': high_funding[:5],
        'neg_funding':  neg_funding[:5],
    }

# ── Market Structure ──────────────────────────────────────────────────────

def analyze_market_structure(all_tickers):
    """Top gainers, losers, volume leaders."""
    perps = []
    for sym, t in all_tickers.items():
        if not sym.endswith('USD') or '_' in sym:
            continue
        price  = float(t.get('close', 0) or 0)
        open_p = float(t.get('open', price) or price)
        vol    = float(t.get('turnover_usd', 0) or 0)
        chg    = round(((price-open_p)/open_p)*100, 2) if open_p > 0 else 0
        if price > 0:
            perps.append({'symbol': sym, 'name': sym.replace('USD',''), 'change_pct': chg, 'volume_usd': vol})

    top_gainers = sorted(perps, key=lambda x: x['change_pct'], reverse=True)[:5]
    top_losers  = sorted(perps, key=lambda x: x['change_pct'])[:5]
    top_volume  = sorted(perps, key=lambda x: x['volume_usd'], reverse=True)[:5]

    return {
        'top_gainers': top_gainers,
        'top_losers':  top_losers,
        'top_volume':  top_volume,
    }

# ── Per-coin F&O detail ───────────────────────────────────────────────────

def build_coin_fno(all_tickers):
    """Per-coin F&O data for our tracked coins."""
    coin_data = {}
    for symbol in FNO_COINS:
        t = all_tickers.get(symbol)
        if not t:
            continue
        name      = symbol.replace('USD','')
        price     = float(t.get('close', 0) or 0)
        oi_usd    = float(t.get('oi_value_usd', 0) or 0)
        oi_chg    = float(t.get('oi_change_usd_6h', 0) or 0)
        rate      = float(t.get('funding_rate', 0) or 0) * 100
        oi_trend  = 'Rising' if oi_chg > 0 else 'Falling' if oi_chg < 0 else 'Stable'
        sentiment = 'Long Heavy' if rate>0.05 else 'Short Heavy' if rate<-0.05 else 'Neutral'

        coin_data[symbol] = {
            'name':     name,
            'symbol':   symbol,
            'price':    round(price, 4),
            'oi_usd':   round(oi_usd, 0),
            'oi_trend': oi_trend,
            'oi_change_6h': round(oi_chg, 0),
            'funding': {
                'rate':       round(rate, 4),
                'annualized': round(rate*3*365, 1),
                'sentiment':  sentiment,
            } if rate != 0 else None,
            'ls_ratio': None,
        }

    return coin_data

# ── F&O Signals ───────────────────────────────────────────────────────────

def build_signals(oi_data, funding_data, structure):
    signals = []

    # High funding
    if funding_data['high_funding']:
        names = ', '.join(f['name'] for f in funding_data['high_funding'][:3])
        signals.append(f"High funding rates: {names} — longs overcrowded, reversal risk")

    # Negative funding
    if funding_data['neg_funding']:
        names = ', '.join(f['name'] for f in funding_data['neg_funding'][:3])
        signals.append(f"Negative funding: {names} — shorts paying, potential squeeze")

    # Rising OI
    if oi_data['rising_oi']:
        names = ', '.join(c['name'] for c in oi_data['rising_oi'][:3])
        signals.append(f"Rising OI (6h): {names} — fresh positions building")

    # Top gainers
    if structure['top_gainers']:
        names = ', '.join(f"{c['name']} +{c['change_pct']}%" for c in structure['top_gainers'][:3])
        signals.append(f"Top gainers today: {names}")

    # Top volume
    if structure['top_volume']:
        names = ', '.join(c['name'] for c in structure['top_volume'][:3])
        signals.append(f"Highest volume: {names}")

    return signals

# ── Main F&O Engine ───────────────────────────────────────────────────────

def run_fno_engine():
    print("\n📊 Crypto F&O Engine (Delta Exchange India) starting...")
    now = datetime.now(timezone.utc)

    print("   Fetching all tickers...")
    all_tickers = fetch_all_tickers()
    time.sleep(0.3)

    if not all_tickers:
        print("   ⚠ No ticker data")
        output = {
            'meta': {'date': now.strftime('%Y-%m-%d'), 'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ')},
            'signals': [], 'coins': {}, 'btc_options': None, 'eth_options': None, 'overview': {},
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(FNO_OUT, 'w') as f:
            json.dump(output, f, indent=2)
        return output

    print("   Analyzing OI...")
    oi_data = analyze_oi(all_tickers)

    print("   Analyzing funding rates...")
    funding_data = analyze_funding(all_tickers)

    print("   Analyzing market structure...")
    structure = analyze_market_structure(all_tickers)

    print("   Building per-coin F&O data...")
    coin_data = build_coin_fno(all_tickers)

    signals = build_signals(oi_data, funding_data, structure)

    output = {
        'meta': {
            'date':         now.strftime('%Y-%m-%d'),
            'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'signals':     signals,
        'coins':       coin_data,
        'oi_analysis': oi_data,
        'funding':     funding_data,
        'structure':   structure,
        'btc_options': None,
        'eth_options': None,
        'overview':    {
            'top_gainers': structure['top_gainers'],
            'top_losers':  structure['top_losers'],
            'top_volume':  structure['top_volume'],
        },
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FNO_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ F&O Engine complete → {FNO_OUT}")
    for sig in signals:
        print(f"   → {sig}")

    return output

if __name__ == '__main__':
    run_fno_engine()
