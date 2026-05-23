"""
COSMO - Market Engine
Layer 2: Reads live stock market data from Yahoo Finance
Outputs: price, volume, EMA, RSI, momentum, sector performance, trend structure
"""

import yfinance as yf
import json
import os
from datetime import datetime, timezone
import pandas as pd

# ── Indian Stock Universe (NSE) ────────────────────────────────────────────
# Format: Yahoo Finance uses .NS suffix for NSE stocks

SECTORS = {
    'Banking': [
        'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
        'KOTAKBANK.NS', 'INDUSINDBK.NS', 'BANKBARODA.NS', 'PNB.NS'
    ],
    'IT': [
        'TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS',
        'TECHM.NS', 'LTIM.NS', 'MPHASIS.NS', 'PERSISTENT.NS'
    ],
    'Energy': [
        'RELIANCE.NS', 'ONGC.NS', 'BPCL.NS', 'IOC.NS',
        'GAIL.NS', 'POWERGRID.NS', 'NTPC.NS', 'ADANIGREEN.NS'
    ],
    'Pharma': [
        'SUNPHARMA.NS', 'DRREDDY.NS', 'CIPLA.NS', 'DIVISLAB.NS',
        'APOLLOHOSP.NS', 'TORNTPHARM.NS', 'LUPIN.NS', 'AUROPHARMA.NS'
    ],
    'Auto': [
        'MARUTI.NS', 'TATAMOTORS.NS', 'M&M.NS', 'BAJAJ-AUTO.NS',
        'HEROMOTOCO.NS', 'EICHERMOT.NS', 'ASHOKLEY.NS', 'TVSMOTOR.NS'
    ],
    'FMCG': [
        'HINDUNILVR.NS', 'ITC.NS', 'NESTLEIND.NS', 'BRITANNIA.NS',
        'DABUR.NS', 'MARICO.NS', 'COLPAL.NS', 'GODREJCP.NS'
    ],
    'Metals': [
        'TATASTEEL.NS', 'JSWSTEEL.NS', 'HINDALCO.NS', 'VEDL.NS',
        'SAIL.NS', 'NMDC.NS', 'COALINDIA.NS', 'JINDALSTEL.NS'
    ],
    'Infra': [
        'LT.NS', 'ULTRACEMCO.NS', 'ADANIPORTS.NS', 'DLF.NS',
        'GRASIM.NS', 'SHREECEM.NS', 'AMBUJACEM.NS', 'ACC.NS'
    ],
    'Finance': [
        'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'HDFCLIFE.NS', 'SBILIFE.NS',
        'MUTHOOTFIN.NS', 'CHOLAFIN.NS', 'ICICIGI.NS', 'PNBHOUSING.NS'
    ],
    'Consumer': [
        'TITAN.NS', 'ASIANPAINT.NS', 'PIDILITIND.NS', 'HAVELLS.NS',
        'VOLTAS.NS', 'WHIRLPOOL.NS', 'VGUARD.NS', 'CROMPTON.NS'
    ]
}

# Index trackers
INDICES = {
    'NIFTY50':    '^NSEI',
    'SENSEX':     '^BSESN',
    'NIFTYBANK':  '^NSEBANK',
    'NIFTYIT':    '^CNXIT',
    'NIFTYPHARMA': '^CNXPHARMA',
    'NIFTYAUTO':  '^CNXAUTO',
    'NIFTYFMCG':  '^CNXFMCG',
    'NIFTYMETAL':  '^CNXMETAL',
}

# ── Technical Indicators ──────────────────────────────────────────────────

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_momentum(series, period=10):
    """Price momentum: current / price N periods ago - 1"""
    return ((series / series.shift(period)) - 1) * 100

def get_trend_structure(close, ema20, ema50):
    """
    Returns trend label based on EMA structure.
    """
    c = close.iloc[-1]
    e20 = ema20.iloc[-1]
    e50 = ema50.iloc[-1]

    if c > e20 > e50:
        return 'Strong Uptrend'
    elif c > e20 and e20 < e50:
        return 'Recovery'
    elif c < e20 < e50:
        return 'Strong Downtrend'
    elif c < e20 and e20 > e50:
        return 'Pullback'
    else:
        return 'Sideways'

def get_volume_signal(volume, avg_volume):
    ratio = volume / avg_volume if avg_volume > 0 else 1
    if ratio >= 2.0:
        return 'Volume Breakout'
    elif ratio >= 1.5:
        return 'High Volume'
    elif ratio >= 1.0:
        return 'Normal Volume'
    else:
        return 'Low Volume'

