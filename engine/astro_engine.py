"""
COSMO - Astro Engine
Layer 1: Reads all 9 Navagraha positions for today
Outputs: rashi, nakshatra, retrograde, conjunctions, aspects, moon phase, day ruler
"""

import swisseph as swe
import json
from datetime import datetime, timezone
import os

# ── Path to ephemeris files (in repo: /ephe/) ──────────────────────────────
EPHE_PATH = os.path.join(os.path.dirname(__file__), '..', 'ephe')
swe.set_ephe_path(EPHE_PATH)

# ── Planet IDs ─────────────────────────────────────────────────────────────
PLANETS = {
    'Sun':     swe.SUN,
    'Moon':    swe.MOON,
    'Mars':    swe.MARS,
    'Mercury': swe.MERCURY,
    'Jupiter': swe.JUPITER,
    'Venus':   swe.VENUS,
    'Saturn':  swe.SATURN,
    'Rahu':    swe.MEAN_NODE,       # North Node
    'Ketu':    None,                # Calculated as Rahu + 180
}

# ── Rashi (Zodiac Signs) ───────────────────────────────────────────────────
RASHIS = [
    'Aries', 'Taurus', 'Gemini', 'Cancer',
    'Leo', 'Virgo', 'Libra', 'Scorpio',
    'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
]

RASHI_LORDS = {
    'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury',
    'Cancer': 'Moon', 'Leo': 'Sun', 'Virgo': 'Mercury',
    'Libra': 'Venus', 'Scorpio': 'Mars', 'Sagittarius': 'Jupiter',
    'Capricorn': 'Saturn', 'Aquarius': 'Saturn', 'Pisces': 'Jupiter'
}

# ── Nakshatras (27) ────────────────────────────────────────────────────────
NAKSHATRAS = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
    'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
    'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
    'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishtha',
    'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
]

NAKSHATRA_LORDS = [
    'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu',
    'Jupiter', 'Saturn', 'Mercury', 'Ketu', 'Venus', 'Sun',
    'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury',
    'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu',
    'Jupiter', 'Saturn', 'Mercury'
]

# ── Day Rulers (Weekday → Planet) ──────────────────────────────────────────
DAY_RULERS = {
    0: 'Moon',     # Monday
    1: 'Mars',     # Tuesday
    2: 'Mercury',  # Wednesday
    3: 'Jupiter',  # Thursday
    4: 'Venus',    # Friday
    5: 'Saturn',   # Saturday
    6: 'Sun',      # Sunday
}

# ── Moon Phase Names ───────────────────────────────────────────────────────
def get_moon_phase_name(angle):
    """Returns moon phase name based on Sun-Moon angular difference."""
    if angle < 0:
        angle += 360
    if angle < 13.5:
        return 'New Moon'
    elif angle < 90:
        return 'Waxing Crescent'
    elif angle < 135:
        return 'First Quarter'
    elif angle < 180:
        return 'Waxing Gibbous'
    elif angle < 193.5:
        return 'Full Moon'
    elif angle < 270:
        return 'Waning Gibbous'
    elif angle < 315:
        return 'Last Quarter'
    elif angle < 346.5:
        return 'Waning Crescent'
    else:
        return 'New Moon'

def get_moon_phase_emoji(phase_name):
    emojis = {
        'New Moon': '🌑',
        'Waxing Crescent': '🌒',
        'First Quarter': '🌓',
        'Waxing Gibbous': '🌔',
        'Full Moon': '🌕',
        'Waning Gibbous': '🌖',
        'Last Quarter': '🌗',
        'Waning Crescent': '🌘',
    }
    return emojis.get(phase_name, '🌑')

# ── Longitude → Rashi + Degrees ───────────────────────────────────────────
def longitude_to_rashi(lon):
    """Converts ecliptic longitude to Vedic rashi using Lahiri ayanamsa."""
    rashi_index = int(lon / 30)
    degree_in_rashi = lon % 30
    rashi = RASHIS[rashi_index % 12]
    return rashi, round(degree_in_rashi, 4)

# ── Longitude → Nakshatra ─────────────────────────────────────────────────
def longitude_to_nakshatra(lon):
    """Each nakshatra spans 13.333... degrees (360 / 27)."""
    nakshatra_span = 360 / 27
    nakshatra_index = int(lon / nakshatra_span)
    pada = int((lon % nakshatra_span) / (nakshatra_span / 4)) + 1
    nakshatra = NAKSHATRAS[nakshatra_index % 27]
    lord = NAKSHATRA_LORDS[nakshatra_index % 27]
    return nakshatra, pada, lord

