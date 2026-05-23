"""
COSMO - Anomaly Detection Engine
Detects unusual sky+market conditions.
Flags rare planetary events, extreme scores, market structure anomalies.
"""

import json
import os
import math
from datetime import datetime, timezone

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
HISTORY_PATH  = os.path.join(DATA_DIR, 'history.json')
LATEST_PATH   = os.path.join(DATA_DIR, 'latest.json')
ANOMALY_OUT   = os.path.join(DATA_DIR, 'anomalies.json')

# ── Rare Planetary Events ─────────────────────────────────────────────────

RARE_PLANET_COMBOS = [
    {
        'id': 'MARS_SATURN_SAME_SIGN',
        'label': 'Mars + Saturn in same sign',
        'description': 'Tension and restriction. Markets under pressure.',
        'severity': 'HIGH',
        'check': lambda p: p.get('Mars', {}).get('rashi') == p.get('Saturn', {}).get('rashi')
    },
    {
        'id': 'JUPITER_SATURN_SAME_SIGN',
        'label': 'Jupiter + Saturn in same sign',
        'description': 'Major economic cycle shift. Watch for macro moves.',
        'severity': 'HIGH',
        'check': lambda p: p.get('Jupiter', {}).get('rashi') == p.get('Saturn', {}).get('rashi')
    },
    {
        'id': 'MOON_KETU_CONJUNCTION',
        'label': 'Moon conjunct Ketu',
        'description': 'Emotional detachment. Unpredictable market sentiment.',
        'severity': 'MEDIUM',
        'check': lambda p: _check_conjunction(p, 'Moon', 'Ketu', degrees=8)
    },
    {
        'id': 'MOON_RAHU_CONJUNCTION',
        'label': 'Moon conjunct Rahu',
        'description': 'Amplified emotions. Potential for sharp moves.',
        'severity': 'MEDIUM',
        'check': lambda p: _check_conjunction(p, 'Moon', 'Rahu', degrees=8)
    },
    {
        'id': 'SUN_SATURN_OPPOSITION',
        'label': 'Sun opposite Saturn',
        'description': 'Authority vs restriction. Leadership under scrutiny.',
        'severity': 'MEDIUM',
        'check': lambda p: _check_opposition(p, 'Sun', 'Saturn', degrees=8)
    },
    {
        'id': 'MARS_RAHU_CONJUNCTION',
        'label': 'Mars conjunct Rahu',
        'description': 'Explosive energy. High risk of sudden sharp moves.',
        'severity': 'VERY_HIGH',
        'check': lambda p: _check_conjunction(p, 'Mars', 'Rahu', degrees=8)
    },
    {
        'id': 'TRIPLE_RETROGRADE',
        'label': '3+ planets retrograde',
        'description': 'Heavy retrograde sky. Confusion and reversals likely.',
        'severity': 'HIGH',
        'check': lambda p: sum(1 for name, data in p.items()
                              if data.get('retrograde') and name not in ['Rahu', 'Ketu']) >= 3
    },
    {
        'id': 'VENUS_JUPITER_CONJUNCTION',
        'label': 'Venus conjunct Jupiter',
        'description': 'Wealth yoga. Strong bullish energy for finance and consumer.',
        'severity': 'POSITIVE',
        'check': lambda p: _check_conjunction(p, 'Venus', 'Jupiter', degrees=8)
    },
    {
        'id': 'JUPITER_EXALTED',
        'label': 'Jupiter exalted in Cancer',
        'description': 'Maximum Jupiter strength. Exceptional for banking and finance.',
        'severity': 'POSITIVE',
        'check': lambda p: p.get('Jupiter', {}).get('rashi') == 'Cancer' and not p.get('Jupiter', {}).get('retrograde')
    },
    {
        'id': 'MARS_EXALTED',
        'label': 'Mars exalted in Capricorn',
        'description': 'Maximum Mars strength. Strong momentum for metals and energy.',
        'severity': 'POSITIVE',
        'check': lambda p: p.get('Mars', {}).get('rashi') == 'Capricorn' and not p.get('Mars', {}).get('retrograde')
    },
    {
        'id': 'ALL_BENEFICS_DIRECT',
        'label': 'All benefics direct',
        'description': 'Jupiter, Venus, Mercury all direct. Clear positive energy.',
        'severity': 'POSITIVE',
        'check': lambda p: (
            not p.get('Jupiter', {}).get('retrograde') and
            not p.get('Venus', {}).get('retrograde') and
            not p.get('Mercury', {}).get('retrograde')
        )
    },
]

# ── Helper functions ──────────────────────────────────────────────────────

def _get_longitude(planets, name):
    return planets.get(name, {}).get('longitude')

