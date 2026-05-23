"""
COSMO CRYPTO - Astro Engine
Planetary positions mapped to crypto sector psychology.
Crypto markets are 24/7 — astro influence is continuous.
"""

import swisseph as swe
import json
import os
from datetime import datetime, timezone

EPHE_PATH = os.path.join(os.path.dirname(__file__), '..', 'ephe')
swe.set_ephe_path(EPHE_PATH)

DATA_DIR  = os.path.join(os.path.dirname(__file__), '..', 'data')
ASTRO_OUT = os.path.join(DATA_DIR, 'astro_data.json')

PLANETS = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
    'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
    'Venus': swe.VENUS, 'Saturn': swe.SATURN,
    'Rahu': swe.MEAN_NODE, 'Ketu': None,
}

RASHIS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
RASHI_LORDS = {'Aries':'Mars','Taurus':'Venus','Gemini':'Mercury','Cancer':'Moon','Leo':'Sun','Virgo':'Mercury','Libra':'Venus','Scorpio':'Mars','Sagittarius':'Jupiter','Capricorn':'Saturn','Aquarius':'Saturn','Pisces':'Jupiter'}

NAKSHATRAS = ['Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra','Punarvasu','Pushya','Ashlesha','Magha','Purva Phalguni','Uttara Phalguni','Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha','Mula','Purva Ashadha','Uttara Ashadha','Shravana','Dhanishtha','Shatabhisha','Purva Bhadrapada','Uttara Bhadrapada','Revati']
NAKSHATRA_LORDS = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury','Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury','Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']

DAY_RULERS = {0:'Moon',1:'Mars',2:'Mercury',3:'Jupiter',4:'Venus',5:'Saturn',6:'Sun'}

# ── Crypto-specific planetary sector map ─────────────────────────────────
# Crypto sectors respond differently than traditional markets
CRYPTO_PLANET_SECTOR_MAP = {
    'Sun':     {'sectors': ['L1', 'Infra'],           'strong': ['Leo','Aries'],      'weak': ['Libra','Aquarius']},
    'Moon':    {'sectors': ['Meme', 'Gaming'],         'strong': ['Cancer','Taurus'],  'weak': ['Scorpio','Capricorn']},
    'Mars':    {'sectors': ['L1', 'Gaming', 'Meme'],   'strong': ['Aries','Scorpio','Capricorn'], 'weak': ['Cancer','Taurus']},
    'Mercury': {'sectors': ['DeFi', 'Infra', 'L2'],   'strong': ['Gemini','Virgo'],   'weak': ['Pisces','Sagittarius']},
    'Jupiter': {'sectors': ['L1', 'DeFi', 'L2'],      'strong': ['Sagittarius','Pisces','Cancer'], 'weak': ['Capricorn','Gemini']},
    'Venus':   {'sectors': ['Meme', 'Gaming', 'DeFi'],'strong': ['Taurus','Libra','Pisces'], 'weak': ['Aries','Scorpio','Virgo']},
    'Saturn':  {'sectors': ['Infra', 'L2', 'DeFi'],   'strong': ['Capricorn','Aquarius','Libra'], 'weak': ['Aries','Cancer','Leo']},
    'Rahu':    {'sectors': ['Meme', 'L1', 'Gaming'],  'strong': ['Gemini','Virgo'],   'weak': ['Sagittarius','Pisces']},
    'Ketu':    {'sectors': ['Infra', 'DeFi'],          'strong': ['Scorpio'],          'weak': ['Taurus']},
}

MOON_PHASE_RULES = {
    'New Moon':        {'bias':'Neutral',  'risk':'High',   'note':'New cycle. Accumulation phase. Watch for breakouts.'},
    'Waxing Crescent': {'bias':'Bullish',  'risk':'Medium', 'note':'Building momentum. Altcoin season energy.'},
    'First Quarter':   {'bias':'Bullish',  'risk':'Medium', 'note':'Strong momentum. Trend entries favored.'},
    'Waxing Gibbous':  {'bias':'Bullish',  'risk':'Low',    'note':'Peak energy. Parabolic moves possible.'},
    'Full Moon':       {'bias':'Volatile', 'risk':'High',   'note':'Maximum speculation. Pump and dump risk. Tighten SL.'},
    'Waning Gibbous':  {'bias':'Neutral',  'risk':'Medium', 'note':'Distribution phase. Take profits.'},
    'Last Quarter':    {'bias':'Bearish',  'risk':'Medium', 'note':'Declining energy. Reduce exposure.'},
    'Waning Crescent': {'bias':'Bearish',  'risk':'High',   'note':'Capitulation risk. Avoid longs.'},
}

