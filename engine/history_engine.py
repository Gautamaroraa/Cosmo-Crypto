"""
COSMO - History Engine
Reads all daily archives, builds structured history log.
Calculates actual next-day outcomes for scored stocks.
Saves data/history.json — the memory of Cosmo.
"""

import json
import os
import glob
from datetime import datetime, timedelta, timezone

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR    = os.path.join(os.path.dirname(__file__), '..', 'data')
HISTORY_OUT = os.path.join(DATA_DIR, 'history.json')

# ── Load all daily archives ───────────────────────────────────────────────

def load_all_archives():
    """
    Reads all YYYY-MM-DD.json files from data/ folder.
    Returns list of (date_str, data) sorted by date ascending.
    """
    pattern = os.path.join(DATA_DIR, '????-??-??.json')
    files = sorted(glob.glob(pattern))
    archives = []
    for filepath in files:
        date_str = os.path.basename(filepath).replace('.json', '')
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            archives.append((date_str, data))
        except Exception as e:
            print(f"   ⚠ Could not load {filepath}: {e}")
    return archives

# ── Extract daily snapshot ────────────────────────────────────────────────

def extract_snapshot(date_str, data):
    """
    Extracts a clean, compact snapshot from a daily JSON.
    This is what gets stored in history.json.
    """
    summary  = data.get('summary', {})
    astro    = data.get('astro', {})
    market   = data.get('market', {})
    sectors  = data.get('sectors', [])
    intel    = data.get('intelligence', {})

    # Top 5 stocks flagged that day
    top_stocks = [
        {
            'ticker':      s['ticker'],
            'sector':      s.get('sector', ''),
            'cosmo_score': s.get('cosmo_score', 0),
            'direction':   s.get('direction', ''),
            'price':       s.get('price', 0),
            'rsi':         s.get('rsi', 0),
            'trend':       s.get('trend', ''),
            'rule_flags':  s.get('rule_flags', []),
        }
        for s in summary.get('top_stocks_today', [])
    ]

    # Sector ranking — just name + score + bias
    sector_log = [
        {
            'name':       s.get('name', ''),
            'cosmo_score': s.get('cosmo_score', 0),
            'astro_bias': s.get('astro_bias', ''),
        }
        for s in sectors[:5]  # Top 5 sectors
    ]

    # Astro conditions
    retrograde = astro.get('retrograde_planets', [])
    planets_simple = {
        name: {
            'rashi':      p.get('rashi', ''),
            'nakshatra':  p.get('nakshatra', ''),
            'retrograde': p.get('retrograde', False),
        }
        for name, p in astro.get('planets', {}).items()
    }

    snapshot = {
        'date':              date_str,
        'day_cosmo_score':   summary.get('day_cosmo_score', 0),
        'market_direction':  summary.get('market_direction', ''),
        'volatility_bias':   summary.get('volatility_bias', ''),
        'risk_level':        summary.get('risk_level', ''),
        'strongest_sector':  summary.get('strongest_sector', ''),
        'weakest_sector':    summary.get('weakest_sector', ''),
        'moon_phase':        astro.get('moon_phase', ''),
        'moon_phase_emoji':  astro.get('moon_phase_emoji', ''),
        'day_ruler':         astro.get('day_ruler', ''),
        'astro_score':       astro.get('astro_score', 0),
        'retrograde_planets': retrograde,
        'planets':           planets_simple,
        'conjunctions':      astro.get('conjunctions', []),
        'aspects':           astro.get('aspects', []),
        'breadth_ratio':     summary.get('breadth', {}).get('breadth_ratio', 50),
        'advancing':         summary.get('breadth', {}).get('advancing', 0),
        'declining':         summary.get('breadth', {}).get('declining', 0),
        'top_sectors':       sector_log,
        'top_stocks':        top_stocks,
        'key_signals':       summary.get('key_signals', []),
        'nifty50':           market.get('indices', {}).get('NIFTY50', {}).get('value'),
        'nifty50_change_pct': market.get('indices', {}).get('NIFTY50', {}).get('change_pct'),
        'outcomes':          {}  # Filled in by calculate_outcomes()
    }

    return snapshot

# ── Calculate Outcomes ────────────────────────────────────────────────────

