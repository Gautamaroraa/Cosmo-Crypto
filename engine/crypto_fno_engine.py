"""
COSMO CRYPTO - F&O Engine
Binance Futures & Options data. No API key required.
Covers: OI, Funding Rates, Long/Short Ratio, Liquidations, BTC/ETH Options Chain
"""

import requests
import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
FNO_OUT  = os.path.join(DATA_DIR, 'fno.json')

FUTURES_BASE = 'https://fapi.binance.com'
OPTIONS_BASE = 'https://eapi.binance.com'
SPOT_BASE    = 'https://api.binance.com'

# ── Coin universe for F&O ─────────────────────────────────────────────────
FNO_COINS = [
    'SOLUSDT','BNBUSDT','XRPUSDT','ADAUSDT','AVAXUSDT',
    'DOTUSDT','LINKUSDT','MATICUSDT','ARBUSDT','OPUSDT',
    'INJUSDT','APTUSDT','SUIUSDT','DOGEUSDT','ATOMUSDT',
]

def safe_get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            if i == retries - 1:
                print(f"   ⚠ {url}: {e}")
    return None

# ── Open Interest ─────────────────────────────────────────────────────────

def fetch_open_interest(symbol):
    data = safe_get(f"{FUTURES_BASE}/fapi/v1/openInterest", {'symbol': symbol})
    if not data:
        return None
    oi = float(data.get('openInterest', 0))
    price_data = safe_get(f"{SPOT_BASE}/api/v3/ticker/price", {'symbol': symbol})
    price = float(price_data.get('price', 0)) if price_data else 0
    oi_usd = round(oi * price, 0)
    return {'oi_coins': round(oi, 2), 'oi_usd': oi_usd}

def fetch_oi_history(symbol):
    """OI change over last 5 periods — trend detection."""
    data = safe_get(f"{FUTURES_BASE}/futures/data/openInterestHist",
                    {'symbol': symbol, 'period': '1h', 'limit': 5})
    if not data or not isinstance(data, list):
        return None
    oi_values = [float(d.get('sumOpenInterest', 0)) for d in data]
    if len(oi_values) >= 2:
        oi_change_pct = round(((oi_values[-1] - oi_values[0]) / oi_values[0]) * 100, 2) if oi_values[0] > 0 else 0
        trend = 'Rising' if oi_change_pct > 1 else 'Falling' if oi_change_pct < -1 else 'Stable'
        return {'oi_change_5h_pct': oi_change_pct, 'trend': trend, 'latest_oi': oi_values[-1]}
    return None

# ── Funding Rate ──────────────────────────────────────────────────────────

def fetch_funding_rate(symbol):
    data = safe_get(f"{FUTURES_BASE}/fapi/v1/fundingRate", {'symbol': symbol, 'limit': 3})
    if not data or not isinstance(data, list):
        return None
    latest = data[-1]
    rate   = round(float(latest.get('fundingRate', 0)) * 100, 4)
    annual = round(rate * 3 * 365, 1)  # 3 funding events per day
    sentiment = 'Strongly Long Heavy' if rate > 0.1 else \
                'Long Heavy' if rate > 0.05 else \
                'Slightly Long' if rate > 0.01 else \
                'Short Heavy' if rate < -0.05 else \
                'Slightly Short' if rate < -0.01 else 'Neutral'
    signal = 'BEARISH' if rate > 0.1 else 'BULLISH' if rate < -0.05 else 'NEUTRAL'
    return {
        'rate':       rate,
        'annualized': annual,
        'sentiment':  sentiment,
        'signal':     signal,
        'next_funding': data[-1].get('fundingTime'),
    }

# ── Long/Short Ratio ──────────────────────────────────────────────────────

def fetch_ls_ratio(symbol):
    data = safe_get(f"{FUTURES_BASE}/futures/data/globalLongShortAccountRatio",
                    {'symbol': symbol, 'period': '1h', 'limit': 3})
    if not data or not isinstance(data, list):
        return None
    latest = data[-1]
    ratio  = round(float(latest.get('longShortRatio', 1)), 3)
    long_pct  = round(float(latest.get('longAccount', 0.5)) * 100, 1)
    short_pct = round(float(latest.get('shortAccount', 0.5)) * 100, 1)
    sentiment = 'Long Dominated' if ratio > 1.5 else \
                'Slightly Long'  if ratio > 1.1 else \
                'Short Dominated' if ratio < 0.7 else \
                'Slightly Short'  if ratio < 0.9 else 'Balanced'
    # Contrarian signal — extreme longs = bearish, extreme shorts = bullish
    contrarian = 'BEARISH' if ratio > 1.8 else 'BULLISH' if ratio < 0.6 else 'NEUTRAL'
    return {
        'ratio':      ratio,
        'long_pct':   long_pct,
        'short_pct':  short_pct,
        'sentiment':  sentiment,
        'contrarian': contrarian,
    }

