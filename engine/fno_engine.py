"""
COSMO - F&O Engine
Fetches NSE options chain data for NIFTY and BANKNIFTY.
Calculates: OI buildup, Max Pain, PCR, expiry astro overlay.
"""

import json
import os
from datetime import datetime, timezone

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR  = os.path.join(os.path.dirname(__file__), '..', 'data')
FNO_OUT   = os.path.join(DATA_DIR, 'fno.json')

# ── NSE fetch via nsepython ───────────────────────────────────────────────

def fetch_option_chain(symbol):
    """
    Fetches option chain from NSE via nsepython.
    Returns raw option chain data or None.
    """
    try:
        from nsepython import nse_optionchain_scrapper
        data = nse_optionchain_scrapper(symbol)
        return data
    except Exception as e:
        print(f"   ⚠ nsepython fetch failed for {symbol}: {e}")
        return None

# ── Parse Option Chain ────────────────────────────────────────────────────

def parse_option_chain(raw_data, symbol):
    """
    Parses raw NSE option chain into structured format.
    Returns: spot_price, expiry_dates, strikes_data
    """
    if not raw_data:
        return None

    try:
        records   = raw_data.get('records', {})
        filtered  = raw_data.get('filtered', {})

        spot_price   = records.get('underlyingValue', 0)
        expiry_dates = records.get('expiryDates', [])
        data_records = records.get('data', [])

        if not data_records:
            return None

        # Use nearest expiry
        nearest_expiry = expiry_dates[0] if expiry_dates else None

        strikes = {}
        total_ce_oi = 0
        total_pe_oi = 0

        for record in data_records:
            if record.get('expiryDate') != nearest_expiry:
                continue

            strike = record.get('strikePrice', 0)
            ce = record.get('CE', {})
            pe = record.get('PE', {})

            ce_oi      = ce.get('openInterest', 0) or 0
            ce_oi_chg  = ce.get('changeinOpenInterest', 0) or 0
            ce_ltp     = ce.get('lastPrice', 0) or 0
            ce_iv      = ce.get('impliedVolatility', 0) or 0
            ce_vol     = ce.get('totalTradedVolume', 0) or 0

            pe_oi      = pe.get('openInterest', 0) or 0
            pe_oi_chg  = pe.get('changeinOpenInterest', 0) or 0
            pe_ltp     = pe.get('lastPrice', 0) or 0
            pe_iv      = pe.get('impliedVolatility', 0) or 0
            pe_vol     = pe.get('totalTradedVolume', 0) or 0

            total_ce_oi += ce_oi
            total_pe_oi += pe_oi

            strikes[strike] = {
                'strike':    strike,
                'ce_oi':     ce_oi,
                'ce_oi_chg': ce_oi_chg,
                'ce_ltp':    ce_ltp,
                'ce_iv':     ce_iv,
                'ce_vol':    ce_vol,
                'pe_oi':     pe_oi,
                'pe_oi_chg': pe_oi_chg,
                'pe_ltp':    pe_ltp,
                'pe_iv':     pe_iv,
                'pe_vol':    pe_vol,
            }

        return {
            'symbol':         symbol,
            'spot_price':     round(spot_price, 2),
            'nearest_expiry': nearest_expiry,
            'expiry_dates':   expiry_dates[:4],  # Next 4 expiries
            'total_ce_oi':    total_ce_oi,
            'total_pe_oi':    total_pe_oi,
            'strikes':        strikes,
        }

    except Exception as e:
        print(f"   ⚠ Parse error for {symbol}: {e}")
        return None

# ── PCR (Put-Call Ratio) ──────────────────────────────────────────────────