def _check_conjunction(planets, p1, p2, degrees=8):
    lon1 = _get_longitude(planets, p1)
    lon2 = _get_longitude(planets, p2)
    if lon1 is None or lon2 is None:
        return False
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff
    return diff <= degrees

def _check_opposition(planets, p1, p2, degrees=8):
    lon1 = _get_longitude(planets, p1)
    lon2 = _get_longitude(planets, p2)
    if lon1 is None or lon2 is None:
        return False
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff
    return abs(diff - 180) <= degrees

# ── Statistical Anomalies ─────────────────────────────────────────────────

def detect_statistical_anomalies(latest, history_snapshots):
    """
    Detects when today's values are statistically unusual vs history.
    """
    anomalies = []

    if len(history_snapshots) < 5:
        return anomalies

    # Cosmo score anomaly
    scores = [s.get('day_cosmo_score', 50) for s in history_snapshots]
    today_score = latest.get('summary', {}).get('day_cosmo_score', 50)
    avg = sum(scores) / len(scores)
    std = math.sqrt(sum((x - avg) ** 2 for x in scores) / len(scores))

    if std > 0:
        z_score = (today_score - avg) / std
        if z_score > 1.5:
            anomalies.append({
                'id':          'UNUSUALLY_HIGH_COSMO_SCORE',
                'label':       f'Unusually high Cosmo Score ({today_score})',
                'description': f'Today\'s score is {round(z_score, 1)} standard deviations above average ({round(avg, 1)})',
                'severity':    'POSITIVE',
                'value':       today_score,
                'avg':         round(avg, 1),
                'z_score':     round(z_score, 2),
            })
        elif z_score < -1.5:
            anomalies.append({
                'id':          'UNUSUALLY_LOW_COSMO_SCORE',
                'label':       f'Unusually low Cosmo Score ({today_score})',
                'description': f'Today\'s score is {round(abs(z_score), 1)} standard deviations below average ({round(avg, 1)})',
                'severity':    'HIGH',
                'value':       today_score,
                'avg':         round(avg, 1),
                'z_score':     round(z_score, 2),
            })

    # Breadth anomaly
    breadths = [s.get('breadth_ratio', 50) for s in history_snapshots]
    today_breadth = latest.get('market', {}).get('breadth', {}).get('breadth_ratio', 50)
    avg_b = sum(breadths) / len(breadths)
    std_b = math.sqrt(sum((x - avg_b) ** 2 for x in breadths) / len(breadths))

    if std_b > 0:
        z_b = (today_breadth - avg_b) / std_b
        if z_b > 1.5:
            anomalies.append({
                'id':          'UNUSUALLY_HIGH_BREADTH',
                'label':       f'Unusually broad advance ({today_breadth}% stocks advancing)',
                'description': 'Market-wide buying. Strong bullish breadth anomaly.',
                'severity':    'POSITIVE',
                'value':       today_breadth,
            })
        elif z_b < -1.5:
            anomalies.append({
                'id':          'UNUSUALLY_LOW_BREADTH',
                'label':       f'Unusually broad decline ({today_breadth}% stocks advancing)',
                'description': 'Market-wide selling. Strong bearish breadth anomaly.',
                'severity':    'HIGH',
                'value':       today_breadth,
            })

    return anomalies

# ── Market Structure Anomalies ────────────────────────────────────────────

def detect_market_anomalies(latest):
    """
    Detects unusual market structure from today's data.
    """
    anomalies = []
    stocks = latest.get('stocks', [])

    if not stocks:
        return anomalies

    # Count volume breakouts
    vb_count = sum(1 for s in stocks if s.get('volume_signal') == 'Volume Breakout')
    if vb_count >= 5:
        anomalies.append({
            'id':          'MULTIPLE_VOLUME_BREAKOUTS',
            'label':       f'{vb_count} stocks with volume breakout today',
            'description': 'Unusual institutional activity. High conviction move possible.',
            'severity':    'HIGH',
            'value':       vb_count,
        })

    # Count strong uptrends
    uptrend_count = sum(1 for s in stocks if s.get('trend') == 'Strong Uptrend')
    total = len(stocks)
    if total > 0:
        uptrend_pct = round((uptrend_count / total) * 100, 1)
        if uptrend_pct >= 60:
            anomalies.append({
                'id':          'BROAD_UPTREND',
                'label':       f'{uptrend_pct}% of stocks in Strong Uptrend',
                'description': 'Rare broad market strength. Momentum phase confirmed.',
                'severity':    'POSITIVE',
                'value':       uptrend_pct,
            })

    # Check for extreme RSI divergence
    rsi_values = [s.get('rsi', 50) for s in stocks if s.get('rsi')]
    if rsi_values:
        overbought = sum(1 for r in rsi_values if r > 70)
        oversold   = sum(1 for r in rsi_values if r < 30)
        if overbought >= 10:
            anomalies.append({
                'id':          'BROAD_OVERBOUGHT',
                'label':       f'{overbought} stocks overbought (RSI > 70)',
                'description': 'Broad overbought condition. Correction risk elevated.',
                'severity':    'HIGH',
                'value':       overbought,
            })
        if oversold >= 10:
            anomalies.append({
                'id':          'BROAD_OVERSOLD',
                'label':       f'{oversold} stocks oversold (RSI < 30)',
                'description': 'Broad oversold condition. Potential bounce setup.',
                'severity':    'MEDIUM',
                'value':       oversold,
            })

    return anomalies