# ── Get Julian Day for today (IST → UTC) ──────────────────────────────────
def get_julian_day(dt=None):
    """Returns Julian Day for given datetime (UTC). Defaults to now."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    jd = swe.julday(dt.year, dt.month, dt.day,
                    dt.hour + dt.minute / 60.0 + dt.second / 3600.0)
    return jd

# ── Calculate Ayanamsa (Lahiri) ───────────────────────────────────────────
def get_ayanamsa(jd):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.get_ayanamsa_ut(jd)

# ── Calculate Planet Position ─────────────────────────────────────────────
def calc_planet(jd, planet_id, ayanamsa):
    """Returns sidereal longitude, speed, retrograde status."""
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    xx, _ = swe.calc_ut(jd, planet_id, flags)
    tropical_lon = xx[0]
    speed = xx[3]
    sidereal_lon = (tropical_lon - ayanamsa) % 360
    is_retrograde = speed < 0
    return sidereal_lon, speed, is_retrograde

# ── Check Conjunction (within 8 degrees) ─────────────────────────────────
def check_conjunctions(positions):
    """Returns list of planet pairs that are conjunct (within 8°)."""
    conjunctions = []
    planet_names = list(positions.keys())
    for i in range(len(planet_names)):
        for j in range(i + 1, len(planet_names)):
            p1 = planet_names[i]
            p2 = planet_names[j]
            lon1 = positions[p1]['longitude']
            lon2 = positions[p2]['longitude']
            diff = abs(lon1 - lon2)
            if diff > 180:
                diff = 360 - diff
            if diff <= 8:
                conjunctions.append({
                    'planets': [p1, p2],
                    'orb': round(diff, 2)
                })
    return conjunctions

# ── Check Aspects ─────────────────────────────────────────────────────────
def check_aspects(positions):
    """
    Checks key aspects:
    Opposition (180°), Trine (120°), Square (90°), Sextile (60°)
    Orb: 8 degrees
    """
    aspects = []
    orb = 8
    aspect_types = {
        180: 'Opposition',
        120: 'Trine',
        90:  'Square',
        60:  'Sextile',
    }
    planet_names = list(positions.keys())
    for i in range(len(planet_names)):
        for j in range(i + 1, len(planet_names)):
            p1 = planet_names[i]
            p2 = planet_names[j]
            lon1 = positions[p1]['longitude']
            lon2 = positions[p2]['longitude']
            diff = abs(lon1 - lon2)
            if diff > 180:
                diff = 360 - diff
            for angle, aspect_name in aspect_types.items():
                if abs(diff - angle) <= orb:
                    aspects.append({
                        'planets': [p1, p2],
                        'aspect': aspect_name,
                        'orb': round(abs(diff - angle), 2)
                    })
    return aspects

# ── Planetary War (Graha Yuddha) ──────────────────────────────────────────
def check_graha_yuddha(positions):
    """Planets within 1 degree = Graha Yuddha (planetary war)."""
    wars = []
    visible_planets = ['Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn']
    for i in range(len(visible_planets)):
        for j in range(i + 1, len(visible_planets)):
            p1 = visible_planets[i]
            p2 = visible_planets[j]
            if p1 in positions and p2 in positions:
                lon1 = positions[p1]['longitude']
                lon2 = positions[p2]['longitude']
                diff = abs(lon1 - lon2)
                if diff > 180:
                    diff = 360 - diff
                if diff <= 1:
                    wars.append({'planets': [p1, p2], 'orb': round(diff, 4)})
    return wars

# ── Planetary Transitions (within 3 days) ────────────────────────────────
def check_upcoming_transitions(jd, positions):
    """Detects if any planet will change rashi within next 3 days."""
    transitions = []
    check_planets = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
        'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
        'Venus': swe.VENUS, 'Saturn': swe.SATURN
    }
    ayanamsa_future = get_ayanamsa(jd + 3)
    for name, pid in check_planets.items():
        future_lon, _, _ = calc_planet(jd + 3, pid, ayanamsa_future)
        current_rashi = positions[name]['rashi']
        future_rashi, _ = longitude_to_rashi(future_lon)
        if future_rashi != current_rashi:
            transitions.append({
                'planet': name,
                'from': current_rashi,
                'to': future_rashi,
                'within_days': 3
            })
    return transitions

# ── Astro Score (0-100) ───────────────────────────────────────────────────
def calculate_astro_score(positions, conjunctions, aspects, moon_phase):
    """
    Simple rule-based astro score.
    Higher = more harmonious sky conditions.
    """
    score = 50  # Base

    # Moon phase bonus
    if moon_phase in ['Waxing Gibbous', 'Full Moon', 'First Quarter']:
        score += 10
    elif moon_phase in ['New Moon', 'Waning Crescent']:
        score -= 5

    # Retrograde penalty
    retrograde_count = sum(1 for p in positions.values() if p.get('retrograde'))
    score -= retrograde_count * 5

    # Benefic aspects bonus (Trine, Sextile)
    for asp in aspects:
        if asp['aspect'] in ['Trine', 'Sextile']:
            score += 4
        elif asp['aspect'] in ['Opposition', 'Square']:
            score -= 3

    # Jupiter strong (own sign or exalted)
    jupiter_rashi = positions.get('Jupiter', {}).get('rashi', '')
    if jupiter_rashi in ['Sagittarius', 'Pisces', 'Cancer']:
        score += 8

    # Saturn strong
    saturn_rashi = positions.get('Saturn', {}).get('rashi', '')
    if saturn_rashi in ['Capricorn', 'Aquarius', 'Libra']:
        score += 5

    # Mars energy
    mars_rashi = positions.get('Mars', {}).get('rashi', '')
    if mars_rashi in ['Aries', 'Scorpio', 'Capricorn']:
        score += 5

    return max(0, min(100, score))

# ── Main Engine ───────────────────────────────────────────────────────────
def run_astro_engine(date=None):
    """
    Master function. Returns full astro data dict for today.
    Pass a datetime object for custom date, or None for today.
    """
    now_utc = date or datetime.now(timezone.utc)
    jd = get_julian_day(now_utc)
    ayanamsa = get_ayanamsa(jd)

    # ── Calculate all planet positions ────────────────────────────────────
    positions = {}

    for name, planet_id in PLANETS.items():
        if name == 'Ketu':
            # Ketu = Rahu + 180
            rahu_lon = positions['Rahu']['longitude']
            ketu_lon = (rahu_lon + 180) % 360
            rashi, deg = longitude_to_rashi(ketu_lon)
            nakshatra, pada, nak_lord = longitude_to_nakshatra(ketu_lon)
            positions['Ketu'] = {
                'longitude': round(ketu_lon, 4),
                'rashi': rashi,
                'rashi_lord': RASHI_LORDS[rashi],
                'degrees_in_rashi': deg,
                'nakshatra': nakshatra,
                'nakshatra_pada': pada,
                'nakshatra_lord': nak_lord,
                'retrograde': True,  # Ketu is always retrograde
                'speed': None
            }
            continue

        lon, speed, retro = calc_planet(jd, planet_id, ayanamsa)
        rashi, deg = longitude_to_rashi(lon)
        nakshatra, pada, nak_lord = longitude_to_nakshatra(lon)

        positions[name] = {
            'longitude': round(lon, 4),
            'rashi': rashi,
            'rashi_lord': RASHI_LORDS[rashi],
            'degrees_in_rashi': round(deg, 4),
            'nakshatra': nakshatra,
            'nakshatra_pada': pada,
            'nakshatra_lord': nak_lord,
            'retrograde': retro,
            'speed': round(speed, 6)
        }

    # ── Moon phase ────────────────────────────────────────────────────────
    sun_lon = positions['Sun']['longitude']
    moon_lon = positions['Moon']['longitude']
    moon_angle = (moon_lon - sun_lon) % 360
    moon_phase = get_moon_phase_name(moon_angle)
    moon_phase_emoji = get_moon_phase_emoji(moon_phase)
    moon_phase_angle = round(moon_angle, 2)

    # ── Day ruler ─────────────────────────────────────────────────────────
    # IST = UTC + 5:30
    ist_hour = now_utc.hour + 5.5
    ist_day = now_utc
    if ist_hour >= 24:
        from datetime import timedelta
        ist_day = now_utc + timedelta(days=1)
    weekday = ist_day.weekday()
    day_ruler = DAY_RULERS[weekday]

    # ── Conjunctions, Aspects, Wars ───────────────────────────────────────
    conjunctions = check_conjunctions(positions)
    aspects = check_aspects(positions)
    graha_yuddha = check_graha_yuddha(positions)
    transitions = check_upcoming_transitions(jd, positions)

    # ── Retrograde summary ────────────────────────────────────────────────
    retrograde_planets = [name for name, data in positions.items() if data.get('retrograde')]

    # ── Astro Score ───────────────────────────────────────────────────────
    astro_score = calculate_astro_score(positions, conjunctions, aspects, moon_phase)

    # ── Build output ──────────────────────────────────────────────────────
    output = {
        'date': now_utc.strftime('%Y-%m-%d'),
        'generated_at': now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'day_ruler': day_ruler,
        'moon_phase': moon_phase,
        'moon_phase_emoji': moon_phase_emoji,
        'moon_phase_angle': moon_phase_angle,
        'ayanamsa_lahiri': round(ayanamsa, 6),
        'planets': positions,
        'retrograde_planets': retrograde_planets,
        'conjunctions': conjunctions,
        'aspects': aspects,
        'graha_yuddha': graha_yuddha,
        'upcoming_transitions': transitions,
        'astro_score': astro_score
    }

    return output


# ── Run & Save ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    result = run_astro_engine()

    # Save to data/astro_data.json
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'astro_data.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"✅ Astro Engine complete → {output_path}")
    print(f"   Date       : {result['date']}")
    print(f"   Day Ruler  : {result['day_ruler']}")
    print(f"   Moon Phase : {result['moon_phase_emoji']} {result['moon_phase']}")
    print(f"   Retrograde : {', '.join(result['retrograde_planets']) or 'None'}")
    print(f"   Astro Score: {result['astro_score']}/100")
    print(f"   Conjunctions: {len(result['conjunctions'])}")
    print(f"   Aspects     : {len(result['aspects'])}")