def calculate_pcr(parsed):
    """
    PCR = Total PE OI / Total CE OI
    PCR > 1.2 = Bullish (more puts = market expects bounce)
    PCR < 0.8 = Bearish (more calls = market expects fall)
    """
    ce_oi = parsed['total_ce_oi']
    pe_oi = parsed['total_pe_oi']

    if ce_oi == 0:
        return None

    pcr = round(pe_oi / ce_oi, 3)

    if pcr >= 1.3:
        sentiment = 'Strongly Bullish'
    elif pcr >= 1.1:
        sentiment = 'Bullish'
    elif pcr >= 0.9:
        sentiment = 'Neutral'
    elif pcr >= 0.7:
        sentiment = 'Bearish'
    else:
        sentiment = 'Strongly Bearish'

    return {
        'pcr':       pcr,
        'sentiment': sentiment,
        'ce_oi':     ce_oi,
        'pe_oi':     pe_oi,
    }

# ── Max Pain ──────────────────────────────────────────────────────────────

def calculate_max_pain(parsed):
    """
    Max Pain = strike price where option buyers lose the most money.
    = strike with minimum total payout by option writers.
    """
    strikes = parsed['strikes']
    if not strikes:
        return None

    strike_prices = sorted(strikes.keys())
    min_pain  = float('inf')
    max_pain_strike = None

    for test_strike in strike_prices:
        total_pain = 0

        for strike, data in strikes.items():
            # CE writers pay max(test_strike - strike, 0) per CE OI
            ce_pain = max(test_strike - strike, 0) * data['ce_oi']
            # PE writers pay max(strike - test_strike, 0) per PE OI
            pe_pain = max(strike - test_strike, 0) * data['pe_oi']
            total_pain += ce_pain + pe_pain

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike

    spot = parsed['spot_price']
    distance_pct = round(((max_pain_strike - spot) / spot) * 100, 2) if spot else 0

    return {
        'max_pain_strike': max_pain_strike,
        'spot_price':      spot,
        'distance_pct':    distance_pct,
        'direction':       'above' if max_pain_strike > spot else 'below',
    }

# ── OI Analysis ───────────────────────────────────────────────────────────

def analyze_oi(parsed):
    """
    Identifies:
    - Max CE OI strike (resistance)
    - Max PE OI strike (support)
    - OI buildup (strikes with highest OI change)
    - OI unwinding (strikes with negative OI change)
    """
    strikes = parsed['strikes']
    spot    = parsed['spot_price']

    if not strikes:
        return None

    # ATM range — within 5% of spot
    atm_range = spot * 0.05

    # Max CE OI = resistance
    ce_strikes = [(s, d['ce_oi']) for s, d in strikes.items() if d['ce_oi'] > 0]
    pe_strikes = [(s, d['pe_oi']) for s, d in strikes.items() if d['pe_oi'] > 0]

    max_ce = max(ce_strikes, key=lambda x: x[1]) if ce_strikes else None
    max_pe = max(pe_strikes, key=lambda x: x[1]) if pe_strikes else None

    # Top 3 CE OI strikes
    top_ce = sorted(ce_strikes, key=lambda x: x[1], reverse=True)[:3]
    top_pe = sorted(pe_strikes, key=lambda x: x[1], reverse=True)[:3]

    # OI Buildup (positive OI change)
    ce_buildup = [(s, d['ce_oi_chg']) for s, d in strikes.items() if d['ce_oi_chg'] > 0]
    pe_buildup = [(s, d['pe_oi_chg']) for s, d in strikes.items() if d['pe_oi_chg'] > 0]

    top_ce_buildup = sorted(ce_buildup, key=lambda x: x[1], reverse=True)[:3]
    top_pe_buildup = sorted(pe_buildup, key=lambda x: x[1], reverse=True)[:3]

    # OI Unwinding (negative OI change)
    ce_unwind = [(s, d['ce_oi_chg']) for s, d in strikes.items() if d['ce_oi_chg'] < 0]
    pe_unwind = [(s, d['pe_oi_chg']) for s, d in strikes.items() if d['pe_oi_chg'] < 0]

    top_ce_unwind = sorted(ce_unwind, key=lambda x: x[1])[:3]
    top_pe_unwind = sorted(pe_unwind, key=lambda x: x[1])[:3]

    # IV Skew — higher PE IV = fear, higher CE IV = greed
    atm_strikes = [s for s in strikes.keys() if abs(s - spot) <= atm_range]
    if atm_strikes:
        avg_ce_iv = sum(strikes[s]['ce_iv'] for s in atm_strikes if strikes[s]['ce_iv']) / len(atm_strikes)
        avg_pe_iv = sum(strikes[s]['pe_iv'] for s in atm_strikes if strikes[s]['pe_iv']) / len(atm_strikes)
        iv_skew = round(avg_pe_iv - avg_ce_iv, 2)
        iv_sentiment = 'Fear' if iv_skew > 3 else 'Greed' if iv_skew < -3 else 'Neutral'
    else:
        iv_skew = 0
        iv_sentiment = 'Neutral'

    return {
        'resistance_strike': max_ce[0] if max_ce else None,
        'support_strike':    max_pe[0] if max_pe else None,
        'top_ce_oi':         [{'strike': s, 'oi': o} for s, o in top_ce],
        'top_pe_oi':         [{'strike': s, 'oi': o} for s, o in top_pe],
        'ce_buildup':        [{'strike': s, 'oi_chg': c} for s, c in top_ce_buildup],
        'pe_buildup':        [{'strike': s, 'oi_chg': c} for s, c in top_pe_buildup],
        'ce_unwinding':      [{'strike': s, 'oi_chg': c} for s, c in top_ce_unwind],
        'pe_unwinding':      [{'strike': s, 'oi_chg': c} for s, c in top_pe_unwind],
        'iv_skew':           iv_skew,
        'iv_sentiment':      iv_sentiment,
    }

