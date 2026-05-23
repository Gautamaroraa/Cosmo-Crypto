"""
COSMO - Pattern Comparison Engine
Finds historical days where sky conditions matched today.
Compares outcomes to generate pattern-based intelligence.
"""

import json
import os
from datetime import datetime, timezone

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
HISTORY_PATH = os.path.join(DATA_DIR, 'history.json')
LATEST_PATH  = os.path.join(DATA_DIR, 'latest.json')
PATTERNS_OUT = os.path.join(DATA_DIR, 'patterns.json')

# ── Load Data ─────────────────────────────────────────────────────────────

def load_history():
    with open(HISTORY_PATH, 'r') as f:
        data = json.load(f)
    return data.get('history', [])

def load_latest():
    with open(LATEST_PATH, 'r') as f:
        return json.load(f)

# ── Condition Extractors ──────────────────────────────────────────────────

def extract_conditions(snapshot):
    """
    Extracts a flat set of sky+market conditions from a snapshot.
    These are the features used for pattern matching.
    """
    planets = snapshot.get('planets', {})
    conditions = {
        # Planetary positions
        'sun_rashi':     planets.get('Sun', {}).get('rashi', ''),
        'moon_rashi':    planets.get('Moon', {}).get('rashi', ''),
        'mars_rashi':    planets.get('Mars', {}).get('rashi', ''),
        'mercury_rashi': planets.get('Mercury', {}).get('rashi', ''),
        'jupiter_rashi': planets.get('Jupiter', {}).get('rashi', ''),
        'venus_rashi':   planets.get('Venus', {}).get('rashi', ''),
        'saturn_rashi':  planets.get('Saturn', {}).get('rashi', ''),

        # Retrograde flags
        'mercury_retro': planets.get('Mercury', {}).get('retrograde', False),
        'venus_retro':   planets.get('Venus', {}).get('retrograde', False),
        'mars_retro':    planets.get('Mars', {}).get('retrograde', False),
        'jupiter_retro': planets.get('Jupiter', {}).get('retrograde', False),
        'saturn_retro':  planets.get('Saturn', {}).get('retrograde', False),

        # Moon
        'moon_phase':    snapshot.get('moon_phase', ''),
        'moon_nakshatra': planets.get('Moon', {}).get('nakshatra', ''),

        # Day ruler
        'day_ruler':     snapshot.get('day_ruler', ''),

        # Market conditions
        'market_direction': snapshot.get('market_direction', ''),
        'volatility_bias':  snapshot.get('volatility_bias', ''),
        'strongest_sector': snapshot.get('strongest_sector', ''),

        # Score buckets
        'cosmo_score_bucket': (
            'high'   if snapshot.get('day_cosmo_score', 50) >= 65 else
            'medium' if snapshot.get('day_cosmo_score', 50) >= 50 else
            'low'
        ),
        'breadth_bucket': (
            'bull'   if snapshot.get('breadth_ratio', 50) >= 60 else
            'bear'   if snapshot.get('breadth_ratio', 50) <= 40 else
            'neutral'
        ),
    }
    return conditions

# ── Similarity Score ──────────────────────────────────────────────────────

CONDITION_WEIGHTS = {
    # High weight — slow-moving, meaningful
    'mars_rashi':        10,
    'jupiter_rashi':     10,
    'saturn_rashi':      10,
    'sun_rashi':         8,

    # Medium weight
    'moon_phase':        7,
    'day_ruler':         6,
    'mercury_rashi':     5,
    'venus_rashi':       5,

    # Lower weight — fast-moving
    'moon_rashi':        4,
    'moon_nakshatra':    3,

    # Retrograde
    'mercury_retro':     6,
    'mars_retro':        5,
    'jupiter_retro':     5,
    'saturn_retro':      5,
    'venus_retro':       4,

    # Market
    'market_direction':  5,
    'volatility_bias':   4,
    'cosmo_score_bucket': 4,
    'breadth_bucket':    3,
    'strongest_sector':  3,
}

TOTAL_WEIGHT = sum(CONDITION_WEIGHTS.values())

def calculate_similarity(cond_a, cond_b):
    """
    Returns similarity score 0-100 between two condition sets.
    Weighted by importance of each condition.
    """
    matched_weight = 0
    for key, weight in CONDITION_WEIGHTS.items():
        if cond_a.get(key) == cond_b.get(key):
            matched_weight += weight
    return round((matched_weight / TOTAL_WEIGHT) * 100, 1)

# ── Find Similar Days ─────────────────────────────────────────────────────

def find_similar_days(today_conditions, history, min_similarity=40, top_n=10):
    """
    Finds historical days most similar to today's conditions.
    Returns list of (similarity, snapshot) sorted by similarity desc.
    """
    similar = []
    for snap in history:
        hist_conditions = extract_conditions(snap)
        similarity = calculate_similarity(today_conditions, hist_conditions)
        if similarity >= min_similarity:
            similar.append((similarity, snap))

    similar.sort(key=lambda x: x[0], reverse=True)
    return similar[:top_n]