def calculate_technical_score(rsi, momentum, trend, volume_signal, price_vs_ema20):
    """
    Returns technical score 0-100.
    """
    score = 50

    # RSI
    if 50 <= rsi <= 65:
        score += 15
    elif 40 <= rsi < 50:
        score += 5
    elif rsi > 70:
        score -= 10  # Overbought
    elif rsi < 30:
        score -= 15  # Oversold

    # Momentum
    if momentum > 5:
        score += 10
    elif momentum > 2:
        score += 5
    elif momentum < -5:
        score -= 10
    elif momentum < -2:
        score -= 5

    # Trend
    if trend == 'Strong Uptrend':
        score += 15
    elif trend == 'Recovery':
        score += 8
    elif trend == 'Pullback':
        score -= 5
    elif trend == 'Strong Downtrend':
        score -= 15

    # Volume
    if volume_signal == 'Volume Breakout':
        score += 10
    elif volume_signal == 'High Volume':
        score += 5
    elif volume_signal == 'Low Volume':
        score -= 5

    # Price vs EMA20
    if price_vs_ema20 > 2:
        score += 5
    elif price_vs_ema20 < -2:
        score -= 5

    return max(0, min(100, score))

# ── Fetch Single Stock ────────────────────────────────────────────────────

def fetch_stock_data(ticker, period='3mo', interval='1d'):
    """
    Fetches OHLCV + technicals for a single stock.
    Returns dict or None if fetch fails.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)

        if hist.empty or len(hist) < 20:
            return None

        close = hist['Close']
        volume = hist['Volume']

        # EMAs
        ema9  = calculate_ema(close, 9)
        ema20 = calculate_ema(close, 20)
        ema50 = calculate_ema(close, 50)

        # RSI
        rsi = calculate_rsi(close)

        # Momentum
        momentum = calculate_momentum(close, 10)

        # Latest values
        current_price  = round(float(close.iloc[-1]), 2)
        current_volume = int(volume.iloc[-1])
        avg_volume     = int(volume.rolling(20).mean().iloc[-1])

        ema9_val  = round(float(ema9.iloc[-1]), 2)
        ema20_val = round(float(ema20.iloc[-1]), 2)
        ema50_val = round(float(ema50.iloc[-1]), 2)
        rsi_val   = round(float(rsi.iloc[-1]), 2)
        mom_val   = round(float(momentum.iloc[-1]), 2)

        # Price change
        prev_close    = round(float(close.iloc[-2]), 2)
        price_change  = round(current_price - prev_close, 2)
        price_change_pct = round((price_change / prev_close) * 100, 2)

        # Trend + Volume
        trend         = get_trend_structure(close, ema20, ema50)
        volume_signal = get_volume_signal(current_volume, avg_volume)
        price_vs_ema20 = round(((current_price - ema20_val) / ema20_val) * 100, 2)

        # 52-week high/low
        week52_high = round(float(close.rolling(252).max().iloc[-1]), 2)
        week52_low  = round(float(close.rolling(252).min().iloc[-1]), 2)
        pct_from_52h = round(((current_price - week52_high) / week52_high) * 100, 2)

        # Technical Score
        tech_score = calculate_technical_score(rsi_val, mom_val, trend, volume_signal, price_vs_ema20)

        return {
            'ticker': ticker,
            'price': current_price,
            'prev_close': prev_close,
            'change': price_change,
            'change_pct': price_change_pct,
            'volume': current_volume,
            'avg_volume': avg_volume,
            'volume_signal': volume_signal,
            'ema9': ema9_val,
            'ema20': ema20_val,
            'ema50': ema50_val,
            'rsi': rsi_val,
            'momentum': mom_val,
            'trend': trend,
            'price_vs_ema20_pct': price_vs_ema20,
            'week52_high': week52_high,
            'week52_low': week52_low,
            'pct_from_52w_high': pct_from_52h,
            'technical_score': tech_score
        }

    except Exception as e:
        print(f"   ⚠ Failed {ticker}: {e}")
        return None

# ── Fetch Index Data ──────────────────────────────────────────────────────

def fetch_index_data():
    """Fetches major Indian index data."""
    indices_data = {}
    for name, ticker in INDICES.items():
        try:
            idx = yf.Ticker(ticker)
            hist = idx.history(period='5d', interval='1d')
            if not hist.empty and len(hist) >= 2:
                current = round(float(hist['Close'].iloc[-1]), 2)
                prev    = round(float(hist['Close'].iloc[-2]), 2)
                change  = round(current - prev, 2)
                chg_pct = round((change / prev) * 100, 2)
                indices_data[name] = {
                    'value': current,
                    'change': change,
                    'change_pct': chg_pct,
                    'direction': 'up' if change >= 0 else 'down'
                }
        except Exception as e:
            print(f"   ⚠ Index {name} failed: {e}")
    return indices_data

# ── Sector Scoring ────────────────────────────────────────────────────────

def score_sector(stocks_data):
    """
    Returns sector score 0-100 based on average technical score
    + bullish/bearish ratio.
    """
    if not stocks_data:
        return 0

    scores = [s['technical_score'] for s in stocks_data if s]
    if not scores:
        return 0

    avg_score = sum(scores) / len(scores)

    # Bullish ratio (stocks with positive change)
    bullish = sum(1 for s in stocks_data if s and s['change_pct'] > 0)
    bull_ratio = bullish / len(stocks_data)

    # Volume breakout bonus
    vb_count = sum(1 for s in stocks_data if s and s['volume_signal'] in ['Volume Breakout', 'High Volume'])
    vb_bonus = min(vb_count * 3, 15)

    sector_score = (avg_score * 0.6) + (bull_ratio * 30) + vb_bonus
    return round(min(100, sector_score), 1)

# ── Main Market Engine ────────────────────────────────────────────────────

def run_market_engine():
    """
    Master function. Returns full market data dict.
    """
    now_utc = datetime.now(timezone.utc)
    print("📈 Market Engine starting...")

    # ── Fetch indices ─────────────────────────────────────────────────────
    print("   Fetching indices...")
    indices = fetch_index_data()

    # ── Market direction from NIFTY50 ────────────────────────────────────
    market_direction = 'Neutral'
    if 'NIFTY50' in indices:
        nifty_chg = indices['NIFTY50']['change_pct']
        if nifty_chg > 0.5:
            market_direction = 'Bullish'
        elif nifty_chg < -0.5:
            market_direction = 'Bearish'

    # ── Fetch all sectors ─────────────────────────────────────────────────
    sector_results = {}
    all_stocks = []

    for sector_name, tickers in SECTORS.items():
        print(f"   Fetching {sector_name}...")
        sector_stocks = []
        for ticker in tickers:
            data = fetch_stock_data(ticker)
            if data:
                data['sector'] = sector_name
                sector_stocks.append(data)
                all_stocks.append(data)

        sector_score = score_sector(sector_stocks)

        # Top 3 stocks in sector by technical score
        top_stocks = sorted(sector_stocks, key=lambda x: x['technical_score'], reverse=True)[:3]

        sector_results[sector_name] = {
            'score': sector_score,
            'stock_count': len(sector_stocks),
            'top_stocks': [s['ticker'].replace('.NS', '') for s in top_stocks],
            'avg_rsi': round(sum(s['rsi'] for s in sector_stocks) / len(sector_stocks), 1) if sector_stocks else 0,
            'bullish_count': sum(1 for s in sector_stocks if s['change_pct'] > 0),
            'bearish_count': sum(1 for s in sector_stocks if s['change_pct'] <= 0),
        }

    # ── Top stocks overall ────────────────────────────────────────────────
    top_stocks_overall = sorted(all_stocks, key=lambda x: x['technical_score'], reverse=True)[:10]

    # ── Sectors ranked ────────────────────────────────────────────────────
    sectors_ranked = sorted(
        sector_results.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )

    # ── Market breadth ────────────────────────────────────────────────────
    total_stocks   = len(all_stocks)
    advancing      = sum(1 for s in all_stocks if s['change_pct'] > 0)
    declining      = sum(1 for s in all_stocks if s['change_pct'] < 0)
    unchanged      = total_stocks - advancing - declining
    breadth_ratio  = round((advancing / total_stocks) * 100, 1) if total_stocks > 0 else 50

    # ── Volatility bias ───────────────────────────────────────────────────
    avg_abs_change = round(sum(abs(s['change_pct']) for s in all_stocks) / total_stocks, 2) if total_stocks > 0 else 0
    if avg_abs_change > 2.0:
        volatility_bias = 'High'
    elif avg_abs_change > 1.0:
        volatility_bias = 'Medium'
    else:
        volatility_bias = 'Low'

    # ── Build output ──────────────────────────────────────────────────────
    output = {
        'date': now_utc.strftime('%Y-%m-%d'),
        'generated_at': now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'market_direction': market_direction,
        'volatility_bias': volatility_bias,
        'breadth': {
            'total': total_stocks,
            'advancing': advancing,
            'declining': declining,
            'unchanged': unchanged,
            'breadth_ratio': breadth_ratio
        },
        'indices': indices,
        'sectors_ranked': [
            {'name': name, **data}
            for name, data in sectors_ranked
        ],
        'top_stocks': top_stocks_overall,
        'all_stocks': all_stocks
    }

    return output

# ── Run & Save ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    result = run_market_engine()

    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_data.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n✅ Market Engine complete → {output_path}")
    print(f"   Market Direction : {result['market_direction']}")
    print(f"   Volatility Bias  : {result['volatility_bias']}")
    print(f"   Advancing/Declining: {result['breadth']['advancing']}/{result['breadth']['declining']}")
    print(f"\n   Top Sectors:")
    for s in result['sectors_ranked'][:5]:
        print(f"   {s['name']:15} Score: {s['score']}")
    print(f"\n   Top Stocks:")
    for s in result['top_stocks'][:5]:
        print(f"   {s['ticker']:20} Score: {s['technical_score']}  RSI: {s['rsi']}  {s['trend']}")
