"""
COSMO CRYPTO - F&O Strategy Engine
Full technical analysis: All Tier 1, 2, 3 indicators.
Generates high-"""
COSMO CRYPTO - F&O Strategy Engine
Full technical analysis: All Tier 1, 2, 3 indicators.
Generates high-confidence trade setups.
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
LATEST_PATH  = os.path.join(DATA_DIR, 'latest.json')
FNO_PATH     = os.path.join(DATA_DIR, 'fno.json')
STRATEGY_OUT = os.path.join(DATA_DIR, 'strategy.json')

MOON_BIAS = {
    'New Moon':'neutral','Waxing Crescent':'bullish','First Quarter':'bullish',
    'Waxing Gibbous':'bullish','Full Moon':'volatile','Waning Gibbous':'neutral',
    'Last Quarter':'bearish','Waning Crescent':'bearish',
}

def load_json(path):
    try:
        with open(path,'r') as f: return json.load(f)
    except: return {}

def get_coin(latest, fno, name):
    coins    = latest.get('coins', [])
    fno_coin = fno.get('coins', {}).get(f"{name}USD", {}) if fno else {}
    coin     = next((c for c in coins if c.get('name') == name), None)
    if not coin: return None
    return {**coin, 'fno': fno_coin}

def analyze_coin(coin, astro):
    moon_phase  = astro.get('moon_phase','')
    moon_bias   = MOON_BIAS.get(moon_phase,'neutral')
    retrograde  = astro.get('retrograde_planets',[])
    astro_score = astro.get('astro_score', 50)

    price    = coin.get('price', 0)
    rsi      = coin.get('rsi', 50)
    rsi_h    = coin.get('rsi_hourly', 50)
    macd_h   = coin.get('macd_histogram', 0)
    trend    = coin.get('trend','Sideways')
    momentum = coin.get('momentum', 0)
    adx      = coin.get('adx', 0)
    adx_str  = coin.get('adx_strength','Weak')
    st_sig   = coin.get('supertrend_signal','Neutral')
    ichi     = coin.get('ichimoku', {})
    cloud    = ichi.get('cloud_signal','')
    tk_cross = ichi.get('tk_cross','')
    psar_sig = coin.get('psar_signal','Neutral')
    bb_upper = coin.get('bb_upper', price)
    bb_lower = coin.get('bb_lower', price)
    bb_width = coin.get('bb_width', 5)
    stoch_k  = coin.get('stoch_rsi_k', 50)
    stoch_d  = coin.get('stoch_rsi_d', 50)
    wr       = coin.get('williams_r', -50)
    cci      = coin.get('cci', 0)
    mfi      = coin.get('mfi', 50)
    obv      = coin.get('obv', 0)
    obv_prev = coin.get('obv_prev', 0)
    vwap     = coin.get('vwap', price)
    atr      = coin.get('atr', 0)
    atr_pct  = coin.get('atr_pct', 2)
    patterns = coin.get('candlestick_patterns', [])
    vol_sig  = coin.get('volume_signal','Normal Volume')
    key_sup  = coin.get('key_support', price*0.95)
    key_res  = coin.get('key_resistance', price*1.05)
    pivots   = coin.get('pivots', {})
    dc_upper = coin.get('donchian_upper', price)
    dc_lower = coin.get('donchian_lower', price)
    roc      = coin.get('roc', 0)
    ts       = coin.get('technical_score', 50)
    score_sigs = coin.get('score_signals', [])
    funding  = coin.get('funding_rate') or coin.get('fno', {}).get('funding') or {}
    fr_rate  = funding.get('rate', 0) if funding else 0
    oi_trend = coin.get('fno', {}).get('oi_trend', 'Stable') if coin.get('fno') else 'Stable'
    sector   = coin.get('sector', '')

    setups = []

    # ── LONG MOMENTUM ────────────────────────────────────────────────────
    long_score = 0
    long_reasons = []

    if trend in ['Strong Uptrend','Uptrend']:
        long_score += 20; long_reasons.append(f"{trend}")
    elif trend == 'Recovery':
        long_score += 10; long_reasons.append("Recovery — bounce in progress")

    if 50 <= rsi <= 65:
        long_score += 12; long_reasons.append(f"RSI {rsi} momentum zone")
    elif rsi < 40:
        long_score += 5; long_reasons.append(f"RSI {rsi} potential reversal")

    if macd_h > 0:
        long_score += 10; long_reasons.append(f"MACD histogram positive")

    if st_sig == 'Bullish':
        long_score += 10; long_reasons.append("Supertrend Bullish")

    if 'Above' in cloud:
        long_score += 8; long_reasons.append("Above Ichimoku Cloud")

    if 'Bullish TK' in tk_cross:
        long_score += 6; long_reasons.append("Bullish TK Cross")

    if adx > 25:
        long_score += 8; long_reasons.append(f"ADX {adx} — {adx_str} trend")

    if psar_sig == 'Bullish':
        long_score += 6; long_reasons.append("Parabolic SAR Bullish")

    if stoch_k > stoch_d and stoch_k < 80:
        long_score += 5; long_reasons.append(f"Stoch RSI bullish K>{stoch_d:.0f}")

    if wr < -70:
        long_score += 5; long_reasons.append(f"Williams %R {wr} oversold")

    if moon_bias == 'bullish':
        long_score += 8; long_reasons.append(f"{moon_phase} — bullish moon")

    if astro_score >= 60:
        long_score += 6; long_reasons.append(f"Astro score {astro_score}/100")

    if oi_trend == 'Rising':
        long_score += 6; long_reasons.append("Open Interest rising")

    if vol_sig == 'Volume Spike':
        long_score += 10; long_reasons.append("Volume Spike — conviction")
    elif vol_sig == 'High Volume':
        long_score += 5; long_reasons.append("High volume")

    if obv > obv_prev:
        long_score += 5; long_reasons.append("OBV rising — buying pressure")

    if price > vwap:
        long_score += 4; long_reasons.append("Price above VWAP")

    if mfi > 50:
        long_score += 4; long_reasons.append(f"MFI {mfi} bullish")

    if any(p in ['Bullish Engulfing','Morning Star','Three White Soldiers','Hammer'] for p in patterns):
        p = next(p for p in patterns if p in ['Bullish Engulfing','Morning Star','Three White Soldiers','Hammer'])
        long_score += 10; long_reasons.append(f"Pattern: {p}")

    if bb_width < 5:
        long_score += 5; long_reasons.append("BB squeeze — breakout setup")

    if momentum > 5:
        long_score += 6; long_reasons.append(f"Momentum +{momentum}%")

    # Penalties
    if fr_rate > 0.08:
        long_score -= 15; long_reasons.append(f"⚠ Funding {fr_rate}% — longs overcrowded")
    if 'Mercury' in retrograde and sector in ['DeFi','L2']:
        long_score -= 8; long_reasons.append("⚠ Mercury Rx — DeFi/L2 caution")
    if moon_bias == 'volatile':
        long_score -= 10; long_reasons.append("⚠ Full Moon — volatility risk")
    if rsi > 75:
        long_score -= 10; long_reasons.append(f"⚠ RSI {rsi} extreme overbought")

    # ── SHORT MOMENTUM ───────────────────────────────────────────────────
    short_score = 0
    short_reasons = []

    if trend in ['Strong Downtrend','Downtrend']:
        short_score += 20; short_reasons.append(f"{trend}")

    if rsi > 70:
        short_score += 12; short_reasons.append(f"RSI {rsi} overbought")

    if macd_h < 0:
        short_score += 10; short_reasons.append("MACD histogram negative")

    if st_sig == 'Bearish':
        short_score += 10; short_reasons.append("Supertrend Bearish")

    if 'Below' in cloud:
        short_score += 8; short_reasons.append("Below Ichimoku Cloud")

    if 'Bearish TK' in tk_cross:
        short_score += 6; short_reasons.append("Bearish TK Cross")

    if psar_sig == 'Bearish':
        short_score += 6; short_reasons.append("Parabolic SAR Bearish")

    if stoch_k < stoch_d and stoch_k > 20:
        short_score += 5; short_reasons.append("Stoch RSI bearish cross")

    if wr > -20:
        short_score += 5; short_reasons.append(f"Williams %R {wr} overbought")

    if cci > 150:
        short_score += 5; short_reasons.append(f"CCI {cci} extreme overbought")

    if fr_rate > 0.08:
        short_score += 15; short_reasons.append(f"Funding {fr_rate}% — longs overcrowded, short opportunity")

    if moon_bias == 'bearish':
        short_score += 8; short_reasons.append(f"{moon_phase} — bearish moon")

    if momentum < -5:
        short_score += 8; short_reasons.append(f"Momentum {momentum}% negative")

    if any(p in ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star'] for p in patterns):
        p = next(p for p in patterns if p in ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star'])
        short_score += 10; short_reasons.append(f"Pattern: {p}")

    if obv < obv_prev:
        short_score += 5; short_reasons.append("OBV falling — selling pressure")

    if price < vwap:
        short_score += 4; short_reasons.append("Price below VWAP")

    # ── MEAN REVERSION SQUEEZE ────────────────────────────────────────────
    squeeze_score = 0
    squeeze_reasons = []

    if fr_rate <= -0.03:
        squeeze_score += 30; squeeze_reasons.append(f"Funding {fr_rate}% — shorts paying")
    if fr_rate <= -0.08:
        squeeze_score += 20; squeeze_reasons.append(f"Extreme negative funding — violent squeeze likely")
    if rsi <= 30:
        squeeze_score += 20; squeeze_reasons.append(f"RSI {rsi} extreme oversold")
    if wr < -85:
        squeeze_score += 10; squeeze_reasons.append(f"Williams %R {wr} extreme oversold")
    if cci < -150:
        squeeze_score += 10; squeeze_reasons.append(f"CCI {cci} extreme oversold")
    if mfi < 20:
        squeeze_score += 10; squeeze_reasons.append(f"MFI {mfi} oversold")
    if moon_bias == 'bullish':
        squeeze_score += 10; squeeze_reasons.append(f"{moon_phase} — waxing energy")
    if price < bb_lower:
        squeeze_score += 10; squeeze_reasons.append("Price below BB lower band")
    if any(p in ['Hammer','Bullish Engulfing','Morning Star'] for p in patterns):
        p = next(p for p in patterns if p in ['Hammer','Bullish Engulfing','Morning Star'])
        squeeze_score += 12; squeeze_reasons.append(f"Pattern: {p} — reversal signal")

    # ── MEAN REVERSION FLUSH ─────────────────────────────────────────────
    flush_score = 0
    flush_reasons = []

    if fr_rate >= 0.10:
        flush_score += 30; flush_reasons.append(f"Extreme funding {fr_rate}% — long liquidation imminent")
    if rsi >= 80:
        flush_score += 20; flush_reasons.append(f"RSI {rsi} extreme overbought")
    if wr > -10:
        flush_score += 10; flush_reasons.append(f"Williams %R {wr} extreme overbought")
    if cci > 200:
        flush_score += 10; flush_reasons.append(f"CCI {cci} extreme overbought")
    if moon_bias == 'volatile':
        flush_score += 20; flush_reasons.append("Full Moon — peak speculation")
    if price > bb_upper:
        flush_score += 10; flush_reasons.append("Price above BB upper band")
    if momentum > 20:
        flush_score += 10; flush_reasons.append(f"Parabolic +{momentum}% — exhaustion")
    if any(p in ['Shooting Star','Bearish Engulfing','Evening Star'] for p in patterns):
        p = next(p for p in patterns if p in ['Shooting Star','Bearish Engulfing','Evening Star'])
        flush_score += 12; flush_reasons.append(f"Pattern: {p} — reversal signal")

    # ── Build setups ──────────────────────────────────────────────────────
    sl_pct = max(atr_pct * 1.5, 2.0)  # ATR-based SL

    def build(direction, score, reasons, setup_type):
        if score < 40: return None
        if direction in ['LONG','SQUEEZE']:
            sl_price     = round(price * (1 - sl_pct/100), 6)
            target1      = round(price * (1 + sl_pct*1.5/100), 6)
            target2      = round(price * (1 + sl_pct*2.5/100), 6)
            entry_note   = f"Long {coin['name']} near ${round(price*1.002,6)}"
            nearest_sup  = max([s for s in [key_sup, pivots.get('s1',0), pivots.get('s2',0)] if s and s < price] or [price*0.95])
            sl_note      = f"SL: ${sl_price} (ATR-based -{sl_pct:.1f}%) or below ${round(nearest_sup,4)}"
            target_note  = f"T1: ${target1} (+{sl_pct*1.5:.1f}%) | T2: ${target2} (+{sl_pct*2.5:.1f}%)"
            nearest_res  = min([r for r in [key_res, pivots.get('r1',0), pivots.get('r2',0)] if r and r > price] or [price*1.05])
            target_note += f" | Key resistance: ${round(nearest_res,4)}"
        else:
            sl_price     = round(price * (1 + sl_pct/100), 6)
            target1      = round(price * (1 - sl_pct*1.5/100), 6)
            target2      = round(price * (1 - sl_pct*2.5/100), 6)
            entry_note   = f"Short {coin['name']} near ${round(price*0.998,6)}"
            nearest_res  = min([r for r in [key_res, pivots.get('r1',0), pivots.get('r2',0)] if r and r > price] or [price*1.05])
            sl_note      = f"SL: ${sl_price} (ATR-based +{sl_pct:.1f}%) or above ${round(nearest_res,4)}"
            target_note  = f"T1: ${target1} (-{sl_pct*1.5:.1f}%) | T2: ${target2} (-{sl_pct*2.5:.1f}%)"
            nearest_sup  = max([s for s in [key_sup, pivots.get('s1',0), pivots.get('s2',0)] if s and s < price] or [price*0.95])
            target_note += f" | Key support: ${round(nearest_sup,4)}"

        rr = f"R:R 1:{sl_pct*1.5/sl_pct:.1f} to 1:{sl_pct*2.5/sl_pct:.1f}"

        funding_note = ''
        if abs(fr_rate) > 0.05:
            funding_note = f"Funding {'+' if fr_rate>0 else ''}{fr_rate}%/8h (~{round(fr_rate*3*365,0):.0f}% annualized)"

        return {
            'type':          setup_type,
            'direction':     direction,
            'coin':          coin['name'],
            'symbol':        coin['symbol'],
            'sector':        sector,
            'instrument':    f"{coin['name']} Perpetual Futures",
            'entry':         entry_note,
            'stop_loss':     sl_note,
            'target':        target_note,
            'risk_reward':   rr,
            'confidence':    min(100, score),
            'reasons':       reasons[:6],
            'funding_note':  funding_note,
            'current_price': price,
            'rsi':           rsi,
            'rsi_hourly':    rsi_h,
            'trend':         trend,
            'adx':           adx,
            'adx_strength':  adx_str,
            'supertrend':    st_sig,
            'ichimoku_cloud': cloud,
            'macd_histogram': macd_h,
            'atr_pct':       atr_pct,
            'bb_width':      bb_width,
            'oi_trend':      oi_trend,
            'candlestick_patterns': patterns,
            'score_signals': score_sigs,
            'warning':       'Full Moon — reduce position size' if moon_bias=='volatile' else '',
        }

    for direction, score, reasons, stype in [
        ('LONG',    long_score,    long_reasons,    'MOMENTUM'),
        ('SHORT',   short_score,   short_reasons,   'MOMENTUM'),
        ('SQUEEZE', squeeze_score, squeeze_reasons, 'MEAN_REVERSION'),
        ('FLUSH',   flush_score,   flush_reasons,   'MEAN_REVERSION'),
    ]:
        if score < 40: continue

        # ── Hard skip rules (research-backed thresholds) ───────────────
        hard_skip   = []
        risky_flags = []

        if direction in ['LONG','SQUEEZE']:
            # Critical — these invalidate the setup completely
            if rsi > 80:
                hard_skip.append(f"RSI {rsi} > 80 — extreme overbought")
            if fr_rate > 0.15:
                hard_skip.append(f"Funding {fr_rate}%/8h > 0.15% — historical top zone (Bitget research)")
            # Blow-off top: all three conditions together
            if fr_rate > 0.05 and oi_trend == 'Rising' and adx > 40:
                hard_skip.append(f"Blow-off: funding {fr_rate}% + OI rising + ADX {adx} — BIS research: predicts 22% surge in liquidations")

            # Risky flags — setup visible but marked as risky
            if fr_rate > 0.10:
                risky_flags.append(f"Funding {fr_rate}%/8h > 0.10% — Bitget: major top precursor since 2020")
            elif fr_rate > 0.05:
                risky_flags.append(f"Funding {fr_rate}%/8h > 0.05% — caution zone")
            if adx < 20:
                risky_flags.append(f"ADX {adx} < 20 — no trend (Wilder threshold)")
            elif adx < 25:
                risky_flags.append(f"ADX {adx} < 25 — weak trend, reduce size")
            if bb_width > 40:
                risky_flags.append(f"BB Width {bb_width}% elevated — move may be extended")
            if oi_trend == 'Falling':
                risky_flags.append("OI Falling — momentum fading, avoid new longs")
            bearish_candles = ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star']
            conflicting = [p for p in patterns if p in bearish_candles]
            if conflicting:
                risky_flags.append(f"Bearish pattern: {conflicting[0]} — conflict (IEEE 2021: ~43% win rate in crypto)")
            if rsi > 72:
                risky_flags.append(f"RSI {rsi} > 72 — approaching overbought on 1h")

        if direction in ['SHORT','FLUSH']:
            if rsi < 20:
                hard_skip.append(f"RSI {rsi} < 20 — extreme oversold, short squeeze risk")
            if fr_rate < -0.15:
                hard_skip.append(f"Funding {fr_rate}%/8h extreme negative — violent squeeze risk")
            if fr_rate < -0.05:
                risky_flags.append(f"Funding {fr_rate}%/8h deeply negative — short squeeze fuel, risky to short")
            if adx < 20:
                risky_flags.append(f"ADX {adx} < 20 — weak trend")

        if hard_skip:
            s = build(direction, score, reasons, stype)
            if s:
                s['quality']      = 'SKIP'
                s['skip_reasons'] = hard_skip
                s['risky_flags']  = risky_flags
                s['confidence']   = 0
                setups.append(s)
            continue

        s = build(direction, score, reasons, stype)
        if s:
            if risky_flags:
                s['quality']     = 'RISKY'
                s['risky_flags'] = risky_flags
            else:
                s['quality']     = 'CLEAN'
                s['risky_flags'] = []
            setups.append(s)

    return setups

def build_trend_summary(latest, astro, fno):
    direction  = latest.get('market',{}).get('direction','Neutral')
    vol_bias   = latest.get('market',{}).get('volatility_bias','Low')
    moon_phase = astro.get('moon_phase','')
    day_ruler  = astro.get('day_ruler','')
    strongest  = latest.get('summary',{}).get('strongest_sector','')
    weakest    = latest.get('summary',{}).get('weakest_sector','')
    ref        = latest.get('market',{}).get('reference',{})
    btc_chg    = ref.get('BTC',{}).get('change_pct',0)
    eth_chg    = ref.get('ETH',{}).get('change_pct',0)
    breadth    = latest.get('market',{}).get('breadth',{})
    adv        = breadth.get('advancing',0)
    dec        = breadth.get('declining',0)
    funding_d  = fno.get('funding',{}) if fno else {}
    high_f     = funding_d.get('high_funding',[])
    neg_f      = funding_d.get('neg_funding',[])
    f_note = ''
    if high_f: f_note += f"High funding: {', '.join(c['name'] for c in high_f[:3])} — longs crowded. "
    if neg_f:  f_note += f"Negative funding: {', '.join(c['name'] for c in neg_f[:3])} — squeeze risk."
    lines = [
        f"Crypto market is {direction} with {vol_bias} volatility.",
        f"BTC {'+' if btc_chg>=0 else ''}{btc_chg}% | ETH {'+' if eth_chg>=0 else ''}{eth_chg}%.",
        f"{adv} coins advancing vs {dec} declining.",
        f"Strongest sector: {strongest}. Weakest: {weakest}.",
        f"Moon is {moon_phase} — {MOON_BIAS.get(moon_phase,'neutral')} energy.",
        f"Day of {day_ruler}.",
    ]
    if f_note: lines.append(f_note)
    return ' '.join(lines)

def run_strategy_engine():
    print("\n🎯 Crypto Strategy Engine (Full TA) starting...")
    latest = load_json(LATEST_PATH)
    fno    = load_json(FNO_PATH)
    if not latest:
        print("   ⚠ No latest.json"); return

    astro = latest.get('astro',{})
    coins = latest.get('coins',[])
    print(f"   Coins: {len(coins)} | Moon: {astro.get('moon_phase')}")

    # No trade check
    no_trade = []
    retro = astro.get('retrograde_planets',[])
    major_retro = [p for p in retro if p in ['Mercury','Mars','Jupiter','Venus']]
    if len(major_retro) >= 3:
        no_trade.append(f"3+ major retrogrades — very high reversal risk")
    for t in astro.get('upcoming_transitions',[]):
        if t.get('planet') in ['Jupiter','Saturn'] and t.get('within_days',99) <= 1:
            no_trade.append(f"{t['planet']} changing sign today — macro shift possible")

    # Generate setups
    all_setups = []
    for coin_raw in coins[:20]:
        name = coin_raw.get('name','')
        if not name: continue
        coin = get_coin(latest, fno, name)
        if not coin: continue
        setups = analyze_coin(coin, astro)
        all_setups.extend(setups)

    all_setups.sort(key=lambda x: x['confidence'], reverse=True)

    clean_setups = [s for s in all_setups if s.get('quality') == 'CLEAN']
    risky_setups = [s for s in all_setups if s.get('quality') == 'RISKY']
    skip_setups  = [s for s in all_setups if s.get('quality') == 'SKIP']

    trend_summary = build_trend_summary(latest, astro, fno)

    if no_trade and len(no_trade) >= 2:
        recommendation = 'NO_TRADE'
        rec_reason     = ' | '.join(no_trade)
    elif clean_setups:
        top = clean_setups[0]
        recommendation = f"{top['type']} {top['direction']} {top['coin']}"
        rec_reason     = f"Confidence {top['confidence']}/100 — {top['instrument']}"
    elif risky_setups:
        top = risky_setups[0]
        recommendation = f"RISKY: {top['type']} {top['direction']} {top['coin']}"
        rec_reason     = f"Confidence {top['confidence']}/100 — proceed with caution"
    else:
        recommendation = 'WAIT'
        rec_reason     = 'No clean setups today. Wait for better conditions.'

    output = {
        'meta': {
            'date':         latest.get('meta',{}).get('date'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'market':       'Crypto Perpetual Futures',
        },
        'trend_summary':    trend_summary,
        'recommendation':   recommendation,
        'rec_reason':       rec_reason,
        'no_trade_reasons': no_trade,
        'setups':           clean_setups[:10],
        'risky_setups':     risky_setups[:10],
        'clean_count':      len(clean_setups),
        'risky_count':      len(risky_setups),
        'astro_summary': {
            'moon_phase':         astro.get('moon_phase'),
            'moon_bias':          MOON_BIAS.get(astro.get('moon_phase',''),'neutral'),
            'day_ruler':          astro.get('day_ruler'),
            'astro_score':        astro.get('astro_score'),
            'retrograde_planets': astro.get('retrograde_planets',[]),
        }
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STRATEGY_OUT,'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Strategy Engine done — {len(all_setups)} setups")
    print(f"   Recommendation: {recommendation}")
    for s in all_setups[:5]:
        print(f"   [{s['confidence']}] {s['type']} {s['direction']} {s['coin']} — RSI:{s['rsi']} ADX:{s['adx']} {s['trend']}")
    return output

if __name__ == '__main__':
    run_strategy_engine() trade setups.
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
LATEST_PATH  = os.path.join(DATA_DIR, 'latest.json')
FNO_PATH     = os.path.join(DATA_DIR, 'fno.json')
STRATEGY_OUT = os.path.join(DATA_DIR, 'strategy.json')

MOON_BIAS = {
    'New Moon':'neutral','Waxing Crescent':'bullish','First Quarter':'bullish',
    'Waxing Gibbous':'bullish','Full Moon':'volatile','Waning Gibbous':'neutral',
    'Last Quarter':'bearish','Waning Crescent':'bearish',
}

def load_json(path):
    try:
        with open(path,'r') as f: return json.load(f)
    except: return {}

def get_coin(latest, fno, name):
    coins    = latest.get('coins', [])
    fno_coin = fno.get('coins', {}).get(f"{name}USD", {}) if fno else {}
    coin     = next((c for c in coins if c.get('name') == name), None)
    if not coin: return None
    return {**coin, 'fno': fno_coin}

def analyze_coin(coin, astro):
    moon_phase  = astro.get('moon_phase','')
    moon_bias   = MOON_BIAS.get(moon_phase,'neutral')
    retrograde  = astro.get('retrograde_planets',[])
    astro_score = astro.get('astro_score', 50)

    price    = coin.get('price', 0)
    rsi      = coin.get('rsi', 50)
    rsi_h    = coin.get('rsi_hourly', 50)
    macd_h   = coin.get('macd_histogram', 0)
    trend    = coin.get('trend','Sideways')
    momentum = coin.get('momentum', 0)
    adx      = coin.get('adx', 0)
    adx_str  = coin.get('adx_strength','Weak')
    st_sig   = coin.get('supertrend_signal','Neutral')
    ichi     = coin.get('ichimoku', {})
    cloud    = ichi.get('cloud_signal','')
    tk_cross = ichi.get('tk_cross','')
    psar_sig = coin.get('psar_signal','Neutral')
    bb_upper = coin.get('bb_upper', price)
    bb_lower = coin.get('bb_lower', price)
    bb_width = coin.get('bb_width', 5)
    stoch_k  = coin.get('stoch_rsi_k', 50)
    stoch_d  = coin.get('stoch_rsi_d', 50)
    wr       = coin.get('williams_r', -50)
    cci      = coin.get('cci', 0)
    mfi      = coin.get('mfi', 50)
    obv      = coin.get('obv', 0)
    obv_prev = coin.get('obv_prev', 0)
    vwap     = coin.get('vwap', price)
    atr      = coin.get('atr', 0)
    atr_pct  = coin.get('atr_pct', 2)
    patterns = coin.get('candlestick_patterns', [])
    vol_sig  = coin.get('volume_signal','Normal Volume')
    key_sup  = coin.get('key_support', price*0.95)
    key_res  = coin.get('key_resistance', price*1.05)
    pivots   = coin.get('pivots', {})
    dc_upper = coin.get('donchian_upper', price)
    dc_lower = coin.get('donchian_lower', price)
    roc      = coin.get('roc', 0)
    ts       = coin.get('technical_score', 50)
    score_sigs = coin.get('score_signals', [])
    funding  = coin.get('funding_rate') or coin.get('fno', {}).get('funding') or {}
    fr_rate  = funding.get('rate', 0) if funding else 0
    oi_trend = coin.get('fno', {}).get('oi_trend', 'Stable') if coin.get('fno') else 'Stable'
    sector   = coin.get('sector', '')

    setups = []

    # ── LONG MOMENTUM ────────────────────────────────────────────────────
    long_score = 0
    long_reasons = []

    if trend in ['Strong Uptrend','Uptrend']:
        long_score += 20; long_reasons.append(f"{trend}")
    elif trend == 'Recovery':
        long_score += 10; long_reasons.append("Recovery — bounce in progress")

    if 50 <= rsi <= 65:
        long_score += 12; long_reasons.append(f"RSI {rsi} momentum zone")
    elif rsi < 40:
        long_score += 5; long_reasons.append(f"RSI {rsi} potential reversal")

    if macd_h > 0:
        long_score += 10; long_reasons.append(f"MACD histogram positive")

    if st_sig == 'Bullish':
        long_score += 10; long_reasons.append("Supertrend Bullish")

    if 'Above' in cloud:
        long_score += 8; long_reasons.append("Above Ichimoku Cloud")

    if 'Bullish TK' in tk_cross:
        long_score += 6; long_reasons.append("Bullish TK Cross")

    if adx > 25:
        long_score += 8; long_reasons.append(f"ADX {adx} — {adx_str} trend")

    if psar_sig == 'Bullish':
        long_score += 6; long_reasons.append("Parabolic SAR Bullish")

    if stoch_k > stoch_d and stoch_k < 80:
        long_score += 5; long_reasons.append(f"Stoch RSI bullish K>{stoch_d:.0f}")

    if wr < -70:
        long_score += 5; long_reasons.append(f"Williams %R {wr} oversold")

    if moon_bias == 'bullish':
        long_score += 8; long_reasons.append(f"{moon_phase} — bullish moon")

    if astro_score >= 60:
        long_score += 6; long_reasons.append(f"Astro score {astro_score}/100")

    if oi_trend == 'Rising':
        long_score += 6; long_reasons.append("Open Interest rising")

    if vol_sig == 'Volume Spike':
        long_score += 10; long_reasons.append("Volume Spike — conviction")
    elif vol_sig == 'High Volume':
        long_score += 5; long_reasons.append("High volume")

    if obv > obv_prev:
        long_score += 5; long_reasons.append("OBV rising — buying pressure")

    if price > vwap:
        long_score += 4; long_reasons.append("Price above VWAP")

    if mfi > 50:
        long_score += 4; long_reasons.append(f"MFI {mfi} bullish")

    if any(p in ['Bullish Engulfing','Morning Star','Three White Soldiers','Hammer'] for p in patterns):
        p = next(p for p in patterns if p in ['Bullish Engulfing','Morning Star','Three White Soldiers','Hammer'])
        long_score += 10; long_reasons.append(f"Pattern: {p}")

    if bb_width < 5:
        long_score += 5; long_reasons.append("BB squeeze — breakout setup")

    if momentum > 5:
        long_score += 6; long_reasons.append(f"Momentum +{momentum}%")

    # Penalties
    if fr_rate > 0.08:
        long_score -= 15; long_reasons.append(f"⚠ Funding {fr_rate}% — longs overcrowded")
    if 'Mercury' in retrograde and sector in ['DeFi','L2']:
        long_score -= 8; long_reasons.append("⚠ Mercury Rx — DeFi/L2 caution")
    if moon_bias == 'volatile':
        long_score -= 10; long_reasons.append("⚠ Full Moon — volatility risk")
    if rsi > 75:
        long_score -= 10; long_reasons.append(f"⚠ RSI {rsi} extreme overbought")

    # ── SHORT MOMENTUM ───────────────────────────────────────────────────
    short_score = 0
    short_reasons = []

    if trend in ['Strong Downtrend','Downtrend']:
        short_score += 20; short_reasons.append(f"{trend}")

    if rsi > 70:
        short_score += 12; short_reasons.append(f"RSI {rsi} overbought")

    if macd_h < 0:
        short_score += 10; short_reasons.append("MACD histogram negative")

    if st_sig == 'Bearish':
        short_score += 10; short_reasons.append("Supertrend Bearish")

    if 'Below' in cloud:
        short_score += 8; short_reasons.append("Below Ichimoku Cloud")

    if 'Bearish TK' in tk_cross:
        short_score += 6; short_reasons.append("Bearish TK Cross")

    if psar_sig == 'Bearish':
        short_score += 6; short_reasons.append("Parabolic SAR Bearish")

    if stoch_k < stoch_d and stoch_k > 20:
        short_score += 5; short_reasons.append("Stoch RSI bearish cross")

    if wr > -20:
        short_score += 5; short_reasons.append(f"Williams %R {wr} overbought")

    if cci > 150:
        short_score += 5; short_reasons.append(f"CCI {cci} extreme overbought")

    if fr_rate > 0.08:
        short_score += 15; short_reasons.append(f"Funding {fr_rate}% — longs overcrowded, short opportunity")

    if moon_bias == 'bearish':
        short_score += 8; short_reasons.append(f"{moon_phase} — bearish moon")

    if momentum < -5:
        short_score += 8; short_reasons.append(f"Momentum {momentum}% negative")

    if any(p in ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star'] for p in patterns):
        p = next(p for p in patterns if p in ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star'])
        short_score += 10; short_reasons.append(f"Pattern: {p}")

    if obv < obv_prev:
        short_score += 5; short_reasons.append("OBV falling — selling pressure")

    if price < vwap:
        short_score += 4; short_reasons.append("Price below VWAP")

    # ── MEAN REVERSION SQUEEZE ────────────────────────────────────────────
    squeeze_score = 0
    squeeze_reasons = []

    if fr_rate <= -0.03:
        squeeze_score += 30; squeeze_reasons.append(f"Funding {fr_rate}% — shorts paying")
    if fr_rate <= -0.08:
        squeeze_score += 20; squeeze_reasons.append(f"Extreme negative funding — violent squeeze likely")
    if rsi <= 30:
        squeeze_score += 20; squeeze_reasons.append(f"RSI {rsi} extreme oversold")
    if wr < -85:
        squeeze_score += 10; squeeze_reasons.append(f"Williams %R {wr} extreme oversold")
    if cci < -150:
        squeeze_score += 10; squeeze_reasons.append(f"CCI {cci} extreme oversold")
    if mfi < 20:
        squeeze_score += 10; squeeze_reasons.append(f"MFI {mfi} oversold")
    if moon_bias == 'bullish':
        squeeze_score += 10; squeeze_reasons.append(f"{moon_phase} — waxing energy")
    if price < bb_lower:
        squeeze_score += 10; squeeze_reasons.append("Price below BB lower band")
    if any(p in ['Hammer','Bullish Engulfing','Morning Star'] for p in patterns):
        p = next(p for p in patterns if p in ['Hammer','Bullish Engulfing','Morning Star'])
        squeeze_score += 12; squeeze_reasons.append(f"Pattern: {p} — reversal signal")

    # ── MEAN REVERSION FLUSH ─────────────────────────────────────────────
    flush_score = 0
    flush_reasons = []

    if fr_rate >= 0.10:
        flush_score += 30; flush_reasons.append(f"Extreme funding {fr_rate}% — long liquidation imminent")
    if rsi >= 80:
        flush_score += 20; flush_reasons.append(f"RSI {rsi} extreme overbought")
    if wr > -10:
        flush_score += 10; flush_reasons.append(f"Williams %R {wr} extreme overbought")
    if cci > 200:
        flush_score += 10; flush_reasons.append(f"CCI {cci} extreme overbought")
    if moon_bias == 'volatile':
        flush_score += 20; flush_reasons.append("Full Moon — peak speculation")
    if price > bb_upper:
        flush_score += 10; flush_reasons.append("Price above BB upper band")
    if momentum > 20:
        flush_score += 10; flush_reasons.append(f"Parabolic +{momentum}% — exhaustion")
    if any(p in ['Shooting Star','Bearish Engulfing','Evening Star'] for p in patterns):
        p = next(p for p in patterns if p in ['Shooting Star','Bearish Engulfing','Evening Star'])
        flush_score += 12; flush_reasons.append(f"Pattern: {p} — reversal signal")

    # ── Build setups ──────────────────────────────────────────────────────
    sl_pct = max(atr_pct * 1.5, 2.0)  # ATR-based SL

    def build(direction, score, reasons, setup_type):
        if score < 40: return None
        if direction in ['LONG','SQUEEZE']:
            sl_price     = round(price * (1 - sl_pct/100), 6)
            target1      = round(price * (1 + sl_pct*1.5/100), 6)
            target2      = round(price * (1 + sl_pct*2.5/100), 6)
            entry_note   = f"Long {coin['name']} near ${round(price*1.002,6)}"
            nearest_sup  = max([s for s in [key_sup, pivots.get('s1',0), pivots.get('s2',0)] if s and s < price] or [price*0.95])
            sl_note      = f"SL: ${sl_price} (ATR-based -{sl_pct:.1f}%) or below ${round(nearest_sup,4)}"
            target_note  = f"T1: ${target1} (+{sl_pct*1.5:.1f}%) | T2: ${target2} (+{sl_pct*2.5:.1f}%)"
            nearest_res  = min([r for r in [key_res, pivots.get('r1',0), pivots.get('r2',0)] if r and r > price] or [price*1.05])
            target_note += f" | Key resistance: ${round(nearest_res,4)}"
        else:
            sl_price     = round(price * (1 + sl_pct/100), 6)
            target1      = round(price * (1 - sl_pct*1.5/100), 6)
            target2      = round(price * (1 - sl_pct*2.5/100), 6)
            entry_note   = f"Short {coin['name']} near ${round(price*0.998,6)}"
            nearest_res  = min([r for r in [key_res, pivots.get('r1',0), pivots.get('r2',0)] if r and r > price] or [price*1.05])
            sl_note      = f"SL: ${sl_price} (ATR-based +{sl_pct:.1f}%) or above ${round(nearest_res,4)}"
            target_note  = f"T1: ${target1} (-{sl_pct*1.5:.1f}%) | T2: ${target2} (-{sl_pct*2.5:.1f}%)"
            nearest_sup  = max([s for s in [key_sup, pivots.get('s1',0), pivots.get('s2',0)] if s and s < price] or [price*0.95])
            target_note += f" | Key support: ${round(nearest_sup,4)}"

        rr = f"R:R 1:{sl_pct*1.5/sl_pct:.1f} to 1:{sl_pct*2.5/sl_pct:.1f}"

        funding_note = ''
        if abs(fr_rate) > 0.05:
            funding_note = f"Funding {'+' if fr_rate>0 else ''}{fr_rate}%/8h (~{round(fr_rate*3*365,0):.0f}% annualized)"

        return {
            'type':          setup_type,
            'direction':     direction,
            'coin':          coin['name'],
            'symbol':        coin['symbol'],
            'sector':        sector,
            'instrument':    f"{coin['name']} Perpetual Futures",
            'entry':         entry_note,
            'stop_loss':     sl_note,
            'target':        target_note,
            'risk_reward':   rr,
            'confidence':    min(100, score),
            'reasons':       reasons[:6],
            'funding_note':  funding_note,
            'current_price': price,
            'rsi':           rsi,
            'rsi_hourly':    rsi_h,
            'trend':         trend,
            'adx':           adx,
            'adx_strength':  adx_str,
            'supertrend':    st_sig,
            'ichimoku_cloud': cloud,
            'macd_histogram': macd_h,
            'atr_pct':       atr_pct,
            'bb_width':      bb_width,
            'oi_trend':      oi_trend,
            'candlestick_patterns': patterns,
            'score_signals': score_sigs,
            'warning':       'Full Moon — reduce position size' if moon_bias=='volatile' else '',
        }

    for direction, score, reasons, stype in [
        ('LONG',    long_score,    long_reasons,    'MOMENTUM'),
        ('SHORT',   short_score,   short_reasons,   'MOMENTUM'),
        ('SQUEEZE', squeeze_score, squeeze_reasons, 'MEAN_REVERSION'),
        ('FLUSH',   flush_score,   flush_reasons,   'MEAN_REVERSION'),
    ]:
        # ── Hard skip rules ────────────────────────────────────────────
        hard_skip = []
        if direction in ['LONG','SQUEEZE']:
            if fr_rate > 1.0:   hard_skip.append(f"Funding {fr_rate}% > +1% — longs overcrowded")
            if rsi > 80:         hard_skip.append(f"RSI {rsi} > 80 — extreme overbought")
            if adx < 20:         hard_skip.append(f"ADX {adx} < 20 — no trend strength")
            if bb_width > 50:    hard_skip.append(f"BB Width {bb_width}% > 50% — move extended")
            if oi_trend == 'Falling': hard_skip.append("OI Falling — momentum fading")
            bearish_candles = ['Bearish Engulfing','Evening Star','Three Black Crows','Shooting Star']
            conflicting = [p for p in patterns if p in bearish_candles]
            if conflicting:      hard_skip.append(f"Bearish pattern: {conflicting[0]} — conflicting signal")

        if hard_skip:
            # Still add setup but mark as skipped
            s = build(direction, score, reasons, stype)
            if s:
                s['skip'] = True
                s['skip_reasons'] = hard_skip
                s['confidence'] = 0
                setups.append(s)
            continue

        s = build(direction, score, reasons, stype)
        if s: setups.append(s)

    return setups

def build_trend_summary(latest, astro, fno):
    direction  = latest.get('market',{}).get('direction','Neutral')
    vol_bias   = latest.get('market',{}).get('volatility_bias','Low')
    moon_phase = astro.get('moon_phase','')
    day_ruler  = astro.get('day_ruler','')
    strongest  = latest.get('summary',{}).get('strongest_sector','')
    weakest    = latest.get('summary',{}).get('weakest_sector','')
    ref        = latest.get('market',{}).get('reference',{})
    btc_chg    = ref.get('BTC',{}).get('change_pct',0)
    eth_chg    = ref.get('ETH',{}).get('change_pct',0)
    breadth    = latest.get('market',{}).get('breadth',{})
    adv        = breadth.get('advancing',0)
    dec        = breadth.get('declining',0)
    funding_d  = fno.get('funding',{}) if fno else {}
    high_f     = funding_d.get('high_funding',[])
    neg_f      = funding_d.get('neg_funding',[])
    f_note = ''
    if high_f: f_note += f"High funding: {', '.join(c['name'] for c in high_f[:3])} — longs crowded. "
    if neg_f:  f_note += f"Negative funding: {', '.join(c['name'] for c in neg_f[:3])} — squeeze risk."
    lines = [
        f"Crypto market is {direction} with {vol_bias} volatility.",
        f"BTC {'+' if btc_chg>=0 else ''}{btc_chg}% | ETH {'+' if eth_chg>=0 else ''}{eth_chg}%.",
        f"{adv} coins advancing vs {dec} declining.",
        f"Strongest sector: {strongest}. Weakest: {weakest}.",
        f"Moon is {moon_phase} — {MOON_BIAS.get(moon_phase,'neutral')} energy.",
        f"Day of {day_ruler}.",
    ]
    if f_note: lines.append(f_note)
    return ' '.join(lines)

def run_strategy_engine():
    print("\n🎯 Crypto Strategy Engine (Full TA) starting...")
    latest = load_json(LATEST_PATH)
    fno    = load_json(FNO_PATH)
    if not latest:
        print("   ⚠ No latest.json"); return

    astro = latest.get('astro',{})
    coins = latest.get('coins',[])
    print(f"   Coins: {len(coins)} | Moon: {astro.get('moon_phase')}")

    # No trade check
    no_trade = []
    retro = astro.get('retrograde_planets',[])
    major_retro = [p for p in retro if p in ['Mercury','Mars','Jupiter','Venus']]
    if len(major_retro) >= 3:
        no_trade.append(f"3+ major retrogrades — very high reversal risk")
    for t in astro.get('upcoming_transitions',[]):
        if t.get('planet') in ['Jupiter','Saturn'] and t.get('within_days',99) <= 1:
            no_trade.append(f"{t['planet']} changing sign today — macro shift possible")

    # Generate setups
    all_setups = []
    for coin_raw in coins[:20]:
        name = coin_raw.get('name','')
        if not name: continue
        coin = get_coin(latest, fno, name)
        if not coin: continue
        setups = analyze_coin(coin, astro)
        all_setups.extend(setups)

    all_setups.sort(key=lambda x: x['confidence'], reverse=True)

    trend_summary = build_trend_summary(latest, astro, fno)

    if no_trade and len(no_trade) >= 2:
        recommendation = 'NO_TRADE'
        rec_reason     = ' | '.join(no_trade)
    elif all_setups:
        top = all_setups[0]
        recommendation = f"{top['type']} {top['direction']} {top['coin']}"
        rec_reason     = f"Confidence {top['confidence']}/100 — {top['instrument']}"
    else:
        recommendation = 'WAIT'
        rec_reason     = 'No high-confidence setups today.'

    output = {
        'meta': {
            'date':         latest.get('meta',{}).get('date'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'market':       'Crypto Perpetual Futures',
        },
        'trend_summary':    trend_summary,
        'recommendation':   recommendation,
        'rec_reason':       rec_reason,
        'no_trade_reasons': no_trade,
        'setups':           all_setups[:15],
        'astro_summary': {
            'moon_phase':         astro.get('moon_phase'),
            'moon_bias':          MOON_BIAS.get(astro.get('moon_phase',''),'neutral'),
            'day_ruler':          astro.get('day_ruler'),
            'astro_score':        astro.get('astro_score'),
            'retrograde_planets': astro.get('retrograde_planets',[]),
        }
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STRATEGY_OUT,'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Strategy Engine done — {len(all_setups)} setups")
    print(f"   Recommendation: {recommendation}")
    for s in all_setups[:5]:
        print(f"   [{s['confidence']}] {s['type']} {s['direction']} {s['coin']} — RSI:{s['rsi']} ADX:{s['adx']} {s['trend']}")
    return output

if __name__ == '__main__':
    run_strategy_engine()