# ── Liquidation Data ──────────────────────────────────────────────────────

def fetch_liquidation_stats(symbol):
    """Recent liquidation orders — proxy for volatility."""
    data = safe_get(f"{FUTURES_BASE}/fapi/v1/allForceOrders",
                    {'symbol': symbol, 'limit': 50})
    if not data or not isinstance(data, list):
        return None
    long_liq  = sum(float(d.get('origQty', 0)) for d in data if d.get('side') == 'SELL')
    short_liq = sum(float(d.get('origQty', 0)) for d in data if d.get('side') == 'BUY')
    total = long_liq + short_liq
    dominant = 'Long Liquidations' if long_liq > short_liq else 'Short Liquidations'
    return {
        'long_liq':   round(long_liq, 2),
        'short_liq':  round(short_liq, 2),
        'total':      round(total, 2),
        'dominant':   dominant,
    }

# ── Top Trader Sentiment ──────────────────────────────────────────────────

def fetch_top_trader_sentiment(symbol):
    data = safe_get(f"{FUTURES_BASE}/futures/data/topLongShortPositionRatio",
                    {'symbol': symbol, 'period': '1h', 'limit': 1})
    if not data or not isinstance(data, list):
        return None
    latest = data[0]
    ratio  = round(float(latest.get('longShortRatio', 1)), 3)
    return {
        'ratio':     ratio,
        'sentiment': 'Smart Money Long' if ratio > 1.2 else 'Smart Money Short' if ratio < 0.8 else 'Mixed',
    }

# ── Options Chain (BTC + ETH only) ───────────────────────────────────────

def fetch_options_mark_price(underlying='BTC'):
    """Fetch options mark prices from Binance European Options."""
    data = safe_get(f"{OPTIONS_BASE}/eapi/v1/mark", {'underlying': underlying + 'USDT'})
    if not data or not isinstance(data, list):
        return None

    # Group by expiry
    by_expiry = {}
    for opt in data:
        symbol    = opt.get('symbol', '')
        parts     = symbol.split('-')
        if len(parts) < 4:
            continue
        expiry    = parts[1]
        strike    = float(parts[2])
        opt_type  = parts[3]  # C or P
        mark_price = float(opt.get('markPrice', 0))
        iv         = float(opt.get('markIV', 0))

        if expiry not in by_expiry:
            by_expiry[expiry] = {'calls': [], 'puts': []}

        if opt_type == 'C':
            by_expiry[expiry]['calls'].append({'strike': strike, 'mark': mark_price, 'iv': iv})
        else:
            by_expiry[expiry]['puts'].append({'strike': strike, 'mark': mark_price, 'iv': iv})

    return by_expiry

def analyze_options(underlying='BTC'):
    """Analyze options chain for PCR, max pain, IV skew."""
    options_data = fetch_options_mark_price(underlying)
    if not options_data:
        return None

    # Use nearest expiry
    expiries = sorted(options_data.keys())
    if not expiries:
        return None

    nearest = expiries[0]
    calls   = options_data[nearest]['calls']
    puts    = options_data[nearest]['puts']

    if not calls or not puts:
        return None

    # PCR by count
    pcr = round(len(puts) / len(calls), 2) if calls else None

    # IV Analysis — fear gauge
    avg_call_iv = round(sum(c['iv'] for c in calls) / len(calls), 2) if calls else 0
    avg_put_iv  = round(sum(p['iv'] for p in puts) / len(puts), 2) if puts else 0
    iv_skew     = round(avg_put_iv - avg_call_iv, 2)
    fear_gauge  = 'Extreme Fear' if iv_skew > 20 else \
                  'Fear' if iv_skew > 10 else \
                  'Greed' if iv_skew < -5 else 'Neutral'

    # Max strike OI proxy (by count of options at that strike)
    call_strikes = {}
    for c in calls:
        s = c['strike']
        call_strikes[s] = call_strikes.get(s, 0) + 1

    put_strikes = {}
    for p in puts:
        s = p['strike']
        put_strikes[s] = put_strikes.get(s, 0) + 1

    max_call_strike = max(call_strikes, key=call_strikes.get) if call_strikes else None
    max_put_strike  = max(put_strikes,  key=put_strikes.get)  if put_strikes  else None

    return {
        'underlying':     underlying,
        'nearest_expiry': nearest,
        'pcr':            pcr,
        'avg_call_iv':    avg_call_iv,
        'avg_put_iv':     avg_put_iv,
        'iv_skew':        iv_skew,
        'fear_gauge':     fear_gauge,
        'max_call_strike': max_call_strike,
        'max_put_strike':  max_put_strike,
        'total_calls':    len(calls),
        'total_puts':     len(puts),
    }