# ── Pattern Analysis ──────────────────────────────────────────────────────

def analyze_patterns(similar_days):
    """
    Given similar historical days, analyzes outcomes.
    Returns pattern insights.
    """
    if not similar_days:
        return {'status': 'insufficient_data', 'message': 'Not enough historical data yet.'}

    days_with_outcomes = [
        (sim, snap) for sim, snap in similar_days
        if snap.get('outcomes', {}).get('status') == 'calculated'
    ]

    if not days_with_outcomes:
        return {
            'status': 'no_outcomes_yet',
            'similar_days_found': len(similar_days),
            'message': 'Similar days found but outcomes not yet available. Check back tomorrow.'
        }

    # Sector performance on similar days
    sector_performance = {}
    for sim, snap in days_with_outcomes:
        for sec in snap.get('top_sectors', []):
            name = sec['name']
            if name not in sector_performance:
                sector_performance[name] = []
            sector_performance[name].append(sec['cosmo_score'])

    sector_avg = {
        name: round(sum(scores) / len(scores), 1)
        for name, scores in sector_performance.items()
    }
    sector_avg_sorted = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    # Stock accuracy on similar days
    all_stock_outcomes = []
    for sim, snap in days_with_outcomes:
        outcomes = snap.get('outcomes', {}).get('stocks', {})
        for ticker, outcome in outcomes.items():
            outcome['similarity'] = sim
            outcome['date'] = snap['date']
            outcome['ticker'] = ticker
            all_stock_outcomes.append(outcome)

    correct = sum(1 for o in all_stock_outcomes if o.get('correct'))
    total   = len(all_stock_outcomes)
    accuracy = round((correct / total) * 100, 1) if total > 0 else None

    # Average next-day change
    changes = [o['change_pct'] for o in all_stock_outcomes if 'change_pct' in o]
    avg_change = round(sum(changes) / len(changes), 2) if changes else None

    # Moon phase pattern
    moon_phases = [snap.get('moon_phase', '') for _, snap in days_with_outcomes]
    moon_phase_counts = {}
    for p in moon_phases:
        moon_phase_counts[p] = moon_phase_counts.get(p, 0) + 1

    # Direction pattern
    directions = [snap.get('market_direction', '') for _, snap in days_with_outcomes]
    bull_count = directions.count('Bullish')
    bear_count = directions.count('Bearish')
    neut_count = directions.count('Neutral')

    # Best performing stocks on similar days
    stock_freq = {}
    for o in all_stock_outcomes:
        t = o['ticker']
        if t not in stock_freq:
            stock_freq[t] = {'correct': 0, 'total': 0, 'changes': []}
        stock_freq[t]['total'] += 1
        if o.get('correct'):
            stock_freq[t]['correct'] += 1
        if 'change_pct' in o:
            stock_freq[t]['changes'].append(o['change_pct'])

    stock_patterns = []
    for ticker, data in stock_freq.items():
        if data['total'] >= 2:
            acc = round((data['correct'] / data['total']) * 100, 1)
            avg_chg = round(sum(data['changes']) / len(data['changes']), 2) if data['changes'] else 0
            stock_patterns.append({
                'ticker':        ticker,
                'appearances':   data['total'],
                'accuracy_pct':  acc,
                'avg_change_pct': avg_chg,
            })

    stock_patterns.sort(key=lambda x: x['accuracy_pct'], reverse=True)

    return {
        'status':               'calculated',
        'similar_days_found':   len(similar_days),
        'days_with_outcomes':   len(days_with_outcomes),
        'overall_accuracy_pct': accuracy,
        'avg_stock_change_pct': avg_change,
        'direction_pattern': {
            'bullish': bull_count,
            'bearish': bear_count,
            'neutral': neut_count,
            'dominant': max(['Bullish', 'Bearish', 'Neutral'],
                           key=lambda x: directions.count(x)) if directions else 'Neutral'
        },
        'top_sectors_on_similar_days': [
            {'name': name, 'avg_score': score}
            for name, score in sector_avg_sorted[:5]
        ],
        'recurring_stocks': stock_patterns[:5],
        'moon_phase_pattern': moon_phase_counts,
    }

# ── Condition Difference Explainer ───────────────────────────────────────

def explain_similarity(today_cond, hist_cond, similarity):
    """
    Returns human-readable explanation of what matched and what differed.
    """
    matches = []
    diffs   = []

    key_labels = {
        'mars_rashi':    'Mars in',
        'jupiter_rashi': 'Jupiter in',
        'saturn_rashi':  'Saturn in',
        'sun_rashi':     'Sun in',
        'moon_phase':    'Moon phase',
        'day_ruler':     'Day ruler',
        'mercury_retro': 'Mercury retrograde',
        'moon_rashi':    'Moon in',
    }

    for key, label in key_labels.items():
        val_today = today_cond.get(key)
        val_hist  = hist_cond.get(key)
        if val_today == val_hist:
            matches.append(f"{label} {val_today}")
        else:
            diffs.append(f"{label}: {val_hist} → now {val_today}")

    return {
        'similarity_pct': similarity,
        'matched': matches[:5],
        'different': diffs[:3],
    }

