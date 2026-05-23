"""
COSMO - Scoring Engine
Layer 4: Combines Astro + Technical + Rule signals into final Cosmo Score.
Produces daily intelligence output → data/latest.json
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

# ── Add engine path ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from astro_engine  import run_astro_engine
from market_engine import run_market_engine
from rule_engine   import run_rule_engine

# ── NaN Cleaner (fixes invalid JSON from yfinance) ────────────────────────
def clean_nans(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(i) for i in obj]
    return obj

# ── Score Weights ─────────────────────────────────────────────────────────
WEIGHTS = {
    'astro':      0.35,
    'technical':  0.40,
    'rule':       0.25,
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
    astro_normalized = (astro_score + 100) / 2
    rule_normalized  = (rule_modifier + 50)
    cosmo = (
        technical_score  * WEIGHTS['technical'] +
        astro_normalized * WEIGHTS['astro']     +
        rule_normalized  * WEIGHTS['rule']
    )
    return round(max(0, min(100, cosmo)), 1)

# ── Sector Final Score ────────────────────────────────────────────────────

def score_sectors_final(sectors_ranked, sector_astro_bias):
    final_sectors = []
    for sector_data in sectors_ranked:
        name = sector_data['name']
        market_score = sector_data['score']
        astro_info = sector_astro_bias.get(name, {})
        astro_score_raw = astro_info.get('astro_score', 0)
        astro_score_normalized = (astro_score_raw + 100) / 2
        final_score = round(market_score * 0.55 + astro_score_normalized * 0.45, 1)
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
    final_sectors.sort(key=lambda x: x['cosmo_score'], reverse=True)
    return final_sectors

# ── Stock Final Score ─────────────────────────────────────────────────────

def score_stocks_final(enriched_stocks, sector_astro_bias):
    scored_stocks = []
    for stock in enriched_stocks:
        sector = stock.get('sector', '')
        astro_info = sector_astro_bias.get(sector, {})
        astro_score_raw = astro_info.get('astro_score', 0)
        technical_score = stock.get('technical_score', 50)
        rule_modifier   = stock.get('rule_modifier', 0)
        cosmo_score = calculate_cosmo_score(technical_score, astro_score_raw, rule_modifier)
        stock['cosmo_score'] = cosmo_score
        stock['confidence']  = confidence_label(cosmo_score)
        stock['direction']   = direction_label(cosmo_score, astro_score_raw)
        scored_stocks.append(stock)
    scored_stocks.sort(key=lambda x: x['cosmo_score'], reverse=True)
    return scored_stocks

# ── Daily Intelligence Summary ────────────────────────────────────────────

def build_daily_summary(astro_data, market_data, rule_data, scored_sectors, scored_stocks):
    retrograde_count = len(astro_data['retrograde_planets'])
    day_cosmo_score = calculate_cosmo_score(
        technical_score = market_data['breadth']['breadth_ratio'],
        astro_score     = astro_data['astro_score'],
        rule_modifier   = 10 if market_data['market_direction'] == 'Bullish' else -10
    )
    risk = risk_label(market_data['volatility_bias'], astro_data['moon_phase'], retrograde_count)
    top_stocks_today = scored_stocks[:5]
    strongest_sector = scored_sectors[0] if scored_sectors else {}
    weakest_sector   = scored_sectors[-1] if scored_sectors else {}
    signals = []
    if astro_data['retrograde_planets']:
        signals.append(f"Retrograde: {', '.join(astro_data['retrograde_planets'])}")
    if astro_data['graha_yuddha']:
        wars = astro_data['graha_yuddha']
        signals.append(f"Graha Yuddha: {wars[0]['planets'][0]} vs {wars[0]['planets'][1]}")
    if astro_data['upcoming_transitions']:
        t = astro_data['upcoming_transitions'][0]
        signals.append(f"{t['planet']} moving {t['from']} to {t['to']} within {t['within_days']} days")
    signals.append(f"{rule_data['moon_intelligence']['phase']} - {rule_data['moon_intelligence']['note']}")
    signals.append(f"Day of {astro_data['day_ruler']} - favors {', '.join(rule_data['day_intelligence']['favored_sectors'])}")
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
    print("\n🪐 COSMO ENGINE STARTING...\n")
    print("=" * 50)

    print("\n[1/4] Astro Engine...")
    astro_data = run_astro_engine()
    print(f"      {astro_data['moon_phase']} | Day of {astro_data['day_ruler']} | Score: {astro_data['astro_score']}")

    print("\n[2/4] Market Engine...")
    market_data = run_market_engine()
    print(f"      {market_data['market_direction']} | Breadth: {market_data['breadth']['breadth_ratio']}%")

    print("\n[3/4] Rule Engine...")
    rule_data = run_rule_engine(astro_data, market_data)
    print(f"      Moon: {rule_data['moon_intelligence']['bias']} | Favors: {rule_data['day_intelligence']['favored_sectors']}")

    print("\n[4/4] Scoring Engine...")
    scored_sectors = score_sectors_final(market_data['sectors_ranked'], rule_data['sector_astro_bias'])
    scored_stocks  = score_stocks_final(rule_data['enriched_stocks'], rule_data['sector_astro_bias'])
    summary = build_daily_summary(astro_data, market_data, rule_data, scored_sectors, scored_stocks)
    print(f"      Day Cosmo Score: {summary['day_cosmo_score']} | Risk: {summary['risk_level']}")

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
        'stocks': scored_stocks[:50],
        'intelligence': {
            'moon': rule_data['moon_intelligence'],
            'day_ruler': rule_data['day_intelligence'],
            'sector_astro_bias': rule_data['sector_astro_bias'],
        }
    }

    # Clean NaN/Inf before saving
    output = clean_nans(output)

    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)

    latest_path  = os.path.join(data_dir, 'latest.json')
    archive_path = os.path.join(data_dir, f"{astro_data['date']}.json")

    with open(latest_path, 'w') as f:
        json.dump(output, f, indent=2)

    with open(archive_path, 'w') as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 50)
    print(f"\nCOSMO ENGINE COMPLETE")
    print(f"   Date       : {astro_data['date']}")
    print(f"   Cosmo Score: {summary['day_cosmo_score']}/100")
    print(f"   Direction  : {summary['market_direction']}")
    print(f"   Risk Level : {summary['risk_level']}")
    print(f"   Top Sector : {summary['strongest_sector']}")
    print(f"\n   Top Stocks:")
    for s in summary['top_stocks_today']:
        print(f"   {s['ticker']:12} {s['cosmo_score']:5.1f}  {s['direction']:8}  {s['confidence']}")
    print(f"\n   Saved to {latest_path}")

    return output

if __name__ == '__main__':
    run_scoring_engine()