# ── Expiry Astro Overlay ──────────────────────────────────────────────────

def build_expiry_astro_overlay(expiry_dates, astro_data):
    """
    Maps upcoming expiry dates against planetary conditions.
    Flags expiries near Full Moon, New Moon, retrograde stations.
    """
    overlays = []

    moon_phase = astro_data.get('moon_phase', '')
    retrograde = astro_data.get('retrograde_planets', [])
    upcoming   = astro_data.get('upcoming_transitions', [])

    for expiry_str in expiry_dates[:4]:
        flags = []
        notes = []

        # Parse expiry date
        try:
            expiry_dt = datetime.strptime(expiry_str, '%d-%b-%Y')
            days_to_expiry = (expiry_dt - datetime.now()).days
        except Exception:
            days_to_expiry = None

        # Flag if near moon phase transition
        if moon_phase == 'Waxing Gibbous' and days_to_expiry and days_to_expiry <= 5:
            flags.append('NEAR_FULL_MOON')
            notes.append('Expiry near Full Moon — expect volatility')

        if moon_phase in ['New Moon', 'Waning Crescent'] and days_to_expiry and days_to_expiry <= 3:
            flags.append('NEAR_NEW_MOON')
            notes.append('Expiry near New Moon — low momentum, unclear direction')

        # Flag retrograde planets
        if 'Mercury' in retrograde:
            flags.append('MERCURY_RETRO_EXPIRY')
            notes.append('Mercury retrograde — communication errors, surprises possible')

        if 'Mars' in retrograde:
            flags.append('MARS_RETRO_EXPIRY')
            notes.append('Mars retrograde — energy reversal, momentum stocks may stall')

        # Upcoming planet transitions near expiry
        for t in upcoming:
            if days_to_expiry and days_to_expiry <= t.get('within_days', 3):
                flags.append(f"{t['planet'].upper()}_TRANSITION")
                notes.append(f"{t['planet']} moving {t['from']} → {t['to']} near expiry")

        # Risk assessment
        if len(flags) >= 3:
            risk = 'Very High'
        elif len(flags) >= 2:
            risk = 'High'
        elif len(flags) >= 1:
            risk = 'Medium'
        else:
            risk = 'Low'
            notes.append('Clean expiry — no major astro conflicts')

        overlays.append({
            'expiry':          expiry_str,
            'days_to_expiry':  days_to_expiry,
            'astro_flags':     flags,
            'notes':           notes,
            'risk':            risk,
        })

    return overlays