# ── Pattern Narratives ────────────────────────────────────────────────────

def build_narratives(today_conditions, patterns, similar_days):
    """
    Builds human-readable pattern narrative strings.
    """
    narratives = []

    if patterns.get('status') != 'calculated':
        narratives.append("Building pattern memory — more data needed.")
        return narratives

    # Accuracy narrative
    acc = patterns.get('overall_accuracy_pct')
    n   = patterns.get('similar_days_found', 0)
    if acc is not None:
        narratives.append(
            f"On {n} similar sky conditions in history, Cosmo's top stock calls were correct {acc}% of the time."
        )

    # Direction narrative
    dp = patterns.get('direction_pattern', {})
    dominant = dp.get('dominant', '')
    if dominant:
        narratives.append(
            f"Market was {dominant} on most similar past days "
            f"({dp.get('bullish',0)}B / {dp.get('bearish',0)}Bear / {dp.get('neutral',0)}N)."
        )

    # Sector narrative
    top_secs = patterns.get('top_sectors_on_similar_days', [])
    if top_secs:
        sec_names = ', '.join(s['name'] for s in top_secs[:3])
        narratives.append(f"Strongest sectors on similar days: {sec_names}.")

    # Avg change narrative
    avg_chg = patterns.get('avg_stock_change_pct')
    if avg_chg is not None:
        direction = 'gained' if avg_chg > 0 else 'lost'
        narratives.append(
            f"Top flagged stocks {direction} an average of {abs(avg_chg)}% next day on similar conditions."
        )

    # Mars + Saturn day pattern
    if today_conditions.get('mars_rashi') and today_conditions.get('day_ruler'):
        narratives.append(
            f"Mars in {today_conditions['mars_rashi']} + Day of {today_conditions['day_ruler']} "
            f"is the dominant sky signature today."
        )

    return narratives

# ── Main Pattern Engine ───────────────────────────────────────────────────

def run_pattern_engine():
    print("\n🔭 Pattern Engine starting...")

    # Load data
    try:
        history = load_history()
    except FileNotFoundError:
        print("   ⚠ history.json not found. Run history engine first.")
        return

    try:
        latest = load_latest()
    except FileNotFoundError:
        print("   ⚠ latest.json not found.")
        return

    print(f"   History: {len(history)} days loaded")

    # Extract today's conditions
    today_snap = {
        'planets':          latest.get('astro', {}).get('planets', {}),
        'moon_phase':       latest.get('astro', {}).get('moon_phase', ''),
        'day_ruler':        latest.get('astro', {}).get('day_ruler', ''),
        'market_direction': latest.get('market', {}).get('direction', ''),
        'volatility_bias':  latest.get('market', {}).get('volatility_bias', ''),
        'strongest_sector': latest.get('summary', {}).get('strongest_sector', ''),
        'day_cosmo_score':  latest.get('summary', {}).get('day_cosmo_score', 50),
        'breadth_ratio':    latest.get('market', {}).get('breadth', {}).get('breadth_ratio', 50),
    }
    today_conditions = extract_conditions(today_snap)

    # Find similar days
    similar_days = find_similar_days(today_conditions, history, min_similarity=40)
    print(f"   Similar days found: {len(similar_days)}")

    # Analyze patterns
    patterns = analyze_patterns(similar_days)
    print(f"   Pattern status: {patterns.get('status')}")
    if patterns.get('overall_accuracy_pct'):
        print(f"   Historical accuracy: {patterns['overall_accuracy_pct']}%")

    # Build narratives
    narratives = build_narratives(today_conditions, patterns, similar_days)

    # Top similar days detail
    similar_detail = []
    for sim, snap in similar_days[:5]:
        hist_cond = extract_conditions(snap)
        explanation = explain_similarity(today_conditions, hist_cond, sim)
        similar_detail.append({
            'date':          snap['date'],
            'similarity_pct': sim,
            'cosmo_score':   snap.get('day_cosmo_score'),
            'moon_phase':    snap.get('moon_phase'),
            'day_ruler':     snap.get('day_ruler'),
            'strongest_sector': snap.get('strongest_sector'),
            'market_direction': snap.get('market_direction'),
            'outcome_accuracy': snap.get('outcomes', {}).get('accuracy_pct'),
            'explanation':   explanation,
        })

    # Build output
    output = {
        'meta': {
            'date':         latest.get('meta', {}).get('date'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'today_conditions':  today_conditions,
        'similar_days_found': len(similar_days),
        'patterns':          patterns,
        'narratives':        narratives,
        'similar_days':      similar_detail,
    }

    # Save
    with open(PATTERNS_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Pattern Engine complete → {PATTERNS_OUT}")
    print(f"   Narratives generated: {len(narratives)}")
    for n in narratives:
        print(f"   → {n}")

    return output


if __name__ == '__main__':
    run_pattern_engine()