def calculate_outcomes(snapshots):
    """
    For each day's top stocks, checks if they went up or down
    by comparing price to next trading day's price in archives.

    Fills snapshot['outcomes'] with actual results.
    """
    # Build price lookup: {date: {ticker: price}}
    price_lookup = {}
    for snap in snapshots:
        date = snap['date']
        price_lookup[date] = {
            s['ticker']: s['price']
            for s in snap['top_stocks']
        }

    # Build date list for finding next day
    dates = sorted([s['date'] for s in snapshots])

    for i, snap in enumerate(snapshots):
        date = snap['date']
        date_index = dates.index(date)

        # Find next available trading day in archives
        next_date = None
        for j in range(date_index + 1, min(date_index + 6, len(dates))):
            next_date = dates[j]
            break

        if not next_date:
            snap['outcomes'] = {'status': 'pending'}
            continue

        outcomes = {}
        correct = 0
        total   = 0

        for stock in snap['top_stocks']:
            ticker    = stock['ticker']
            direction = stock['direction']
            entry_price = stock['price']

            # Look for this ticker in next day's data
            next_price = price_lookup.get(next_date, {}).get(ticker)

            if next_price and entry_price and entry_price > 0:
                change_pct = round(((next_price - entry_price) / entry_price) * 100, 2)
                actual_direction = 'Bullish' if change_pct > 0 else 'Bearish'
                correct_call = (direction == actual_direction) or \
                               (direction == 'Bullish' and change_pct > 0) or \
                               (direction == 'Bearish' and change_pct < 0)

                outcomes[ticker] = {
                    'entry_price':       entry_price,
                    'next_price':        next_price,
                    'change_pct':        change_pct,
                    'predicted':         direction,
                    'actual':            actual_direction,
                    'correct':           correct_call,
                    'next_date':         next_date,
                }

                if correct_call:
                    correct += 1
                total += 1

        accuracy = round((correct / total) * 100, 1) if total > 0 else None

        snap['outcomes'] = {
            'status':          'calculated',
            'next_date':       next_date,
            'stocks':          outcomes,
            'accuracy_pct':    accuracy,
            'correct_calls':   correct,
            'total_calls':     total,
        }

    return snapshots

# ── Build Statistics ──────────────────────────────────────────────────────