EXALTATION   = {'Sun':'Aries','Moon':'Taurus','Mars':'Capricorn','Mercury':'Virgo','Jupiter':'Cancer','Venus':'Pisces','Saturn':'Libra'}
DEBILITATION = {'Sun':'Libra','Moon':'Scorpio','Mars':'Cancer','Mercury':'Pisces','Jupiter':'Capricorn','Venus':'Virgo','Saturn':'Aries'}

def get_julian_day(dt=None):
    dt = dt or datetime.now(timezone.utc)
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60 + dt.second/3600)

def get_ayanamsa(jd):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.get_ayanamsa_ut(jd)

def calc_planet(jd, pid, ayanamsa):
    xx, _ = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
    lon = (xx[0] - ayanamsa) % 360
    return lon, xx[3], xx[3] < 0

def longitude_to_rashi(lon):
    idx = int(lon / 30)
    return RASHIS[idx % 12], round(lon % 30, 4)

def longitude_to_nakshatra(lon):
    span = 360 / 27
    idx  = int(lon / span)
    pada = int((lon % span) / (span / 4)) + 1
    return NAKSHATRAS[idx % 27], pada, NAKSHATRA_LORDS[idx % 27]

def get_moon_phase(moon_lon, sun_lon):
    angle = (moon_lon - sun_lon) % 360
    if angle < 13.5:    return 'New Moon', '🌑', angle
    elif angle < 90:    return 'Waxing Crescent', '🌒', angle
    elif angle < 135:   return 'First Quarter', '🌓', angle
    elif angle < 180:   return 'Waxing Gibbous', '🌔', angle
    elif angle < 193.5: return 'Full Moon', '🌕', angle
    elif angle < 270:   return 'Waning Gibbous', '🌖', angle
    elif angle < 315:   return 'Last Quarter', '🌗', angle
    elif angle < 346.5: return 'Waning Crescent', '🌘', angle
    return 'New Moon', '🌑', angle