# ── Build Anomaly Summary ─────────────────────────────────────────────────

def build_anomaly_summary(all_anomalies):
    """
    Builds a prioritized summary of all anomalies.
    """
    severity_order = {'VERY_HIGH': 0, 'HIGH': 1, 'POSITIVE': 2, 'MEDIUM': 3, 'LOW': 4}

    sorted_anomalies = sorted(
        all_anomalies,
        key=lambda x: severity_order.get(x.get('severity', 'LOW'), 4)
    )

    risk_anomalies     = [a for a in sorted_anomalies if a.get('severity') in ['VERY_HIGH', 'HIGH']]
    positive_anomalies = [a for a in sorted_anomalies if a.get('severity') == 'POSITIVE']
    medium_anomalies   = [a for a in sorted_anomalies if a.get('severity') == 'MEDIUM']

    # Overall anomaly level
    if any(a['severity'] == 'VERY_HIGH' for a in all_anomalies):
        overall_level = 'CRITICAL'
    elif len(risk_anomalies) >= 3:
        overall_level = 'HIGH ALERT'
    elif len(risk_anomalies) >= 1:
        overall_level = 'ELEVATED'
    elif len(positive_anomalies) >= 2:
        overall_level = 'POSITIVE ANOMALY'
    elif all_anomalies:
        overall_level = 'MINOR'
    else:
        overall_level = 'NORMAL'

    return {
        'overall_level':     overall_level,
        'total_anomalies':   len(all_anomalies),
        'risk_count':        len(risk_anomalies),
        'positive_count':    len(positive_anomalies),
        'medium_count':      len(medium_anomalies),
        'priority_alerts':   sorted_anomalies[:3],
    }

# ── Main Anomaly Engine ───────────────────────────────────────────────────

def run_anomaly_engine():
    print("\n🚨 Anomaly Engine starting...")

    try:
        with open(LATEST_PATH, 'r') as f:
            latest = json.load(f)
    except FileNotFoundError:
        print("   ⚠ latest.json not found.")
        return

    try:
        with open(HISTORY_PATH, 'r') as f:
            history_data = json.load(f)
        history_snapshots = history_data.get('history', [])
    except FileNotFoundError:
        history_snapshots = []

    planets = latest.get('astro', {}).get('planets', {})
    all_anomalies = []

    # 1. Planetary event anomalies
    print("   Checking planetary events...")
    for event in RARE_PLANET_COMBOS:
        try:
            if event['check'](planets):
                all_anomalies.append({
                    'id':          event['id'],
                    'label':       event['label'],
                    'description': event['description'],
                    'severity':    event['severity'],
                    'type':        'planetary',
                })
        except Exception:
            pass

    # 2. Statistical anomalies vs history
    print("   Checking statistical anomalies...")
    stat_anomalies = detect_statistical_anomalies(latest, history_snapshots)
    all_anomalies.extend(stat_anomalies)

    # 3. Market structure anomalies
    print("   Checking market structure...")
    market_anomalies = detect_market_anomalies(latest)
    all_anomalies.extend(market_anomalies)

    print(f"   Total anomalies found: {len(all_anomalies)}")

    # Build summary
    summary = build_anomaly_summary(all_anomalies)
    print(f"   Overall level: {summary['overall_level']}")

    # Build output
    output = {
        'meta': {
            'date':         latest.get('meta', {}).get('date'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'summary':    summary,
        'anomalies':  all_anomalies,
    }

    with open(ANOMALY_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Anomaly Engine complete → {ANOMALY_OUT}")
    if all_anomalies:
        for a in summary['priority_alerts']:
            print(f"   [{a['severity']}] {a['label']}")
    else:
        print("   No anomalies detected — normal sky conditions.")

    return output


if __name__ == '__main__':
    run_anomaly_engine()