def build_statistics(snapshots):
    """
    Builds aggregate statistics across all history.
    """
    if not snapshots:
        return {}

    completed = [s for s in snapshots if s.get('outcomes', {}).get('status') == 'calculated']

    # Overall accuracy
    accuracies = [s['outcomes']['accuracy_pct'] for s in completed if s['outcomes']['accuracy_pct'] is not None]
    overall_accuracy = round(sum(accuracies) / len(accuracies), 1) if accuracies else None

    # Best performing sectors
    sector_scores = {}
    for snap in snapshots:
        for sec in snap.get('top_sectors', []):
            name = sec['name']
            if name not in sector_scores:
                sector_scores[name] = []
            sector_scores[name].append(sec['cosmo_score'])

    sector_avg = {
        name: round(sum(scores) / len(scores), 1)
        for name, scores in sector_scores.items()
    }
    sector_avg_sorted = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    # Moon phase performance
    moon_accuracy = {}
    for snap in completed:
        phase = snap.get('moon_phase', '')
        acc   = snap['outcomes'].get('accuracy_pct')
        if phase and acc is not None:
            if phase not in moon_accuracy:
                moon_accuracy[phase] = []
            moon_accuracy[phase].append(acc)

    moon_avg = {
        phase: round(sum(accs) / len(accs), 1)
        for phase, accs in moon_accuracy.items()
    }

    # Day ruler performance
    ruler_accuracy = {}
    for snap in completed:
        ruler = snap.get('day_ruler', '')
        acc   = snap['outcomes'].get('accuracy_pct')
        if ruler and acc is not None:
            if ruler not in ruler_accuracy:
                ruler_accuracy[ruler] = []
            ruler_accuracy[ruler].append(acc)

    ruler_avg = {
        ruler: round(sum(accs) / len(accs), 1)
        for ruler, accs in ruler_accuracy.items()
    }

    # Cosmo score vs accuracy correlation
    score_buckets = {'high': [], 'medium': [], 'low': []}
    for snap in completed:
        score = snap.get('day_cosmo_score', 50)
        acc   = snap['outcomes'].get('accuracy_pct')
        if acc is not None:
            if score >= 65:
                score_buckets['high'].append(acc)
            elif score >= 50:
                score_buckets['medium'].append(acc)
            else:
                score_buckets['low'].append(acc)

    score_accuracy = {
        bucket: round(sum(accs) / len(accs), 1) if accs else None
        for bucket, accs in score_buckets.items()
    }

    return {
        'total_days':          len(snapshots),
        'days_with_outcomes':  len(completed),
        'overall_accuracy_pct': overall_accuracy,
        'sector_avg_scores':   dict(sector_avg_sorted),
        'moon_phase_accuracy': moon_avg,
        'day_ruler_accuracy':  ruler_avg,
        'cosmo_score_accuracy': score_accuracy,
        'generated_at':        datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

# ── Anomaly Detection ─────────────────────────────────────────────────────

def detect_anomalies(snapshots):
    """
    Flags unusual days — extreme scores, rare planet combos, high accuracy streaks.
    """
    anomalies = []

    if len(snapshots) < 3:
        return anomalies

    scores = [s['day_cosmo_score'] for s in snapshots]
    avg_score = sum(scores) / len(scores)
    std_score = (sum((x - avg_score) ** 2 for x in scores) / len(scores)) ** 0.5

    for snap in snapshots:
        flags = []

        # Unusually high/low Cosmo Score
        if snap['day_cosmo_score'] > avg_score + 1.5 * std_score:
            flags.append('UNUSUALLY_HIGH_COSMO_SCORE')
        elif snap['day_cosmo_score'] < avg_score - 1.5 * std_score:
            flags.append('UNUSUALLY_LOW_COSMO_SCORE')

        # Many retrogrades
        if len(snap.get('retrograde_planets', [])) >= 4:
            flags.append('HEAVY_RETROGRADE_SKY')

        # Perfect accuracy
        if snap.get('outcomes', {}).get('accuracy_pct') == 100:
            flags.append('PERFECT_ACCURACY_DAY')

        # Zero accuracy
        if snap.get('outcomes', {}).get('accuracy_pct') == 0:
            flags.append('ZERO_ACCURACY_DAY')

        # Full Moon or New Moon
        if snap.get('moon_phase') in ['Full Moon', 'New Moon']:
            flags.append(f"{snap['moon_phase'].upper().replace(' ','_')}_DAY")

        if flags:
            anomalies.append({
                'date':  snap['date'],
                'flags': flags,
                'cosmo_score': snap['day_cosmo_score'],
                'moon_phase':  snap['moon_phase'],
            })

    return anomalies

# ── Main History Engine ───────────────────────────────────────────────────

def run_history_engine():
    """
    Master function. Builds complete history.json from all archives.
    """
    print("\n📚 History Engine starting...")

    # Load all archives
    archives = load_all_archives()
    print(f"   Found {len(archives)} daily archives")

    if not archives:
        print("   No archives found. Run scoring engine first.")
        return

    # Extract snapshots
    snapshots = []
    for date_str, data in archives:
        snap = extract_snapshot(date_str, data)
        snapshots.append(snap)

    print(f"   Extracted {len(snapshots)} snapshots")

    # Calculate outcomes
    snapshots = calculate_outcomes(snapshots)
    completed = sum(1 for s in snapshots if s.get('outcomes', {}).get('status') == 'calculated')
    print(f"   Outcomes calculated for {completed} days")

    # Build statistics
    stats = build_statistics(snapshots)
    print(f"   Overall accuracy: {stats.get('overall_accuracy_pct', 'N/A')}%")

    # Detect anomalies
    anomalies = detect_anomalies(snapshots)
    print(f"   Anomalies detected: {len(anomalies)}")

    # Build output
    output = {
        'meta': {
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'total_days':   len(snapshots),
            'version':      '1.0'
        },
        'statistics':  stats,
        'anomalies':   anomalies,
        'history':     snapshots,  # Full history array, oldest first
    }

    # Save
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HISTORY_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ History Engine complete → {HISTORY_OUT}")
    print(f"   Total days logged : {len(snapshots)}")
    print(f"   Days with outcomes: {completed}")
    if stats.get('overall_accuracy_pct'):
        print(f"   Overall accuracy  : {stats['overall_accuracy_pct']}%")
    if stats.get('moon_phase_accuracy'):
        print(f"   Best moon phase   : {max(stats['moon_phase_accuracy'], key=stats['moon_phase_accuracy'].get)}")
    if stats.get('day_ruler_accuracy'):
        print(f"   Best day ruler    : {max(stats['day_ruler_accuracy'], key=stats['day_ruler_accuracy'].get)}")

    return output


if __name__ == '__main__':
    run_history_engine()
