"""
COSMO CRYPTO - Market Engine
Delta Exchange India public API.
Full technical analysis: All Tier 1, 2, 3 indicators.
"""

import requests
import json
import os
import time
import math
from datetime import datetime, timezone

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
MARKET_OUT = os.path.join(DATA_DIR, 'market_data.json')
BASE_URL   = 'https://api.india.delta.exchange'

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

ALL_COINS  = [c for coins in COINS.values() for c in coins]
SECTOR_MAP = {name: sector for sector, coins in COINS.items() for name, sym in coins}
DISPLAY_NAME = {name: name.replace('1000','') for name, sym in [c for coins in COINS.values() for c in coins]}

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

# ── Candle fetching ───────────────────────────────────────────────────────

def fetch_candles(symbol, resolution='1d', limit=100):
    end   = int(datetime.now(timezone.utc).timestamp())
    start = end - (limit * (86400 if resolution == '1d' else 3600))
    data  = safe_get(f"{BASE_URL}/v2/history/candles", {
        'resolution': resolution, 'symbol': symbol, 'start': start, 'end': end
    })
    if not data or not data.get('success'):
        return None
    candles = data.get('result', [])
    if len(candles) < 10:
        return None
    return candles

def extract_ohlcv(candles):
    opens   = [float(c['open'])   for c in candles]
    highs   = [float(c['high'])   for c in candles]
    lows    = [float(c['low'])    for c in candles]
    closes  = [float(c['close'])  for c in candles]
    volumes = [float(c['volume']) for c in candles]
    return opens, highs, lows, closes, volumes

# ══════════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS — ALL TIERS
# ══════════════════════════════════════════════════════════════════════════

# ── Tier 1 ────────────────────────────────────────────────────────────────

