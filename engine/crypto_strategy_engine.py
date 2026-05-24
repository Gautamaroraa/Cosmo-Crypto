"""
COSMO CRYPTO - F&O Strategy Engine
Generates daily trade setups for crypto perpetual futures.
Combines: Astro + Technical + Funding Rate + OI + L/S Ratio
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
LATEST_PATH  = os.path.join(DATA_DIR, 'latest.json')
FNO_PATH     = os.path.join(DATA_DIR, 'fno.json')
STRATEGY_OUT = os.path.join(DATA_DIR, 'strategy.json')

# ── Thresholds ────────────────────────────────────────────────────────────
FUNDING_HIGH       = 0.05   # Longs overcrowded — bearish signal
FUNDING_EXTREME    = 0.10   # Extreme longs — strong reversion signal
FUNDING_NEG        = -0.03  # Shorts overcrowded — bullish signal
FUNDING_NEG_EXT    = -0.08  # Extreme shorts — strong squeeze signal
RSI_OVERBOUGHT     = 70
RSI_OVERSOLD       = 30
RSI_MOMENTUM_ZONE  = (50, 65)
OI_RISING_THRESHOLD = 5.0   # OI rising >5% = strong momentum
MIN_CONFIDENCE     = 40

MOON_BIAS = {
    'New Moon':        'neutral',
    'Waxing Crescent': 'bullish',
    'First Quarter':   'bullish',
    'Waxing Gibbous':  'bullish',
    'Full Moon':       'volatile',
    'Waning Gibbous':  'neutral',
    'Last Quarter':    'bearish',
    'Waning Crescent': 'bearish',
}

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return {}

# ── Get coin data ─────────────────────────────────────────────────────────

def get_coin_data(latest_data, fno_data, coin_name):
    """Get combined technical + F&O data for a coin."""
    coins    = latest_data.get('coins', [])
    fno_coin = fno_data.get('coins', {}).get(f"{coin_name}USD", {})

    coin_tech = next((c for c in coins if c.get('name') == coin_name), None)

    if not coin_tech:
        return None

    return {
        'name':         coin_name,
        'price':        coin_tech.get('price', 0),
        'change_pct':   coin_tech.get('change_pct', 0),
        'rsi':          coin_tech.get('rsi', 50),
        'momentum':     coin_tech.get('momentum', 0),
        'trend':        coin_tech.get('trend', 'Sideways'),
        'cosmo_score':  coin_tech.get('cosmo_score', 50),
        'sector':       coin_tech.get('sector', ''),
        'volume_signal': coin_tech.get('volume_signal', 'Normal'),
        'funding_rate': fno_coin.get('funding', {}).get('rate', 0) if fno_coin else 0,
        'funding_sent': fno_coin.get('funding', {}).get('sentiment', 'Neutral') if fno_coin else 'Neutral',
        'oi_usd':       fno_coin.get('oi_usd', 0) if fno_coin else 0,
        'oi_trend':     fno_coin.get('oi_trend', 'Stable') if fno_coin else 'Stable',
    }

# ── Momentum Setup per coin ───────────────────────────────────────────────

def check_coin_momentum(coin, astro):
    """Check momentum setup for a single coin."""
    moon_phase  = astro.get('moon_phase', '')
    moon_bias   = MOON_BIAS.get(moon_phase, 'neutral')
    retrograde  = astro.get('retrograde_planets', [])
    astro_score = astro.get('astro_score', 50)

    rsi         = coin['rsi']
    trend       = coin['trend']
    funding     = coin['funding_rate']
    oi_trend    = coin['oi_trend']
    momentum    = coin['momentum']
    vol_signal  = coin['volume_signal']
    cosmo_score = coin['cosmo_score']

    # ── LONG MOMENTUM ─────────────────────────────────────────────────────
    long_score = 0
    long_reasons = []

    if trend == 'Strong Uptrend':
        long_score += 25
        long_reasons.append(f"Strong Uptrend on {coin['name']}")

    if RSI_MOMENTUM_ZONE[0] <= rsi <= RSI_MOMENTUM_ZONE[1]:
        long_score += 15
        long_reasons.append(f"RSI {rsi} in momentum zone (50-65)")

    if momentum > 5:
        long_score += 15
        long_reasons.append(f"Strong momentum +{momentum}%")

    if moon_bias == 'bullish':
        long_score += 10
        long_reasons.append(f"{moon_phase} — bullish moon phase")

    if astro_score >= 60:
        long_score += 10
        long_reasons.append(f"Astro score {astro_score}/100")

    if oi_trend == 'Rising':
        long_score += 10
        long_reasons.append("Open Interest rising — fresh longs entering")

    if vol_signal in ['Volume Spike', 'High Volume']:
        long_score += 10
        long_reasons.append(f"{vol_signal} — conviction move")

    if -0.02 <= funding <= 0.03:
        long_score += 5
        long_reasons.append(f"Funding neutral {funding}% — not overcrowded")

    # Penalties
    if funding > FUNDING_HIGH:
        long_score -= 15
        long_reasons.append(f"⚠ Funding {funding}% — longs overcrowded, risk of flush")

    mercury_retro = 'Mercury' in retrograde
    if mercury_retro and coin['sector'] in ['DeFi', 'L2']:
        long_score -= 10
        long_reasons.append("⚠ Mercury retrograde — DeFi/L2 caution")

    if moon_bias == 'volatile':
        long_score -= 10
        long_reasons.append("⚠ Full Moon — volatile conditions")

    # ── SHORT MOMENTUM ─────────────────────────────────────────────────────
    short_score = 0
    short_reasons = []

    if trend == 'Strong Downtrend':
        short_score += 25
        short_reasons.append(f"Strong Downtrend on {coin['name']}")

    if rsi >= RSI_OVERBOUGHT:
        short_score += 15
        short_reasons.append(f"RSI {rsi} — overbought")

    if momentum < -5:
        short_score += 15
        short_reasons.append(f"Negative momentum {momentum}%")

    if moon_bias == 'bearish':
        short_score += 10
        short_reasons.append(f"{moon_phase} — bearish moon phase")

    if funding > FUNDING_HIGH:
        short_score += 15
        short_reasons.append(f"Funding {funding}% — longs overcrowded, short opportunity")

    if oi_trend == 'Falling':
        short_score += 10
        short_reasons.append("OI falling — longs exiting")

    return long_score, long_reasons, short_score, short_reasons

# ── Mean Reversion per coin ───────────────────────────────────────────────

def check_coin_reversion(coin, astro):
    """Check mean reversion setup for a coin."""
    moon_phase = astro.get('moon_phase', '')
    moon_bias  = MOON_BIAS.get(moon_phase, 'neutral')
    rsi        = coin['rsi']
    funding    = coin['funding_rate']
    trend      = coin['trend']
    momentum   = coin['momentum']

    # ── SQUEEZE SETUP (Short squeeze) ─────────────────────────────────────
    squeeze_score = 0
    squeeze_reasons = []

    if funding <= FUNDING_NEG:
        squeeze_score += 30
        squeeze_reasons.append(f"Funding {funding}% — shorts paying, squeeze risk")

    if funding <= FUNDING_NEG_EXT:
        squeeze_score += 20
        squeeze_reasons.append(f"Extreme negative funding {funding}% — violent squeeze likely")

    if rsi <= RSI_OVERSOLD:
        squeeze_score += 20
        squeeze_reasons.append(f"RSI {rsi} — oversold, reversal setup")

    if moon_bias == 'bullish':
        squeeze_score += 15
        squeeze_reasons.append(f"{moon_phase} — waxing energy supports bounce")

    if trend in ['Pullback', 'Recovery'] and momentum > 0:
        squeeze_score += 15
        squeeze_reasons.append("Pullback in uptrend — buy the dip")

    # ── FLUSH SETUP (Long liquidation) ────────────────────────────────────
    flush_score = 0
    flush_reasons = []

    if funding >= FUNDING_EXTREME:
        flush_score += 30
        flush_reasons.append(f"Extreme funding {funding}% — long liquidation imminent")

    if rsi >= RSI_OVERBOUGHT:
        flush_score += 20
        flush_reasons.append(f"RSI {rsi} — overbought extreme")

    if moon_bias == 'volatile':
        flush_score += 20
        flush_reasons.append("Full Moon — peak speculative energy, reversal likely")

    if trend == 'Strong Uptrend' and momentum > 15:
        flush_score += 15
        flush_reasons.append(f"Parabolic +{momentum}% — exhaustion likely")

    return squeeze_score, squeeze_reasons, flush_score, flush_reasons

# ── Build Setup ───────────────────────────────────────────────────────────

def build_setup(coin, setup_type, direction, score, reasons, astro):
    price = coin['price']

    # Entry, SL, Target based on direction
    if direction in ['LONG', 'SQUEEZE']:
        entry  = f"Long {coin['name']} perpetual near ${round(price * 1.002, 4)}"
        sl     = f"SL: ${round(price * 0.975, 4)} (-2.5%)"
        target = f"Target: ${round(price * 1.05, 4)} (+5%) or ${round(price * 1.08, 4)} (+8%)"
        rr     = "R:R 1:2"
    else:
        entry  = f"Short {coin['name']} perpetual near ${round(price * 0.998, 4)}"
        sl     = f"SL: ${round(price * 1.025, 4)} (+2.5%)"
        target = f"Target: ${round(price * 0.95, 4)} (-5%) or ${round(price * 0.92, 4)} (-8%)"
        rr     = "R:R 1:2"

    funding = coin['funding_rate']
    funding_note = ''
    if abs(funding) > 0.05:
        funding_note = f"Funding {'+' if funding > 0 else ''}{funding}%/8h (annualized ~{round(funding*3*365,0)}%) — monitor closely"

    return {
        'type':          setup_type,
        'direction':     direction,
        'coin':          coin['name'],
        'sector':        coin['sector'],
        'instrument':    f"{coin['name']} Perpetual Futures",
        'entry':         entry,
        'stop_loss':     sl,
        'target':        target,
        'risk_reward':   rr,
        'confidence':    min(100, score),
        'reasons':       reasons[:5],
        'funding_note':  funding_note,
        'current_price': price,
        'rsi':           coin['rsi'],
        'trend':         coin['trend'],
        'oi_trend':      coin['oi_trend'],
        'warning':       'Full Moon — use smaller position size' if astro.get('moon_phase') == 'Full Moon' else '',
    }

# ── No Trade Conditions ───────────────────────────────────────────────────

def check_no_trade(astro):
    reasons = []
    retrograde = astro.get('retrograde_planets', [])
    moon_phase = astro.get('moon_phase', '')

    major_retro = [p for p in retrograde if p in ['Mercury','Mars','Jupiter','Venus']]
    if len(major_retro) >= 3:
        reasons.append(f"3+ major retrogrades — very high reversal risk")

    if moon_phase in ['New Moon']:
        reasons.append("New Moon — wait for direction clarity before entering")

    transitions = astro.get('upcoming_transitions', [])
    for t in transitions:
        if t.get('planet') in ['Jupiter','Saturn'] and t.get('within_days', 99) <= 1:
            reasons.append(f"{t['planet']} changing sign today — macro shift possible")

    return reasons

# ── Trend Summary ─────────────────────────────────────────────────────────

def build_trend_summary(latest_data, astro, fno_data):
    direction  = latest_data.get('market', {}).get('direction', 'Neutral')
    vol_bias   = latest_data.get('market', {}).get('volatility_bias', 'Low')
    moon_phase = astro.get('moon_phase', '')
    day_ruler  = astro.get('day_ruler', '')
    strongest  = latest_data.get('summary', {}).get('strongest_sector', '')
    weakest    = latest_data.get('summary', {}).get('weakest_sector', '')
    breadth    = latest_data.get('market', {}).get('breadth', {})
    adv        = breadth.get('advancing', 0)
    dec        = breadth.get('declining', 0)
    ref        = latest_data.get('market', {}).get('reference', {})
    btc_chg    = ref.get('BTC', {}).get('change_pct', 0)
    eth_chg    = ref.get('ETH', {}).get('change_pct', 0)

    # Funding overview
    funding_data  = fno_data.get('funding', {}) if fno_data else {}
    high_f = funding_data.get('high_funding', [])
    neg_f  = funding_data.get('neg_funding', [])
    funding_note = ''
    if high_f:
        funding_note = f"High funding: {', '.join(c['name'] for c in high_f[:3])} — longs overcrowded."
    if neg_f:
        funding_note += f" Negative funding: {', '.join(c['name'] for c in neg_f[:3])} — squeeze risk."

    lines = [
        f"Crypto market is {direction} with {vol_bias} volatility.",
        f"BTC {'+' if btc_chg >= 0 else ''}{btc_chg}% | ETH {'+' if eth_chg >= 0 else ''}{eth_chg}%.",
        f"{adv} coins advancing vs {dec} declining.",
        f"Strongest sector: {strongest}. Weakest: {weakest}.",
        f"Moon is {moon_phase} — {MOON_BIAS.get(moon_phase, 'neutral')} energy.",
        f"Today is ruled by {day_ruler}.",
    ]

    if funding_note:
        lines.append(funding_note)

    return ' '.join(lines)

# ── Main Strategy Engine ──────────────────────────────────────────────────

def run_strategy_engine():
    print("\n🎯 Crypto F&O Strategy Engine starting...")

    latest_data = load_json(LATEST_PATH)
    fno_data    = load_json(FNO_PATH)

    if not latest_data:
        print("   ⚠ No latest.json data")
        return

    astro = latest_data.get('astro', {})
    coins = latest_data.get('coins', [])

    print(f"   Moon      : {astro.get('moon_phase')}")
    print(f"   Direction : {latest_data.get('market',{}).get('direction','?')}")
    print(f"   Coins     : {len(coins)}")

    # No trade check
    no_trade = check_no_trade(astro)

    # Generate setups for all coins
    all_setups = []

    for coin_data_raw in coins[:20]:  # Top 20 by Cosmo score
        coin_name = coin_data_raw.get('name', '')
        if not coin_name:
            continue

        coin = get_coin_data(latest_data, fno_data, coin_name)
        if not coin:
            continue

        # Momentum
        long_s, long_r, short_s, short_r = check_coin_momentum(coin, astro)
        if long_s >= MIN_CONFIDENCE:
            all_setups.append(build_setup(coin, 'MOMENTUM', 'LONG', long_s, long_r, astro))
        if short_s >= MIN_CONFIDENCE:
            all_setups.append(build_setup(coin, 'MOMENTUM', 'SHORT', short_s, short_r, astro))

        # Mean reversion
        squeeze_s, squeeze_r, flush_s, flush_r = check_coin_reversion(coin, astro)
        if squeeze_s >= MIN_CONFIDENCE:
            all_setups.append(build_setup(coin, 'MEAN_REVERSION', 'SQUEEZE', squeeze_s, squeeze_r, astro))
        if flush_s >= MIN_CONFIDENCE:
            all_setups.append(build_setup(coin, 'MEAN_REVERSION', 'FLUSH', flush_s, flush_r, astro))

    # Sort by confidence
    all_setups.sort(key=lambda x: x['confidence'], reverse=True)

    # Trend summary
    trend_summary = build_trend_summary(latest_data, astro, fno_data)

    # Top recommendation
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
            'date':         latest_data.get('meta', {}).get('date'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'market':       'Crypto Perpetual Futures',
        },
        'trend_summary':    trend_summary,
        'recommendation':   recommendation,
        'rec_reason':       rec_reason,
        'no_trade_reasons': no_trade,
        'setups':           all_setups[:10],  # Top 10 setups
        'astro_summary': {
            'moon_phase':         astro.get('moon_phase'),
            'moon_bias':          MOON_BIAS.get(astro.get('moon_phase',''), 'neutral'),
            'day_ruler':          astro.get('day_ruler'),
            'astro_score':        astro.get('astro_score'),
            'retrograde_planets': astro.get('retrograde_planets', []),
        }
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STRATEGY_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Crypto Strategy Engine complete → {STRATEGY_OUT}")
    print(f"   Recommendation : {recommendation}")
    print(f"   Setups found   : {len(all_setups)}")
    for s in all_setups[:5]:
        print(f"   [{s['confidence']}] {s['type']} {s['direction']} {s['coin']} — {s['trend']}")
    if no_trade:
        print(f"   ⚠ No-trade: {no_trade}")

    return output

if __name__ == '__main__':
    run_strategy_engine()
