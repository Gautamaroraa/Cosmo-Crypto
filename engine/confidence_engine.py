"""
COSMO - Confidence Engine
Refines scoring based on historical outcomes.
Builds confidence intervals for current predictions.
Tells you HOW MUCH to trust today's calls.
"""

import json
import os
from datetime import datetime, timezone

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR        = os.path.join(os.path.dirname(__file__), '..', 'data')
HISTORY_PATH    = os.path.join(DATA_DIR, 'history.json')
LATEST_PATH     = os.path.join(DATA_DIR, 'latest.json')
PATTERNS_PATH   = os.path.join(DATA_DIR, 'patterns.json')
CONFIDENCE_OUT  = os.path.join(DATA_DIR, 'confidence.json')

# ── Minimum data thresholds ───────────────────────────────────────────────
MIN_DAYS_FOR_CALIBRATION = 5
MIN_DAYS_FOR_REFINEMENT  = 15
MIN_DAYS_FOR_FULL        = 30

# ── Load Data ─────────────────────────────────────────────────────────────

def load_history():
    with open(HISTORY_PATH, 'r') as f:
        return json.load(f)

def load_latest():
    with open(LATEST_PATH, 'r') as f:
        return json.load(f)

def load_patterns():
    try:
        with open(PATTERNS_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# ── Score Calibration ─────────────────────────────────────────────────────

def build_score_calibration(history_snapshots):
    """
    Analyzes how well different Cosmo Score ranges have predicted outcomes.
    Returns calibration table: score_range → accuracy.
    """
    completed = [
        s for s in history_snapshots
        if s.get('outcomes', {}).get('status') == 'calculated'
    ]

    if len(completed) < MIN_DAYS_FOR_CALIBRATION:
        return {
            'status': 'insufficient_data',
            'days_needed': MIN_DAYS_FOR_CALIBRATION - len(completed),
            'days_available': len(completed),
        }

    # Build score buckets
    buckets = {
        '80-100': {'correct': 0, 'total': 0, 'changes': []},
        '65-79':  {'correct': 0, 'total': 0, 'changes': []},
        '50-64':  {'correct': 0, 'total': 0, 'changes': []},
        '35-49':  {'correct': 0, 'total': 0, 'changes': []},
        '0-34':   {'correct': 0, 'total': 0, 'changes': []},
    }

    for snap in completed:
        outcomes = snap.get('outcomes', {}).get('stocks', {})
        for ticker, outcome in outcomes.items():
            # Find the stock's cosmo score from top_stocks
            stock_score = None
            for s in snap.get('top_stocks', []):
                if s['ticker'] == ticker:
                    stock_score = s.get('cosmo_score', 50)
                    break

            if stock_score is None:
                stock_score = snap.get('day_cosmo_score', 50)

            # Assign to bucket
            if stock_score >= 80:   bucket = '80-100'
            elif stock_score >= 65: bucket = '65-79'
            elif stock_score >= 50: bucket = '50-64'
            elif stock_score >= 35: bucket = '35-49'
            else:                   bucket = '0-34'

            buckets[bucket]['total'] += 1
            if outcome.get('correct'):
                buckets[bucket]['correct'] += 1
            if 'change_pct' in outcome:
                buckets[bucket]['changes'].append(outcome['change_pct'])

    calibration = {}
    for bucket, data in buckets.items():
        if data['total'] > 0:
            acc = round((data['correct'] / data['total']) * 100, 1)
            avg_chg = round(sum(data['changes']) / len(data['changes']), 2) if data['changes'] else None
            calibration[bucket] = {
                'accuracy_pct':       acc,
                'avg_change_pct':     avg_chg,
                'sample_size':        data['total'],
                'correct_calls':      data['correct'],
            }
        else:
            calibration[bucket] = {
                'accuracy_pct':   None,
                'avg_change_pct': None,
                'sample_size':    0,
                'correct_calls':  0,
            }

    return {'status': 'calculated', 'buckets': calibration}

# ── Condition Confidence ──────────────────────────────────────────────────

def build_condition_confidence(history_snapshots):
    """
    For specific conditions (moon phase, day ruler, planet positions),
    calculates how often they led to correct calls.
    """
    completed = [
        s for s in history_snapshots
        if s.get('outcomes', {}).get('status') == 'calculated'
    ]

    if len(completed) < MIN_DAYS_FOR_CALIBRATION:
        return {'status': 'insufficient_data'}

    # Moon phase confidence
    moon_conf = {}
    for snap in completed:
        phase = snap.get('moon_phase', '')
        acc   = snap.get('outcomes', {}).get('accuracy_pct')
        if phase and acc is not None:
            if phase not in moon_conf:
                moon_conf[phase] = {'accuracies': [], 'days': 0}
            moon_conf[phase]['accuracies'].append(acc)
            moon_conf[phase]['days'] += 1

    moon_confidence = {
        phase: {
            'avg_accuracy': round(sum(d['accuracies']) / len(d['accuracies']), 1),
            'days':         d['days'],
        }
        for phase, d in moon_conf.items()
    }

    # Day ruler confidence
    ruler_conf = {}
    for snap in completed:
        ruler = snap.get('day_ruler', '')
        acc   = snap.get('outcomes', {}).get('accuracy_pct')
        if ruler and acc is not None:
            if ruler not in ruler_conf:
                ruler_conf[ruler] = {'accuracies': [], 'days': 0}
            ruler_conf[ruler]['accuracies'].append(acc)
            ruler_conf[ruler]['days'] += 1

    ruler_confidence = {
        ruler: {
            'avg_accuracy': round(sum(d['accuracies']) / len(d['accuracies']), 1),
            'days':         d['days'],
        }
        for ruler, d in ruler_conf.items()
    }

    # Sector confidence — how often top-ranked sector actually performed well
    sector_conf = {}
    for snap in completed:
        strongest = snap.get('strongest_sector', '')
        outcomes  = snap.get('outcomes', {}).get('stocks', {})
        if strongest and outcomes:
            # Check if stocks from strongest sector performed well
            sector_stocks_correct = []
            for s in snap.get('top_stocks', []):
                if s.get('sector') == strongest:
                    ticker = s['ticker']
                    if ticker in outcomes:
                        sector_stocks_correct.append(outcomes[ticker].get('correct', False))

            if sector_stocks_correct:
                correct_pct = sum(sector_stocks_correct) / len(sector_stocks_correct) * 100
                if strongest not in sector_conf:
                    sector_conf[strongest] = []
                sector_conf[strongest].append(correct_pct)

    sector_confidence = {
        sector: {
            'avg_accuracy': round(sum(accs) / len(accs), 1),
            'days':         len(accs),
        }
        for sector, accs in sector_conf.items()
    }

    return {
        'status':             'calculated',
        'moon_phase':         moon_confidence,
        'day_ruler':          ruler_confidence,
        'sector':             sector_confidence,
    }

# ── Today's Confidence Assessment ────────────────────────────────────────

def assess_today_confidence(latest, calibration, condition_confidence, patterns):
    """
    Gives today a confidence rating based on all available data.
    Returns: confidence_level, confidence_score, explanation.
    """
    confidence_score = 50  # Base
    factors = []
    warnings = []

    summary = latest.get('summary', {})
    astro   = latest.get('astro', {})

    day_cosmo_score = summary.get('day_cosmo_score', 50)
    moon_phase      = astro.get('moon_phase', '')
    day_ruler       = astro.get('day_ruler', '')
    retrograde      = astro.get('retrograde_planets', [])
    risk_level      = summary.get('risk_level', 'Medium')

    # 1. Score calibration factor
    if calibration.get('status') == 'calculated':
        buckets = calibration.get('buckets', {})
        if day_cosmo_score >= 80:   bucket_key = '80-100'
        elif day_cosmo_score >= 65: bucket_key = '65-79'
        elif day_cosmo_score >= 50: bucket_key = '50-64'
        elif day_cosmo_score >= 35: bucket_key = '35-49'
        else:                       bucket_key = '0-34'

        bucket_data = buckets.get(bucket_key, {})
        bucket_acc  = bucket_data.get('accuracy_pct')
        if bucket_acc is not None:
            adjustment = (bucket_acc - 50) * 0.3
            confidence_score += adjustment
            factors.append(
                f"Score {bucket_key} range has historically been {bucket_acc}% accurate"
            )

    # 2. Moon phase confidence
    moon_conf = condition_confidence.get('moon_phase', {})
    moon_data = moon_conf.get(moon_phase, {})
    moon_acc  = moon_data.get('avg_accuracy')
    if moon_acc is not None:
        adjustment = (moon_acc - 50) * 0.2
        confidence_score += adjustment
        factors.append(f"{moon_phase} has been {moon_acc}% accurate historically")

    # 3. Day ruler confidence
    ruler_conf = condition_confidence.get('day_ruler', {})
    ruler_data = ruler_conf.get(day_ruler, {})
    ruler_acc  = ruler_data.get('avg_accuracy')
    if ruler_acc is not None:
        adjustment = (ruler_acc - 50) * 0.2
        confidence_score += adjustment
        factors.append(f"Day of {day_ruler} has been {ruler_acc}% accurate historically")

    # 4. Pattern similarity bonus
    pattern_data = patterns.get('patterns', {})
    if pattern_data.get('status') == 'calculated':
        hist_acc = pattern_data.get('overall_accuracy_pct')
        if hist_acc is not None:
            adjustment = (hist_acc - 50) * 0.25
            confidence_score += adjustment
            n = patterns.get('similar_days_found', 0)
            factors.append(f"On {n} similar sky days, accuracy was {hist_acc}%")

    # 5. Risk penalties
    if risk_level == 'Very High':
        confidence_score -= 15
        warnings.append("Very high risk conditions — reduce position size")
    elif risk_level == 'High':
        confidence_score -= 8
        warnings.append("High risk day — use tighter stop losses")

    # 6. Retrograde penalties
    major_retro = [p for p in retrograde if p in ['Mercury', 'Mars', 'Jupiter', 'Venus']]
    if major_retro:
        confidence_score -= len(major_retro) * 4
        warnings.append(f"{', '.join(major_retro)} retrograde — signals may be unreliable")

    # 7. Full Moon / New Moon warning
    if moon_phase in ['Full Moon', 'New Moon']:
        confidence_score -= 10
        warnings.append(f"{moon_phase} — expect reversals and volatility")

    # Clamp
    confidence_score = round(max(0, min(100, confidence_score)), 1)

    # Confidence level label
    if confidence_score >= 75:
        level = 'High Confidence'
    elif confidence_score >= 60:
        level = 'Moderate Confidence'
    elif confidence_score >= 45:
        level = 'Low Confidence'
    else:
        level = 'Very Low Confidence'

    return {
        'confidence_score': confidence_score,
        'confidence_level': level,
        'factors':          factors,
        'warnings':         warnings,
    }

# ── Weight Refinement Suggestions ────────────────────────────────────────

def suggest_weight_refinements(history_snapshots, calibration):
    """
    After enough data, suggests which scoring weights to adjust.
    """
    completed = [
        s for s in history_snapshots
        if s.get('outcomes', {}).get('status') == 'calculated'
    ]

    if len(completed) < MIN_DAYS_FOR_REFINEMENT:
        return {
            'status': 'insufficient_data',
            'message': f"Need {MIN_DAYS_FOR_REFINEMENT} days with outcomes. Have {len(completed)}.",
        }

    suggestions = []

    # Check if high Cosmo Score days are actually more accurate
    high_score_days = [s for s in completed if s.get('day_cosmo_score', 0) >= 65]
    low_score_days  = [s for s in completed if s.get('day_cosmo_score', 0) < 50]

    if high_score_days and low_score_days:
        high_acc = sum(
            s['outcomes'].get('accuracy_pct', 50) for s in high_score_days
        ) / len(high_score_days)
        low_acc = sum(
            s['outcomes'].get('accuracy_pct', 50) for s in low_score_days
        ) / len(low_score_days)

        if high_acc > low_acc + 10:
            suggestions.append({
                'type':    'weight_increase',
                'target':  'cosmo_score_threshold',
                'reason':  f"High score days ({round(high_acc,1)}%) significantly outperform low score days ({round(low_acc,1)}%)",
                'action':  'Consider only trading when Cosmo Score > 65'
            })
        elif high_acc < low_acc:
            suggestions.append({
                'type':   'investigation',
                'target': 'cosmo_score_weights',
                'reason': f"Unexpectedly, lower score days outperform higher score days",
                'action': 'Review rule engine weights'
            })

    # Moon phase refinement
    moon_accs = {}
    for snap in completed:
        phase = snap.get('moon_phase', '')
        acc   = snap.get('outcomes', {}).get('accuracy_pct')
        if phase and acc is not None:
            if phase not in moon_accs:
                moon_accs[phase] = []
            moon_accs[phase].append(acc)

    for phase, accs in moon_accs.items():
        if len(accs) >= 3:
            avg = sum(accs) / len(accs)
            if avg >= 70:
                suggestions.append({
                    'type':   'weight_increase',
                    'target': f'moon_phase:{phase}',
                    'reason': f"{phase} shows {round(avg,1)}% accuracy — strong signal",
                    'action': f'Increase confidence multiplier for {phase}'
                })
            elif avg <= 35:
                suggestions.append({
                    'type':   'weight_decrease',
                    'target': f'moon_phase:{phase}',
                    'reason': f"{phase} shows only {round(avg,1)}% accuracy — weak signal",
                    'action': f'Reduce position size or skip on {phase}'
                })

    return {
        'status':      'calculated',
        'suggestions': suggestions,
        'based_on':    len(completed),
    }

# ── Main Confidence Engine ────────────────────────────────────────────────

def run_confidence_engine():
    print("\n🎯 Confidence Engine starting...")

    # Load data
    try:
        history_data = load_history()
        history_snapshots = history_data.get('history', [])
    except FileNotFoundError:
        print("   ⚠ history.json not found.")
        return

    try:
        latest = load_latest()
    except FileNotFoundError:
        print("   ⚠ latest.json not found.")
        return

    patterns = load_patterns()

    print(f"   History: {len(history_snapshots)} days")

    # Build calibration
    calibration = build_score_calibration(history_snapshots)
    print(f"   Calibration: {calibration.get('status')}")

    # Build condition confidence
    condition_confidence = build_condition_confidence(history_snapshots)
    print(f"   Condition confidence: {condition_confidence.get('status')}")

    # Assess today
    today_confidence = assess_today_confidence(
        latest, calibration, condition_confidence, patterns
    )
    print(f"   Today: {today_confidence['confidence_level']} ({today_confidence['confidence_score']})")

    # Weight refinement suggestions
    refinements = suggest_weight_refinements(history_snapshots, calibration)
    print(f"   Refinements: {refinements.get('status')}")

    # Build output
    output = {
        'meta': {
            'date':         latest.get('meta', {}).get('date'),
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'total_days':   len(history_snapshots),
        },
        'today': today_confidence,
        'calibration': calibration,
        'condition_confidence': condition_confidence,
        'refinement_suggestions': refinements,
        'data_quality': {
            'days_total':           len(history_snapshots),
            'days_with_outcomes':   sum(
                1 for s in history_snapshots
                if s.get('outcomes', {}).get('status') == 'calculated'
            ),
            'calibration_ready':    len(history_snapshots) >= MIN_DAYS_FOR_CALIBRATION,
            'refinement_ready':     len(history_snapshots) >= MIN_DAYS_FOR_REFINEMENT,
            'full_confidence_ready': len(history_snapshots) >= MIN_DAYS_FOR_FULL,
        }
    }

    with open(CONFIDENCE_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Confidence Engine complete → {CONFIDENCE_OUT}")
    print(f"   Confidence Score : {today_confidence['confidence_score']}/100")
    print(f"   Confidence Level : {today_confidence['confidence_level']}")
    if today_confidence['warnings']:
        for w in today_confidence['warnings']:
            print(f"   ⚠ {w}")
    if today_confidence['factors']:
        for f in today_confidence['factors']:
            print(f"   → {f}")

    return output


if __name__ == '__main__':
    run_confidence_engine()