# ── F&O Intelligence Summary ──────────────────────────────────────────────

def build_fno_intelligence(nifty_data, banknifty_data):
    """
    Produces high-level F&O intelligence narrative.
    """
    signals = []

    # NIFTY signals
    if nifty_data:
        pcr = nifty_data.get('pcr', {})
        mp  = nifty_data.get('max_pain', {})
        oi  = nifty_data.get('oi_analysis', {})

        if pcr:
            signals.append(f"NIFTY PCR: {pcr['pcr']} — {pcr['sentiment']}")

        if mp:
            direction = 'above' if mp['distance_pct'] > 0 else 'below'
            signals.append(
                f"NIFTY Max Pain: {mp['max_pain_strike']} "
                f"({abs(mp['distance_pct'])}% {direction} spot)"
            )

        if oi:
            if oi.get('resistance_strike'):
                signals.append(f"NIFTY Resistance: {oi['resistance_strike']} (max CE OI)")
            if oi.get('support_strike'):
                signals.append(f"NIFTY Support: {oi['support_strike']} (max PE OI)")
            if oi.get('iv_sentiment') != 'Neutral':
                signals.append(f"NIFTY IV Skew: {oi['iv_sentiment']} (skew: {oi['iv_skew']})")

    # BANKNIFTY signals
    if banknifty_data:
        pcr = banknifty_data.get('pcr', {})
        mp  = banknifty_data.get('max_pain', {})

        if pcr:
            signals.append(f"BANKNIFTY PCR: {pcr['pcr']} — {pcr['sentiment']}")
        if mp:
            signals.append(f"BANKNIFTY Max Pain: {mp['max_pain_strike']}")

    return signals

# ── Main F&O Engine ───────────────────────────────────────────────────────

def run_fno_engine():
    print("\n📊 F&O Engine starting...")

    # Load astro data for overlay
    try:
        with open(os.path.join(DATA_DIR, 'latest.json'), 'r') as f:
            latest = json.load(f)
        astro_data = latest.get('astro', {})
    except Exception:
        astro_data = {}

    results = {}

    # Process NIFTY and BANKNIFTY
    for symbol in ['NIFTY', 'BANKNIFTY']:
        print(f"   Fetching {symbol} option chain...")
        raw = fetch_option_chain(symbol)

        if not raw:
            print(f"   ⚠ No data for {symbol}")
            results[symbol] = {'status': 'failed'}
            continue

        parsed = parse_option_chain(raw, symbol)
        if not parsed:
            results[symbol] = {'status': 'parse_failed'}
            continue

        pcr          = calculate_pcr(parsed)
        max_pain     = calculate_max_pain(parsed)
        oi_analysis  = analyze_oi(parsed)
        expiry_astro = build_expiry_astro_overlay(
            parsed.get('expiry_dates', []), astro_data
        )

        results[symbol] = {
            'status':        'ok',
            'spot_price':    parsed['spot_price'],
            'nearest_expiry': parsed['nearest_expiry'],
            'expiry_dates':  parsed['expiry_dates'],
            'pcr':           pcr,
            'max_pain':      max_pain,
            'oi_analysis':   oi_analysis,
            'expiry_astro':  expiry_astro,
        }

        print(f"   ✅ {symbol}: Spot {parsed['spot_price']} | PCR {pcr['pcr'] if pcr else 'N/A'} | Max Pain {max_pain['max_pain_strike'] if max_pain else 'N/A'}")

    # Build intelligence signals
    intelligence = build_fno_intelligence(
        results.get('NIFTY'),
        results.get('BANKNIFTY')
    )

    output = {
        'meta': {
            'date':         datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'intelligence': intelligence,
        'NIFTY':        results.get('NIFTY', {}),
        'BANKNIFTY':    results.get('BANKNIFTY', {}),
    }

    # Save
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FNO_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ F&O Engine complete → {FNO_OUT}")
    for sig in intelligence:
        print(f"   → {sig}")

    return output


if __name__ == '__main__':
    run_fno_engine()
