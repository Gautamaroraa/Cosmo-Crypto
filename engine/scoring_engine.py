"""
COSMO - Scoring Engine
Layer 4: Combines Astro + Technical + Rule signals into final Cosmo Score.
Produces daily intelligence output → data/latest.json
"""

import json
import os
import sys
from datetime import datetime, timezone

# ── Add engine path ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from astro_engine  import run_astro_engine
from market_engine import run_market_engine
from rule_engine   import run_rule_engine

# ── Score Weights ─────────────────────────────────────────────────────────
WEIGHTS = {
    'astro':      0.35,   # 35% — planetary conditions
    'technical':  0.40,   # 40% — price/volume/momentum
    'rule':       0.25,   # 25% — rule engine modifier
}

# ── Confidence Labels ─────────────────────────────────────────────────────
def confidence_label(score):
    if score >= 80:   return 'Very High'
    elif score >= 65: return 'High'
    elif score >= 50: return 'Medium'
    elif score >= 35: return 'Low'
    else:             return 'Very Low'

def direction_label(score, astro_bias):
    if score >= 65 and astro_bias >= 10:
        return 'Bullish'
    elif score <= 35 or astro_bias <= -20:
        return 'Bearish'
    else:
        return 'Neutral'

def risk_label(volatility_bias, moon_phase, retrograde_count):
    risk = 0
    if volatility_bias == 'High':    risk += 2
    elif volatility_bias == 'Medium': risk += 1
    if moon_phase in ['Full Moon', 'New Moon']: risk += 2
    elif moon_phase in ['Waning Crescent', 'Last Quarter']: risk += 1
    risk += retrograde_count
    if risk >= 5:   return 'Very High'
    elif risk >= 3: return 'High'
    elif risk >= 2: return 'Medium'
    else:           return 'Low'

# ── Cosmo Score Calculator ────────────────────────────────────────────────

def calculate_cosmo_score(technical_score, astro_score, rule_modifier):
    """
    Final Cosmo Score (0-100).
    Weighted combination of all three layers.
    """
    # Normalize astro_score from -100..100 to 0..100
    astro_normalized = (astro_score + 100) / 2

    # Normalize rule_modifier from -50..50 to 0..100
    rule_normalized = (rule_modifier + 50)

    cosmo = (
        technical_score  * WEIGHTS['technical'] +
        astro_normalized * WEIGHTS['astro']     +
        rule_normalized  * WEIGHTS['rule']
    )
    return round(max(0, min(100, cosmo)), 1)

# ── Sector Final Score ────────────────────────────────────────────────────

def score_sectors_final(sectors_ranked, sector_astro_bias):
    """
    Combines market sector score with astro sector bias
    into a final sector ranking.
    """
    final_sectors = []

    for sector_data in sectors_ranked:
        name = sector_data['name']
        market_score = sector_data['score']  # 0-100 from market engine

        astro_info = sector_astro_bias.get(name, {})
        astro_score_raw = astro_info.get('astro_score', 0)  # -100 to +100
        astro_score_normalized = (astro_score_raw + 100) / 2  # 0-100

        # Final sector score
        final_score = round(
            market_score * 0.55 + astro_score_normalized * 0.45,
            1
        )

        final_sectors.append({
            'name': name,
            'cosmo_score': final_score,
            'market_score': market_score,
            'astro_score': astro_score_raw,
            'astro_bias': astro_info.get('bias', 'Neutral'),
            'top_stocks': sector_data.get('top_stocks', []),
            'avg_rsi': sector_data.get('avg_rsi', 0),
            'bullish_count': sector_data.get('bullish_count', 0),
            'bearish_count': sector_data.get('bearish_count', 0),
            'notes': astro_info.get('notes', [])
        })

    # Sort by final score
    final_sectors.sort(key=lambda x: x['cosmo_score'], reverse=True)
    return final_sectors

# ── Stock Final Score ─────────────────────────────────────────────────────