def calc_ema(closes, period):
    if len(closes) < period: return [closes[-1]] * len(closes)
    k = 2 / (period + 1)
    ema = [closes[0]]
    for p in closes[1:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema

def calc_sma(closes, period):
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(sum(closes[:i+1]) / (i+1))
        else:
            result.append(sum(closes[i-period+1:i+1]) / period)
    return result

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return 50
    deltas = [closes[i]-closes[i-1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    rsi_vals = []
    for i in range(period, len(deltas)):
        ag = (ag * (period-1) + gains[i]) / period
        al = (al * (period-1) + losses[i]) / period
        rs = ag / al if al != 0 else 100
        rsi_vals.append(100 - 100/(1+rs))
    return round(rsi_vals[-1], 2) if rsi_vals else 50

def calc_macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal: return 0, 0, 0
    ema_fast   = calc_ema(closes, fast)
    ema_slow   = calc_ema(closes, slow)
    macd_line  = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = calc_ema(macd_line, signal)
    histogram  = [m - s for m, s in zip(macd_line, signal_line)]
    return round(macd_line[-1], 6), round(signal_line[-1], 6), round(histogram[-1], 6)

def calc_bollinger(closes, period=20, std_dev=2):
    if len(closes) < period: return closes[-1], closes[-1], closes[-1], 0
    sma    = calc_sma(closes, period)
    mid    = sma[-1]
    recent = closes[-period:]
    std    = (sum((x - mid)**2 for x in recent) / period) ** 0.5
    upper  = mid + std_dev * std
    lower  = mid - std_dev * std
    bw     = round((upper - lower) / mid * 100, 2) if mid > 0 else 0
    return round(upper, 6), round(mid, 6), round(lower, 6), bw

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1: return 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period-1) + tr) / period
    return round(atr, 6)

def calc_vwap(highs, lows, closes, volumes):
    tp_vol = sum(((h+l+c)/3) * v for h,l,c,v in zip(highs, lows, closes, volumes))
    total_vol = sum(volumes)
    return round(tp_vol / total_vol, 6) if total_vol > 0 else closes[-1]

def calc_obv(closes, volumes):
    obv = [0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i-1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return obv[-1], obv[-5] if len(obv) >= 5 else obv[0]

def calc_support_resistance(highs, lows, closes, lookback=20):
    recent_h = highs[-lookback:]
    recent_l = lows[-lookback:]
    resistance = round(max(recent_h), 6)
    support    = round(min(recent_l), 6)
    # Find pivot highs/lows
    pivot_highs = []
    pivot_lows  = []
    for i in range(2, len(recent_h)-2):
        if recent_h[i] > recent_h[i-1] and recent_h[i] > recent_h[i+1] and \
           recent_h[i] > recent_h[i-2] and recent_h[i] > recent_h[i+2]:
            pivot_highs.append(recent_h[i])
        if recent_l[i] < recent_l[i-1] and recent_l[i] < recent_l[i+1] and \
           recent_l[i] < recent_l[i-2] and recent_l[i] < recent_l[i+2]:
            pivot_lows.append(recent_l[i])
    key_resistance = round(sorted(pivot_highs, reverse=True)[0], 6) if pivot_highs else resistance
    key_support    = round(sorted(pivot_lows)[0], 6) if pivot_lows else support
    return support, resistance, key_support, key_resistance

def detect_candlestick_patterns(opens, highs, lows, closes):
    patterns = []
    if len(closes) < 3: return patterns
    o1,h1,l1,c1 = opens[-3],highs[-3],lows[-3],closes[-3]
    o2,h2,l2,c2 = opens[-2],highs[-2],lows[-2],closes[-2]
    o3,h3,l3,c3 = opens[-1],highs[-1],lows[-1],closes[-1]
    body3 = abs(c3-o3)
    range3 = h3-l3 if h3-l3 > 0 else 0.0001
    # Doji
    if body3 / range3 < 0.1:
        patterns.append('Doji')
    # Hammer
    lower_wick = min(o3,c3) - l3
    upper_wick = h3 - max(o3,c3)
    if lower_wick > 2*body3 and upper_wick < body3 and c3 < c2:
        patterns.append('Hammer')
    # Shooting Star
    if upper_wick > 2*body3 and lower_wick < body3 and c3 > c2:
        patterns.append('Shooting Star')
    # Bullish Engulfing
    if c2 < o2 and c3 > o3 and c3 > o2 and o3 < c2:
        patterns.append('Bullish Engulfing')
    # Bearish Engulfing
    if c2 > o2 and c3 < o3 and c3 < o2 and o3 > c2:
        patterns.append('Bearish Engulfing')
    # Morning Star
    if c1 < o1 and abs(c2-o2)/(h2-l2+0.0001) < 0.3 and c3 > o3 and c3 > (o1+c1)/2:
        patterns.append('Morning Star')
    # Evening Star
    if c1 > o1 and abs(c2-o2)/(h2-l2+0.0001) < 0.3 and c3 < o3 and c3 < (o1+c1)/2:
        patterns.append('Evening Star')
    # Three White Soldiers
    if c1>o1 and c2>o2 and c3>o3 and c3>c2>c1:
        patterns.append('Three White Soldiers')
    # Three Black Crows
    if c1<o1 and c2<o2 and c3<o3 and c3<c2<c1:
        patterns.append('Three Black Crows')
    return patterns

# ── Tier 2 ────────────────────────────────────────────────────────────────

def calc_stoch_rsi(closes, rsi_period=14, stoch_period=14, smooth_k=3, smooth_d=3):
    if len(closes) < rsi_period + stoch_period + smooth_k + smooth_d:
        return 50, 50
    # Calculate RSI series
    rsi_series = []
    for i in range(rsi_period, len(closes)):
        chunk = closes[i-rsi_period:i+1]
        deltas = [chunk[j]-chunk[j-1] for j in range(1, len(chunk))]
        gains  = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        ag = sum(gains) / rsi_period
        al = sum(losses) / rsi_period
        rs = ag / al if al != 0 else 100
        rsi_series.append(100 - 100/(1+rs))
    if len(rsi_series) < stoch_period: return 50, 50
    # Stoch of RSI
    stoch_k = []
    for i in range(stoch_period-1, len(rsi_series)):
        window = rsi_series[i-stoch_period+1:i+1]
        mn, mx = min(window), max(window)
        k = (rsi_series[i]-mn)/(mx-mn)*100 if mx-mn > 0 else 50
        stoch_k.append(k)
    if len(stoch_k) < smooth_k: return 50, 50
    smooth_k_vals = calc_sma(stoch_k, smooth_k)
    if len(smooth_k_vals) < smooth_d: return round(smooth_k_vals[-1],2), 50
    smooth_d_vals = calc_sma(smooth_k_vals, smooth_d)
    return round(smooth_k_vals[-1],2), round(smooth_d_vals[-1],2)

def calc_williams_r(highs, lows, closes, period=14):
    if len(closes) < period: return -50
    h = max(highs[-period:])
    l = min(lows[-period:])
    c = closes[-1]
    wr = ((h-c)/(h-l)*-100) if h-l > 0 else -50
    return round(wr, 2)

def calc_ichimoku(highs, lows, closes):
    def donchian_mid(h, l, period):
        if len(h) < period: return (highs[-1]+lows[-1])/2
        return (max(h[-period:]) + min(l[-period:])) / 2
    tenkan  = donchian_mid(highs, lows, 9)
    kijun   = donchian_mid(highs, lows, 26)
    senkou_a = (tenkan + kijun) / 2
    senkou_b = donchian_mid(highs, lows, 52)
    chikou  = closes[-1]
    price   = closes[-1]
    cloud_top    = max(senkou_a, senkou_b)
    cloud_bottom = min(senkou_a, senkou_b)
    if price > cloud_top:
        cloud_signal = 'Above Cloud (Bullish)'
    elif price < cloud_bottom:
        cloud_signal = 'Below Cloud (Bearish)'
    else:
        cloud_signal = 'Inside Cloud (Neutral)'
    tk_cross = 'Bullish TK Cross' if tenkan > kijun else 'Bearish TK Cross' if tenkan < kijun else 'No Cross'
    return {
        'tenkan':       round(tenkan, 6),
        'kijun':        round(kijun, 6),
        'senkou_a':     round(senkou_a, 6),
        'senkou_b':     round(senkou_b, 6),
        'cloud_signal': cloud_signal,
        'tk_cross':     tk_cross,
    }

def calc_supertrend(highs, lows, closes, period=10, multiplier=3):
    if len(closes) < period + 1: return closes[-1], 'Neutral'
    atr_vals = []
    for i in range(1, len(closes)):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        atr_vals.append(tr)
    atr_series = []
    atr_avg = sum(atr_vals[:period]) / period
    atr_series.append(atr_avg)
    for tr in atr_vals[period:]:
        atr_avg = (atr_avg*(period-1) + tr) / period
        atr_series.append(atr_avg)
    if not atr_series: return closes[-1], 'Neutral'
    atr_now = atr_series[-1]
    hl2 = (highs[-1] + lows[-1]) / 2
    upper_band = hl2 + multiplier * atr_now
    lower_band = hl2 - multiplier * atr_now
    trend = 'Bullish' if closes[-1] > lower_band else 'Bearish'
    return round(lower_band if trend == 'Bullish' else upper_band, 6), trend

def calc_pivot_points(highs, lows, closes):
    h, l, c = highs[-2], lows[-2], closes[-2]
    pp = (h + l + c) / 3
    r1 = 2*pp - l
    r2 = pp + (h - l)
    r3 = h + 2*(pp - l)
    s1 = 2*pp - h
    s2 = pp - (h - l)
    s3 = l - 2*(h - pp)
    return {
        'pp': round(pp,6), 'r1': round(r1,6), 'r2': round(r2,6), 'r3': round(r3,6),
        's1': round(s1,6), 's2': round(s2,6), 's3': round(s3,6),
    }

# ── Tier 3 ────────────────────────────────────────────────────────────────

def calc_adx(highs, lows, closes, period=14):
    if len(closes) < period*2: return 0, 'Weak'
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(closes)):
        h_diff = highs[i] - highs[i-1]
        l_diff = lows[i-1] - lows[i]
        plus_dm.append(h_diff if h_diff > l_diff and h_diff > 0 else 0)
        minus_dm.append(l_diff if l_diff > h_diff and l_diff > 0 else 0)
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        trs.append(tr)
    def smooth(vals, p):
        s = sum(vals[:p])
        result = [s]
        for v in vals[p:]:
            s = s - s/p + v
            result.append(s)
        return result
    atr_s   = smooth(trs, period)
    pdm_s   = smooth(plus_dm, period)
    mdm_s   = smooth(minus_dm, period)
    pdi     = [100*p/a if a>0 else 0 for p,a in zip(pdm_s, atr_s)]
    mdi     = [100*m/a if a>0 else 0 for m,a in zip(mdm_s, atr_s)]
    dx      = [100*abs(p-m)/(p+m) if p+m>0 else 0 for p,m in zip(pdi, mdi)]
    if len(dx) < period: return 0, 'Weak'
    adx = sum(dx[-period:]) / period
    trend_str = 'Very Strong' if adx>50 else 'Strong' if adx>25 else 'Moderate' if adx>20 else 'Weak'
    return round(adx, 2), trend_str

def calc_cci(highs, lows, closes, period=20):
    if len(closes) < period: return 0
    tp = [(h+l+c)/3 for h,l,c in zip(highs, lows, closes)]
    tp_recent = tp[-period:]
    sma = sum(tp_recent) / period
    mean_dev = sum(abs(x-sma) for x in tp_recent) / period
    cci = (tp[-1]-sma) / (0.015*mean_dev) if mean_dev > 0 else 0
    return round(cci, 2)

def calc_roc(closes, period=10):
    if len(closes) <= period: return 0
    return round(((closes[-1]-closes[-period-1])/closes[-period-1])*100, 2)

def calc_mfi(highs, lows, closes, volumes, period=14):
    if len(closes) < period+1: return 50
    tp = [(h+l+c)/3 for h,l,c in zip(highs, lows, closes)]
    pos_flow, neg_flow = 0, 0
    for i in range(-period, 0):
        mf = tp[i] * volumes[i]
        if tp[i] > tp[i-1]: pos_flow += mf
        else: neg_flow += mf
    if neg_flow == 0: return 100
    mfr = pos_flow / neg_flow
    return round(100 - 100/(1+mfr), 2)

def calc_parabolic_sar(highs, lows, closes, af_start=0.02, af_max=0.2):
    if len(closes) < 5: return closes[-1], 'Neutral'
    bull = closes[1] > closes[0]
    sar  = lows[0] if bull else highs[0]
    ep   = highs[0] if bull else lows[0]
    af   = af_start
    for i in range(1, len(closes)):
        sar = sar + af*(ep-sar)
        if bull:
            if lows[i] < sar:
                bull = False; sar = ep; ep = lows[i]; af = af_start
            else:
                if highs[i] > ep: ep = highs[i]; af = min(af+af_start, af_max)
                sar = min(sar, lows[i-1], lows[i-2] if i>=2 else lows[i-1])
        else:
            if highs[i] > sar:
                bull = True; sar = ep; ep = highs[i]; af = af_start
            else:
                if lows[i] < ep: ep = lows[i]; af = min(af+af_start, af_max)
                sar = max(sar, highs[i-1], highs[i-2] if i>=2 else highs[i-1])
    trend = 'Bullish' if bull else 'Bearish'
    return round(sar, 6), trend

def calc_keltner(highs, lows, closes, period=20, multiplier=2):
    if len(closes) < period: return closes[-1], closes[-1], closes[-1]
    ema_mid = calc_ema(closes, period)[-1]
    atr = calc_atr(highs, lows, closes, period)
    return round(ema_mid + multiplier*atr, 6), round(ema_mid, 6), round(ema_mid - multiplier*atr, 6)

def calc_donchian(highs, lows, period=20):
    if len(highs) < period: return highs[-1], lows[-1]
    return round(max(highs[-period:]), 6), round(min(lows[-period:]), 6)

# ── Master Technical Score ────────────────────────────────────────────────

def calculate_master_score(ta):
    score = 50
    signals = []

    # Trend signals
    e9, e20, e50 = ta['ema9'], ta['ema20'], ta['ema50']
    price = ta['price']

    if price > e9 > e20 > e50:
        score += 20; signals.append('EMA Stack Bullish')
    elif price < e9 < e20 < e50:
        score -= 20; signals.append('EMA Stack Bearish')
    elif price > e20 > e50:
        score += 10; signals.append('Price above EMA20/50')

    # RSI
    rsi = ta['rsi']
    if 50 <= rsi <= 65:    score += 15; signals.append(f'RSI {rsi} momentum zone')
    elif rsi > 70:         score -= 10; signals.append(f'RSI {rsi} overbought')
    elif rsi < 30:         score -= 15; signals.append(f'RSI {rsi} oversold')
    elif 40 <= rsi < 50:   score += 5

    # MACD
    macd, sig, hist = ta['macd'], ta['macd_signal'], ta['macd_histogram']
    if hist > 0 and macd > sig:  score += 10; signals.append('MACD Bullish')
    elif hist < 0 and macd < sig: score -= 10; signals.append('MACD Bearish')

    # Bollinger
    bb_upper, bb_mid, bb_lower, bw = ta['bb_upper'], ta['bb_mid'], ta['bb_lower'], ta['bb_width']
    if price < bb_lower:  score += 8;  signals.append('Price below BB lower (oversold)')
    elif price > bb_upper: score -= 8; signals.append('Price above BB upper (overbought)')
    if bw < 5:             score += 5; signals.append('BB squeeze — breakout imminent')

    # ADX
    adx, adx_str = ta['adx'], ta['adx_strength']
    if adx > 25: score += 5; signals.append(f'ADX {adx} — {adx_str} trend')

    # Supertrend
    if ta['supertrend_signal'] == 'Bullish': score += 8;  signals.append('Supertrend Bullish')
    elif ta['supertrend_signal'] == 'Bearish': score -= 8; signals.append('Supertrend Bearish')

    # Ichimoku
    cloud = ta['ichimoku']['cloud_signal']
    if 'Above' in cloud: score += 8;  signals.append('Above Ichimoku Cloud')
    elif 'Below' in cloud: score -= 8; signals.append('Below Ichimoku Cloud')

    # Stoch RSI
    k, d = ta['stoch_rsi_k'], ta['stoch_rsi_d']
    if k > d and k < 80:  score += 5; signals.append('Stoch RSI bullish cross')
    elif k < d and k > 20: score -= 5; signals.append('Stoch RSI bearish cross')

    # Williams %R
    wr = ta['williams_r']
    if wr < -80: score += 5;  signals.append('Williams %R oversold')
    elif wr > -20: score -= 5; signals.append('Williams %R overbought')

    # CCI
    cci = ta['cci']
    if cci > 100:   score -= 5; signals.append(f'CCI {cci} overbought')
    elif cci < -100: score += 5; signals.append(f'CCI {cci} oversold')

    # MFI
    mfi = ta['mfi']
    if mfi > 80:   score -= 5; signals.append(f'MFI {mfi} overbought')
    elif mfi < 20:  score += 5; signals.append(f'MFI {mfi} oversold')

    # OBV trend
    obv, obv_prev = ta['obv'], ta['obv_prev']
    if obv > obv_prev: score += 5;  signals.append('OBV rising — buying pressure')
    else:               score -= 3; signals.append('OBV falling — selling pressure')

    # Parabolic SAR
    if ta['psar_signal'] == 'Bullish': score += 5;  signals.append('Parabolic SAR Bullish')
    elif ta['psar_signal'] == 'Bearish': score -= 5; signals.append('Parabolic SAR Bearish')

    # Volume
    vs = ta['volume_signal']
    if vs == 'Volume Spike': score += 10; signals.append('Volume Spike')
    elif vs == 'High Volume': score += 5; signals.append('High Volume')

    # Candlestick patterns
    patterns = ta['candlestick_patterns']
    bullish_patterns = ['Bullish Engulfing','Morning Star','Three White Soldiers','Hammer']
    bearish_patterns = ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star']
    for p in patterns:
        if p in bullish_patterns: score += 8;  signals.append(f'Pattern: {p}')
        elif p in bearish_patterns: score -= 8; signals.append(f'Pattern: {p}')

    # VWAP
    vwap = ta['vwap']
    if price > vwap: score += 5;  signals.append('Price above VWAP')
    else:             score -= 3; signals.append('Price below VWAP')

    return max(0, min(100, round(score, 1))), signals[:8]

# ── Full Technical Analysis per coin ─────────────────────────────────────

def full_ta(symbol, daily_candles, hourly_candles):
    opens_d, highs_d, lows_d, closes_d, volumes_d = extract_ohlcv(daily_candles)

    price = closes_d[-1]

    # EMA
    ema9  = round(calc_ema(closes_d, 9)[-1], 6)
    ema20 = round(calc_ema(closes_d, 20)[-1], 6)
    ema50 = round(calc_ema(closes_d, 50)[-1] if len(closes_d)>=50 else calc_ema(closes_d, len(closes_d))[-1], 6)
    ema200= round(calc_ema(closes_d, 200)[-1] if len(closes_d)>=200 else calc_ema(closes_d, len(closes_d))[-1], 6)

    # RSI (daily + hourly)
    rsi_daily  = calc_rsi(closes_d, 14)
    rsi_hourly = 50
    if hourly_candles:
        _, _, _, closes_h, _ = extract_ohlcv(hourly_candles)
        rsi_hourly = calc_rsi(closes_h, 14)

    # MACD
    macd_val, macd_sig, macd_hist = calc_macd(closes_d)

    # Bollinger Bands
    bb_upper, bb_mid, bb_lower, bb_width = calc_bollinger(closes_d)

    # ATR
    atr = calc_atr(highs_d, lows_d, closes_d)
    atr_pct = round((atr / price) * 100, 2) if price > 0 else 0

    # VWAP
    vwap = calc_vwap(highs_d, lows_d, closes_d, volumes_d)

    # OBV
    obv, obv_prev = calc_obv(closes_d, volumes_d)

    # Support & Resistance
    support, resistance, key_support, key_resistance = calc_support_resistance(highs_d, lows_d, closes_d)

    # Candlestick patterns
    patterns = detect_candlestick_patterns(opens_d, highs_d, lows_d, closes_d)

    # Volume analysis
    avg_vol = sum(volumes_d[-20:])/20 if len(volumes_d)>=20 else volumes_d[-1]
    cur_vol = volumes_d[-1]
    vol_ratio = round(cur_vol/avg_vol, 2) if avg_vol > 0 else 1
    vol_signal = 'Volume Spike' if vol_ratio>=2 else 'High Volume' if vol_ratio>=1.5 else 'Normal Volume' if vol_ratio>=0.8 else 'Low Volume'

    # Momentum
    momentum_val = round(((closes_d[-1]/closes_d[-10])-1)*100, 2) if len(closes_d)>10 else 0
    change_pct   = round(((closes_d[-1]-closes_d[-2])/closes_d[-2])*100, 2) if len(closes_d)>1 else 0

    # Tier 2
    stoch_k, stoch_d = calc_stoch_rsi(closes_d)
    williams_r = calc_williams_r(highs_d, lows_d, closes_d)
    ichimoku   = calc_ichimoku(highs_d, lows_d, closes_d)
    st_val, st_signal = calc_supertrend(highs_d, lows_d, closes_d)
    pivots     = calc_pivot_points(highs_d, lows_d, closes_d)

    # Tier 3
    adx_val, adx_str = calc_adx(highs_d, lows_d, closes_d)
    cci_val    = calc_cci(highs_d, lows_d, closes_d)
    roc_val    = calc_roc(closes_d)
    mfi_val    = calc_mfi(highs_d, lows_d, closes_d, volumes_d)
    psar_val, psar_sig = calc_parabolic_sar(highs_d, lows_d, closes_d)
    kc_upper, kc_mid, kc_lower = calc_keltner(highs_d, lows_d, closes_d)
    dc_upper, dc_lower = calc_donchian(highs_d, lows_d)

    # Trend structure
    if price > ema9 > ema20 > ema50:   trend = 'Strong Uptrend'
    elif price > ema20 > ema50:         trend = 'Uptrend'
    elif price > ema20:                  trend = 'Recovery'
    elif price < ema9 < ema20 < ema50:  trend = 'Strong Downtrend'
    elif price < ema20 < ema50:         trend = 'Downtrend'
    elif price < ema20:                  trend = 'Pullback'
    else:                                trend = 'Sideways'

    ta = {
        'price':         round(price, 6),
        'change_pct':    change_pct,
        'volume_usd':    round(cur_vol * price, 0),
        # Tier 1
        'ema9':          ema9, 'ema20': ema20, 'ema50': ema50, 'ema200': ema200,
        'rsi':           rsi_daily, 'rsi_hourly': rsi_hourly,
        'macd':          macd_val, 'macd_signal': macd_sig, 'macd_histogram': macd_hist,
        'bb_upper':      bb_upper, 'bb_mid': bb_mid, 'bb_lower': bb_lower, 'bb_width': bb_width,
        'atr':           atr, 'atr_pct': atr_pct,
        'vwap':          vwap,
        'obv':           obv, 'obv_prev': obv_prev,
        'support':       support, 'resistance': resistance,
        'key_support':   key_support, 'key_resistance': key_resistance,
        'candlestick_patterns': patterns,
        'volume_signal': vol_signal, 'vol_ratio': vol_ratio,
        'momentum':      momentum_val,
        'trend':         trend,
        # Tier 2
        'stoch_rsi_k':   stoch_k, 'stoch_rsi_d': stoch_d,
        'williams_r':    williams_r,
        'ichimoku':      ichimoku,
        'supertrend':    st_val, 'supertrend_signal': st_signal,
        'pivots':        pivots,
        # Tier 3
        'adx':           adx_val, 'adx_strength': adx_str,
        'cci':           cci_val,
        'roc':           roc_val,
        'mfi':           mfi_val,
        'psar':          psar_val, 'psar_signal': psar_sig,
        'keltner_upper': kc_upper, 'keltner_mid': kc_mid, 'keltner_lower': kc_lower,
        'donchian_upper': dc_upper, 'donchian_lower': dc_lower,
    }

    technical_score, score_signals = calculate_master_score(ta)
    ta['technical_score'] = technical_score
    ta['score_signals']   = score_signals

    return ta

# ── Sector scoring ────────────────────────────────────────────────────────

def score_sector(coins):
    if not coins: return 0
    avg  = sum(c['technical_score'] for c in coins) / len(coins)
    bull = sum(1 for c in coins if c['change_pct'] > 0) / len(coins)
    vb   = min(sum(1 for c in coins if c['volume_signal'] in ['Volume Spike','High Volume'])*3, 15)
    return round(min(100, avg*0.6 + bull*30 + vb), 1)

# ── Main ──────────────────────────────────────────────────────────────────

def fetch_all_tickers():
    data = safe_get(f"{BASE_URL}/v2/tickers")
    if not data or not data.get('success'): return {}
    return {t.get('symbol',''): t for t in data.get('result', [])}

def fetch_funding_rate(symbol):
    t = safe_get(f"{BASE_URL}/v2/tickers")
    if not t: return None
    for ticker in t.get('result', []):
        if ticker.get('symbol') == symbol:
            rate = float(ticker.get('funding_rate', 0) or 0) * 100
            if rate == 0: return None
            return {
                'rate': round(rate, 4),
                'annualized': round(rate*3*365, 1),
                'sentiment': 'Long Heavy' if rate>0.05 else 'Short Heavy' if rate<-0.05 else 'Neutral'
            }
    return None

def run_market_engine():
    print("📈 Crypto Market Engine (Full TA) starting...")
    now = datetime.now(timezone.utc)

    print("   Fetching tickers...")
    all_tickers = fetch_all_tickers()
    time.sleep(0.5)

    if not all_tickers:
        print("   ⚠ No ticker data")
        output = {
            'date': now.strftime('%Y-%m-%d'), 'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'market_direction': 'Neutral', 'volatility_bias': 'Low',
            'breadth': {'total_pairs':0,'advancing':0,'declining':0,'breadth_ratio':50,'btc_dominance_proxy':0},
            'reference': {}, 'sectors_ranked': [], 'all_coins': [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(MARKET_OUT, 'w') as f: json.dump(output, f, indent=2)
        return output

    # Breadth
    all_t = list(all_tickers.values())
    adv   = sum(1 for t in all_t if float(t.get('change', 0) or 0) > 0)
    br    = round((adv/len(all_t))*100, 1) if all_t else 50
    direction = 'Bullish' if br>=60 else 'Bearish' if br<=40 else 'Neutral'

    # Reference
    reference = {}
    for coin, sym in [('BTC','BTCUSD'),('ETH','ETHUSD')]:
        t = all_tickers.get(sym)
        if t:
            price  = float(t.get('close', 0) or 0)
            open_p = float(t.get('open', price) or price)
            chg    = round(((price-open_p)/open_p)*100, 2) if open_p > 0 else 0
            fr     = float(t.get('funding_rate', 0) or 0) * 100
            reference[coin] = {
                'price': round(price,2), 'change_pct': chg,
                'funding': {'rate': round(fr,4), 'sentiment': 'Long Heavy' if fr>0.05 else 'Neutral'} if fr != 0 else None
            }

    # Process coins
    all_coins_data = []
    sector_results = {}

    for sector, coin_pairs in COINS.items():
        print(f"   {sector}...")
        sc = []
        for name, delta_sym in coin_pairs:
            ticker = all_tickers.get(delta_sym)
            if not ticker:
                continue

            # Fetch candles
            daily_c   = fetch_candles(delta_sym, '1d', 100)
            time.sleep(0.2)
            hourly_c  = fetch_candles(delta_sym, '1h', 100)
            time.sleep(0.2)

            if not daily_c or len(daily_c) < 10:
                continue

            ta = full_ta(delta_sym, daily_c, hourly_c)

            # Add funding from ticker
            fr_rate = float(ticker.get('funding_rate', 0) or 0) * 100
            funding = None
            if fr_rate != 0:
                funding = {
                    'rate': round(fr_rate, 4),
                    'annualized': round(fr_rate*3*365, 1),
                    'sentiment': 'Long Heavy' if fr_rate>0.05 else 'Short Heavy' if fr_rate<-0.05 else 'Neutral'
                }

            coin_data = {
                'symbol':   delta_sym,
                'name':     DISPLAY_NAME.get(name, name),
                'sector':   sector,
                'funding_rate': funding,
                'open_interest': None,
                'ls_ratio': None,
                **ta
            }
            sc.append(coin_data)
            all_coins_data.append(coin_data)

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
    vol_bias = 'High' if (sum(changes)/len(changes) if changes else 0)>5 else 'Medium' if (sum(changes)/len(changes) if changes else 0)>2 else 'Low'

    output = {
        'date': now.strftime('%Y-%m-%d'), 'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'market_direction': direction, 'volatility_bias': vol_bias,
        'breadth': {'total_pairs':len(all_t),'advancing':adv,'declining':len(all_t)-adv,'breadth_ratio':br,'btc_dominance_proxy':0},
        'reference': reference,
        'sectors_ranked': [{'name':n,**d} for n,d in ranked],
        'all_coins': all_coins_data,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_OUT, 'w') as f:
        # Clean NaN/Inf
        def clean(obj):
            if isinstance(obj, float):
                return None if (obj != obj or obj == float('inf') or obj == float('-inf')) else obj
            elif isinstance(obj, dict): return {k: clean(v) for k,v in obj.items()}
            elif isinstance(obj, list): return [clean(i) for i in obj]
            return obj
        json.dump(clean(output), f, indent=2)

    print(f"\n✅ Full TA Market Engine done — {len(all_coins_data)} coins")
    print(f"   BTC: ${reference.get('BTC',{}).get('price','N/A')} | Direction: {direction}")
    return output

if __name__ == '__main__':
    run_market_engine()
