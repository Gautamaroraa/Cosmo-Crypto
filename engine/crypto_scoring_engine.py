"""
COSMO CRYPTO - Scoring Engine
Master runner. Combines all 4 layers into final Cosmo Crypto Score.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from crypto_astro_engine  import run_astro_engine
from crypto_market_engine import run_market_engine
from crypto_rule_engine   import run_rule_engine

DATA_DIR    = os.path.join(os.path.dirname(__file__), '..', 'data')
LATEST_OUT  = os.path.join(DATA_DIR, 'latest.json')

WEIGHTS = {'astro': 0.30, 'technical': 0.45, 'rule': 0.25}

def clean_nans(obj):
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    elif isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(i) for i in obj]
    return obj

def confidence_label(score):
    if score >= 80:   return 'Very High'
    elif score >= 65: return 'High'
    elif score >= 50: return 'Medium'
    elif score >= 35: return 'Low'
    return 'Very Low'

def direction_label(score, astro_bias):
    if score >= 65 and astro_bias >= 10:  return 'Bullish'
    elif score <= 35 or astro_bias <= -20: return 'Bearish'
    return 'Neutral'

def risk_label(volatility_bias, moon_phase, retro_count):
    risk = 0
    if volatility_bias == 'High':    risk += 2
    elif volatility_bias == 'Medium': risk += 1
    if moon_phase in ['Full Moon', 'New Moon']:          risk += 2
    elif moon_phase in ['Waning Crescent','Last Quarter']: risk += 1
    risk += retro_count
    if risk >= 5:   return 'Very High'
    elif risk >= 3: return 'High'
    elif risk >= 2: return 'Medium'
    return 'Low'

def calculate_cosmo_score(tech_score, astro_score, rule_modifier):
    astro_norm = (astro_score + 100) / 2
    rule_norm  = rule_modifier + 50
    score = (tech_score * WEIGHTS['technical'] + astro_norm * WEIGHTS['astro'] + rule_norm * WEIGHTS['rule'])
    return round(max(0, min(100, score)), 1)

def score_sectors_final(sectors_ranked, sector_astro_bias):
    final = []
    for sec in sectors_ranked:
        name  = sec['name']
        ms    = sec['score']
        astro = sector_astro_bias.get(name, {})
        ar    = astro.get('astro_score', 0)
        an    = (ar + 100) / 2
        fs    = round(ms * 0.55 + an * 0.45, 1)
        final.append({
            'name': name, 'cosmo_score': fs, 'market_score': ms,
            'astro_score': ar, 'astro_bias': astro.get('bias', 'Neutral'),
            'top_coins': sec.get('top_coins', []),
            'avg_rsi': sec.get('avg_rsi', 0),
            'bullish_count': sec.get('bullish_count', 0),
            'bearish_count': sec.get('bearish_count', 0),
            'notes': astro.get('notes', [])
        })
    final.sort(key=lambda x: x['cosmo_score'], reverse=True)
    return final

def score_coins_final(enriched_coins, sector_astro_bias):
    scored = []
    for coin in enriched_coins:
        sector   = coin.get('sector', '')
        astro_info = sector_astro_bias.get(sector, {})
        ar       = astro_info.get('astro_score', 0)
        ts       = coin.get('technical_score', 50)
        rm       = coin.get('rule_modifier', 0)
        cs       = calculate_cosmo_score(ts, ar, rm)
        coin['cosmo_score'] = cs
        coin['confidence']  = confidence_label(cs)
        coin['direction']   = direction_label(cs, ar)
        scored.append(coin)
    scored.sort(key=lambda x: x['cosmo_score'], reverse=True)
    return scored

def build_summary(astro_data, market_data, rule_data, scored_sectors, scored_coins):
    retro_count = len(astro_data['retrograde_planets'])
    day_cosmo   = calculate_cosmo_score(
        market_data['breadth'].get('breadth_ratio', 50),
        astro_data['astro_score'],
        10 if market_data['market_direction'] == 'Bullish' else -10
    )
    risk = risk_label(market_data['volatility_bias'], astro_data['moon_phase'], retro_count)

    top5 = scored_coins[:5]
    strongest = scored_sectors[0] if scored_sectors else {}
    weakest   = scored_sectors[-1] if scored_sectors else {}

    signals = []
    if astro_data['retrograde_planets']:
        signals.append(f"Retrograde: {', '.join(astro_data['retrograde_planets'])}")
    if astro_data['upcoming_transitions']:
        t = astro_data['upcoming_transitions'][0]
        signals.append(f"{t['planet']} moving {t['from']} to {t['to']} within {t['within_days']} days")
    signals.append(f"{rule_data['moon_intelligence']['phase']} - {rule_data['moon_intelligence']['note']}")
    signals.append(f"Day of {astro_data['day_ruler']} - favors {', '.join(rule_data['day_intelligence']['favored_sectors'])}")

    # Funding rate signals
    high_funding = [c for c in scored_coins[:20] if c.get('funding_rate', {}) and c['funding_rate'].get('rate', 0) > 0.08]
    if high_funding:
        signals.append(f"High funding rates: {', '.join(c['name'] for c in high_funding[:3])} — longs crowded")

    return {
        'day_cosmo_score':   day_cosmo,
        'market_direction':  market_data['market_direction'],
        'volatility_bias':   market_data['volatility_bias'],
        'risk_level':        risk,
        'momentum_quality':  confidence_label(market_data['breadth'].get('breadth_ratio', 50)),
        'strongest_sector':  strongest.get('name', ''),
        'weakest_sector':    weakest.get('name', ''),
        'btc_dominance':     market_data.get('breadth', {}).get('btc_dominance_proxy', 0),
        'top_coins_today': [
            {
                'symbol':      c['symbol'],
                'name':        c['name'],
                'sector':      c.get('sector', ''),
                'cosmo_score': c['cosmo_score'],
                'confidence':  c['confidence'],
                'direction':   c['direction'],
                'price':       c['price'],
                'change_pct':  c['change_pct'],
                'rsi':         c['rsi'],
                'trend':       c['trend'],
                'rule_flags':  c.get('rule_flags', []),
                'funding_rate': c.get('funding_rate'),
            }
            for c in top5
        ],
        'key_signals': signals,
        'breadth': market_data['breadth'],
        'reference': market_data.get('reference', {}),
    }

def run_scoring_engine():
    print("\n🪐 COSMO CRYPTO ENGINE STARTING...\n" + "="*50)

    print("\n[1/4] Astro Engine...")
    astro_data = run_astro_engine()
    print(f"      {astro_data['moon_phase']} | Day of {astro_data['day_ruler']} | Score: {astro_data['astro_score']}")

    print("\n[2/4] Market Engine...")
    market_data = run_market_engine()
    print(f"      {market_data['market_direction']} | Breadth: {market_data['breadth'].get('breadth_ratio')}%")

    print("\n[3/4] Rule Engine...")
    rule_data = run_rule_engine(astro_data, market_data)
    print(f"      Moon: {rule_data['moon_intelligence']['bias']} | Favors: {rule_data['day_intelligence']['favored_sectors']}")

    print("\n[4/4] Scoring Engine...")
    scored_sectors = score_sectors_final(market_data['sectors_ranked'], rule_data['sector_astro_bias'])
    scored_coins   = score_coins_final(rule_data['enriched_coins'], rule_data['sector_astro_bias'])
    summary        = build_summary(astro_data, market_data, rule_data, scored_sectors, scored_coins)
    print(f"      Day Cosmo Score: {summary['day_cosmo_score']} | Risk: {summary['risk_level']}")

    output = {
        'meta': {
            'date':         astro_data['date'],
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'version':      '1.0',
            'type':         'crypto'
        },
        'summary': summary,
        'astro': {
            'day_ruler':          astro_data['day_ruler'],
            'moon_phase':         astro_data['moon_phase'],
            'moon_phase_emoji':   astro_data['moon_phase_emoji'],
            'astro_score':        astro_data['astro_score'],
            'retrograde_planets': astro_data['retrograde_planets'],
            'planets':            astro_data['planets'],
            'conjunctions':       astro_data['conjunctions'],
            'aspects':            astro_data['aspects'],
            'graha_yuddha':       astro_data['graha_yuddha'],
            'upcoming_transitions': astro_data['upcoming_transitions'],
        },
        'market': {
            'direction':      market_data['market_direction'],
            'volatility_bias': market_data['volatility_bias'],
            'breadth':         market_data['breadth'],
            'reference':       market_data.get('reference', {}),
        },
        'sectors': scored_sectors,
        'coins':   scored_coins[:40],
        'intelligence': {
            'moon':              rule_data['moon_intelligence'],
            'day_ruler':         rule_data['day_intelligence'],
            'sector_astro_bias': rule_data['sector_astro_bias'],
        }
    }

    output = clean_nans(output)

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(LATEST_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    archive = os.path.join(DATA_DIR, f"{astro_data['date']}.json")
    with open(archive, 'w') as f:
        json.dump(output, f, indent=2)

    print("\n" + "="*50)
    print(f"\nCOSMO CRYPTO COMPLETE")
    print(f"   Score     : {summary['day_cosmo_score']}/100")
    print(f"   Direction : {summary['market_direction']}")
    print(f"   Risk      : {summary['risk_level']}")
    print(f"   Top Sector: {summary['strongest_sector']}")
    print(f"\n   Top Coins:")
    for c in summary['top_coins_today']:
        print(f"   {c['name']:10} {c['cosmo_score']:5.1f}  {c['direction']:8}  {c['confidence']}")

    return output

if __name__ == '__main__':
    run_scoring_engine()