def score_stocks_final(enriched_stocks, sector_astro_bias):
    """
    Produces final Cosmo Score for every stock.
    """
    scored_stocks = []

    for stock in enriched_stocks:
        sector = stock.get('sector', '')
        astro_info = sector_astro_bias.get(sector, {})
        astro_score_raw = astro_info.get('astro_score', 0)

        technical_score = stock.get('technical_score', 50)
        rule_modifier   = stock.get('rule_modifier', 0)

        cosmo_score = calculate_cosmo_score(
            technical_score,
            astro_score_raw,
            rule_modifier
        )

        stock['cosmo_score'] = cosmo_score
        stock['confidence']  = confidence_label(cosmo_score)
        stock['direction']   = direction_label(cosmo_score, astro_score_raw)

        scored_stocks.append(stock)

    # Sort by Cosmo Score
    scored_stocks.sort(key=lambda x: x['cosmo_score'], reverse=True)
    return scored_stocks

# ── Daily Intelligence Summary ────────────────────────────────────────────

def build_daily_summary(astro_data, market_data, rule_data, scored_sectors, scored_stocks):
    """
    Builds the top-level daily intelligence card.
    """
    retrograde_count = len(astro_data['retrograde_planets'])

    # Overall market astro score
    top_sector_astro = sum(
        s['astro_score'] for s in scored_sectors[:3]
    ) / 3 if scored_sectors else 0

    # Overall Cosmo Score for the day
    day_cosmo_score = calculate_cosmo_score(
        technical_score = market_data['breadth']['breadth_ratio'],
        astro_score     = astro_data['astro_score'],
        rule_modifier   = 10 if market_data['market_direction'] == 'Bullish' else -10
    )

    risk = risk_label(
        market_data['volatility_bias'],
        astro_data['moon_phase'],
        retrograde_count
    )

    # Top 5 stocks today
    top_stocks_today = scored_stocks[:5]

    # Strongest sector today
    strongest_sector = scored_sectors[0] if scored_sectors else {}
    weakest_sector   = scored_sectors[-1] if scored_sectors else {}

    # Build key signals list
    signals = []
    if astro_data['retrograde_planets']:
        signals.append(f"⚠ Retrograde: {', '.join(astro_data['retrograde_planets'])}")
    if astro_data['graha_yuddha']:
        wars = astro_data['graha_yuddha']
        signals.append(f"⚔ Graha Yuddha: {wars[0]['planets'][0]} vs {wars[0]['planets'][1]}")
    if astro_data['upcoming_transitions']:
        t = astro_data['upcoming_transitions'][0]
        signals.append(f"🔄 {t['planet']} moving {t['from']} → {t['to']} within {t['within_days']} days")
    signals.append(f"{rule_data['moon_intelligence']['phase']} — {rule_data['moon_intelligence']['note']}")
    signals.append(f"Day of {astro_data['day_ruler']} — favors {', '.join(rule_data['day_intelligence']['favored_sectors'])}")

    return {
        'day_cosmo_score': day_cosmo_score,
        'market_direction': market_data['market_direction'],
        'volatility_bias': market_data['volatility_bias'],
        'risk_level': risk,
        'momentum_quality': confidence_label(market_data['breadth']['breadth_ratio']),
        'strongest_sector': strongest_sector.get('name', ''),
        'weakest_sector': weakest_sector.get('name', ''),
        'top_stocks_today': [
            {
                'ticker': s['ticker'].replace('.NS', ''),
                'sector': s.get('sector', ''),
                'cosmo_score': s['cosmo_score'],
                'confidence': s['confidence'],
                'direction': s['direction'],
                'price': s['price'],
                'change_pct': s['change_pct'],
                'rsi': s['rsi'],
                'trend': s['trend'],
                'rule_flags': s.get('rule_flags', [])
            }
            for s in top_stocks_today
        ],
        'key_signals': signals,
        'breadth': market_data['breadth'],
    }

# ── Master Runner ─────────────────────────────────────────────────────────