# ── Market-wide Futures Overview ──────────────────────────────────────────

def fetch_futures_overview():
    """Top gainers/losers in futures, total market OI."""
    data = safe_get(f"{FUTURES_BASE}/fapi/v1/ticker/24hr")
    if not data or not isinstance(data, list):
        return {}

    usdt_pairs = [d for d in data if d['symbol'].endswith('USDT')]
    sorted_by_change = sorted(usdt_pairs, key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)

    top_gainers = [{'symbol': d['symbol'].replace('USDT',''), 'change_pct': round(float(d['priceChangePercent']),2)} for d in sorted_by_change[:5]]
    top_losers  = [{'symbol': d['symbol'].replace('USDT',''), 'change_pct': round(float(d['priceChangePercent']),2)} for d in sorted_by_change[-5:]]

    # High OI coins
    high_oi = sorted(usdt_pairs, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)[:5]
    top_volume = [{'symbol': d['symbol'].replace('USDT',''), 'volume_usd': round(float(d['quoteVolume']),0)} for d in high_oi]

    return {
        'top_gainers': top_gainers,
        'top_losers':  top_losers,
        'top_volume':  top_volume,
    }

# ── F&O Intelligence Signals ──────────────────────────────────────────────

def build_fno_signals(coin_data, btc_options, eth_options, overview):
    signals = []

    # Extreme funding rates
    high_funding = [(s, d) for s, d in coin_data.items() if d.get('funding') and d['funding']['rate'] > 0.08]
    if high_funding:
        names = ', '.join(s.replace('USDT','') for s, _ in high_funding[:3])
        signals.append(f"High funding: {names} — longs overcrowded, reversal risk")

    neg_funding = [(s, d) for s, d in coin_data.items() if d.get('funding') and d['funding']['rate'] < -0.05]
    if neg_funding:
        names = ', '.join(s.replace('USDT','') for s, _ in neg_funding[:3])
        signals.append(f"Negative funding: {names} — shorts paying, potential squeeze")

    # Rising OI
    rising_oi = [(s, d) for s, d in coin_data.items() if d.get('oi_hist') and d['oi_hist']['trend'] == 'Rising']
    if rising_oi:
        names = ', '.join(s.replace('USDT','') for s, _ in rising_oi[:3])
        signals.append(f"Rising OI: {names} — fresh positions being built")

    # BTC options fear gauge
    if btc_options and btc_options.get('fear_gauge') != 'Neutral':
        signals.append(f"BTC Options: {btc_options['fear_gauge']} (IV Skew: {btc_options['iv_skew']})")

    # ETH options
    if eth_options and eth_options.get('fear_gauge') != 'Neutral':
        signals.append(f"ETH Options: {eth_options['fear_gauge']} (IV Skew: {eth_options['iv_skew']})")

    # Top futures movers
    if overview.get('top_gainers'):
        gainers = ', '.join(c['symbol'] for c in overview['top_gainers'][:3])
        signals.append(f"Futures top gainers: {gainers}")

    return signals

# ── Main F&O Engine ───────────────────────────────────────────────────────

def run_fno_engine():
    print("\n📊 Crypto F&O Engine starting...")
    now = datetime.now(timezone.utc)

    coin_data = {}

    for symbol in FNO_COINS:
        print(f"   {symbol}...")
        name = symbol.replace('USDT', '')
        oi       = fetch_open_interest(symbol)
        oi_hist  = fetch_oi_history(symbol)
        funding  = fetch_funding_rate(symbol)
        ls       = fetch_ls_ratio(symbol)
        liq      = fetch_liquidation_stats(symbol)
        smart    = fetch_top_trader_sentiment(symbol)

        coin_data[symbol] = {
            'name':     name,
            'symbol':   symbol,
            'oi':       oi,
            'oi_hist':  oi_hist,
            'funding':  funding,
            'ls_ratio': ls,
            'liquidations': liq,
            'smart_money':  smart,
        }

    # Options analysis
    print("   BTC Options...")
    btc_options = analyze_options('BTC')
    print("   ETH Options...")
    eth_options = analyze_options('ETH')

    # Market overview
    print("   Futures overview...")
    overview = fetch_futures_overview()

    # Signals
    signals = build_fno_signals(coin_data, btc_options, eth_options, overview)

    output = {
        'meta': {
            'date':         now.strftime('%Y-%m-%d'),
            'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'signals':      signals,
        'coins':        coin_data,
        'btc_options':  btc_options,
        'eth_options':  eth_options,
        'overview':     overview,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FNO_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Crypto F&O Engine complete → {FNO_OUT}")
    for sig in signals:
        print(f"   → {sig}")

    return output

if __name__ == '__main__':
    run_fno_engine()