def check_conjunctions(positions):
    conj = []
    names = list(positions.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            p1, p2 = names[i], names[j]
            diff = abs(positions[p1]['longitude'] - positions[p2]['longitude'])
            if diff > 180: diff = 360 - diff
            if diff <= 8:
                conj.append({'planets': [p1, p2], 'orb': round(diff, 2)})
    return conj

def check_aspects(positions):
    aspects = []
    aspect_types = {180:'Opposition', 120:'Trine', 90:'Square', 60:'Sextile'}
    names = list(positions.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            p1, p2 = names[i], names[j]
            diff = abs(positions[p1]['longitude'] - positions[p2]['longitude'])
            if diff > 180: diff = 360 - diff
            for angle, name in aspect_types.items():
                if abs(diff - angle) <= 8:
                    aspects.append({'planets': [p1, p2], 'aspect': name, 'orb': round(abs(diff - angle), 2)})
    return aspects

def calculate_crypto_astro_score(positions, moon_phase, retrograde_planets):
    score = 50
    moon_rule = MOON_PHASE_RULES.get(moon_phase, {})
    if moon_rule.get('bias') == 'Bullish': score += 10
    elif moon_rule.get('bias') == 'Bearish': score -= 8
    elif moon_rule.get('bias') == 'Volatile': score -= 5
    score -= len([p for p in retrograde_planets if p in ['Mercury','Mars','Jupiter','Venus','Saturn']]) * 5
    jupiter_rashi = positions.get('Jupiter', {}).get('rashi', '')
    if jupiter_rashi in ['Sagittarius','Pisces','Cancer']: score += 10
    mars_rashi = positions.get('Mars', {}).get('rashi', '')
    if mars_rashi in ['Aries','Scorpio','Capricorn']: score += 8
    rahu_rashi = positions.get('Rahu', {}).get('rashi', '')
    if rahu_rashi in ['Gemini','Virgo']: score += 6  # Rahu in tech signs = crypto bullish
    return max(0, min(100, score))

def run_astro_engine(date=None):
    now = date or datetime.now(timezone.utc)
    jd  = get_julian_day(now)
    ayanamsa = get_ayanamsa(jd)
    positions = {}

    for name, pid in PLANETS.items():
        if name == 'Ketu':
            rahu_lon = positions['Rahu']['longitude']
            ketu_lon = (rahu_lon + 180) % 360
            rashi, deg = longitude_to_rashi(ketu_lon)
            nak, pada, nak_lord = longitude_to_nakshatra(ketu_lon)
            positions['Ketu'] = {'longitude': round(ketu_lon,4), 'rashi': rashi, 'rashi_lord': RASHI_LORDS[rashi], 'degrees_in_rashi': deg, 'nakshatra': nak, 'nakshatra_pada': pada, 'nakshatra_lord': nak_lord, 'retrograde': True, 'speed': None}
            continue
        lon, speed, retro = calc_planet(jd, pid, ayanamsa)
        rashi, deg = longitude_to_rashi(lon)
        nak, pada, nak_lord = longitude_to_nakshatra(lon)
        positions[name] = {'longitude': round(lon,4), 'rashi': rashi, 'rashi_lord': RASHI_LORDS[rashi], 'degrees_in_rashi': round(deg,4), 'nakshatra': nak, 'nakshatra_pada': pada, 'nakshatra_lord': nak_lord, 'retrograde': retro, 'speed': round(speed,6)}

    moon_phase, moon_emoji, moon_angle = get_moon_phase(positions['Moon']['longitude'], positions['Sun']['longitude'])
    weekday   = now.weekday()
    day_ruler = DAY_RULERS[weekday]
    retrograde = [n for n, d in positions.items() if d.get('retrograde')]
    conjunctions = check_conjunctions(positions)
    aspects      = check_aspects(positions)
    astro_score  = calculate_crypto_astro_score(positions, moon_phase, retrograde)

    # Check upcoming transitions
    transitions = []
    future_jd   = jd + 3
    future_ayanamsa = get_ayanamsa(future_jd)
    for name, pid in {'Sun':swe.SUN,'Moon':swe.MOON,'Mars':swe.MARS,'Mercury':swe.MERCURY,'Jupiter':swe.JUPITER,'Venus':swe.VENUS,'Saturn':swe.SATURN}.items():
        future_lon, _, _ = calc_planet(future_jd, pid, future_ayanamsa)
        future_rashi, _ = longitude_to_rashi(future_lon)
        if future_rashi != positions[name]['rashi']:
            transitions.append({'planet': name, 'from': positions[name]['rashi'], 'to': future_rashi, 'within_days': 3})

    output = {
        'date': now.strftime('%Y-%m-%d'),
        'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'day_ruler': day_ruler,
        'moon_phase': moon_phase,
        'moon_phase_emoji': moon_emoji,
        'moon_phase_angle': round(moon_angle, 2),
        'ayanamsa_lahiri': round(ayanamsa, 6),
        'planets': positions,
        'retrograde_planets': retrograde,
        'conjunctions': conjunctions,
        'aspects': aspects,
        'graha_yuddha': [],
        'upcoming_transitions': transitions,
        'astro_score': astro_score,
        'crypto_planet_map': CRYPTO_PLANET_SECTOR_MAP,
        'moon_rule': MOON_PHASE_RULES.get(moon_phase, {}),
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ASTRO_OUT, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"✅ Crypto Astro Engine complete")
    print(f"   Moon: {moon_emoji} {moon_phase} | Day: {day_ruler} | Score: {astro_score}")
    print(f"   Retrograde: {', '.join(retrograde) or 'None'}")
    return output

if __name__ == '__main__':
    run_astro_engine()