def run_scoring_engine():
    """
    Runs all 4 layers and produces final output.
    """
    print("\n🪐 COSMO ENGINE STARTING...\n")
    print("=" * 50)

    # Layer 1
    print("\n[1/4] Astro Engine...")
    astro_data = run_astro_engine()
    print(f"      ✅ {astro_data['moon_phase']} | Day of {astro_data['day_ruler']} | Score: {astro_data['astro_score']}")

    # Layer 2
    print("\n[2/4] Market Engine...")
    market_data = run_market_engine()
    print(f"      ✅ {market_data['market_direction']} | Breadth: {market_data['breadth']['breadth_ratio']}%")

    # Layer 3
    print("\n[3/4] Rule Engine...")
    rule_data = run_rule_engine(astro_data, market_data)
    print(f"      ✅ Moon: {rule_data['moon_intelligence']['bias']} | Day ruler favors: {rule_data['day_intelligence']['favored_sectors']}")

    # Layer 4
    print("\n[4/4] Scoring Engine...")
    scored_sectors = score_sectors_final(
        market_data['sectors_ranked'],
        rule_data['sector_astro_bias']
    )
    scored_stocks = score_stocks_final(
        rule_data['enriched_stocks'],
        rule_data['sector_astro_bias']
    )
    summary = build_daily_summary(
        astro_data, market_data, rule_data,
        scored_sectors, scored_stocks
    )
    print(f"      ✅ Day Cosmo Score: {summary['day_cosmo_score']} | Risk: {summary['risk_level']}")

    # ── Build final output ────────────────────────────────────────────────
    output = {
        'meta': {
            'date': astro_data['date'],
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'version': '1.0'
        },
        'summary': summary,
        'astro': {
            'day_ruler': astro_data['day_ruler'],
            'moon_phase': astro_data['moon_phase'],
            'moon_phase_emoji': astro_data['moon_phase_emoji'],
            'astro_score': astro_data['astro_score'],
            'retrograde_planets': astro_data['retrograde_planets'],
            'planets': astro_data['planets'],
            'conjunctions': astro_data['conjunctions'],
            'aspects': astro_data['aspects'],
            'graha_yuddha': astro_data['graha_yuddha'],
            'upcoming_transitions': astro_data['upcoming_transitions'],
        },
        'market': {
            'direction': market_data['market_direction'],
            'volatility_bias': market_data['volatility_bias'],
            'breadth': market_data['breadth'],
            'indices': market_data['indices'],
        },
        'sectors': scored_sectors,
        'stocks': scored_stocks[:50],   # Top 50 stocks
        'intelligence': {
            'moon': rule_data['moon_intelligence'],
            'day_ruler': rule_data['day_intelligence'],
            'sector_astro_bias': rule_data['sector_astro_bias'],
        }
    }

    # ── Save output ───────────────────────────────────────────────────────
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)

    # latest.json — always current day
    latest_path = os.path.join(data_dir, 'latest.json')
    with open(latest_path, 'w') as f:
        json.dump(output, f, indent=2)

    # Archive by date
    archive_path = os.path.join(data_dir, f"{astro_data['date']}.json")
    with open(archive_path, 'w') as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 50)
    print(f"\n✅ COSMO ENGINE COMPLETE")
    print(f"   Date          : {astro_data['date']}")
    print(f"   Cosmo Score   : {summary['day_cosmo_score']}/100")
    print(f"   Direction     : {summary['market_direction']}")
    print(f"   Risk Level    : {summary['risk_level']}")
    print(f"   Top Sector    : {summary['strongest_sector']}")
    print(f"\n   Top Stocks Today:")
    for s in summary['top_stocks_today']:
        print(f"   {s['ticker']:12} {s['cosmo_score']:5.1f}  {s['direction']:8}  {s['confidence']}")
    print(f"\n   Saved → {latest_path}")

    return output

# ── Entry Point ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    run_scoring_engine()
