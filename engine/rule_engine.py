"""
COSMO - Rule Engine
Layer 3: YOUR intellectual property.
Maps planetary conditions → sector bias → stock confidence.
This is the core brain that connects the sky to the market.
"""

# ── Planetary Sector Rulebook ─────────────────────────────────────────────
"""
Each planet governs certain sectors.
Strong planet (own sign, exalted, direct) = bullish bias for its sectors.
Weak planet (debilitated, retrograde, combust) = bearish bias.
"""

PLANET_SECTOR_MAP = {
    'Sun': {
        'sectors': ['Energy', 'Infra', 'Consumer'],
        'strong_signs': ['Leo', 'Aries'],        # Own + Exalted
        'weak_signs':   ['Libra', 'Aquarius'],   # Debilitated + Enemy
    },
    'Moon': {
        'sectors': ['FMCG', 'Consumer', 'Finance'],
        'strong_signs': ['Cancer', 'Taurus'],
        'weak_signs':   ['Scorpio', 'Capricorn'],
    },
    'Mars': {
        'sectors': ['Metals', 'Energy', 'Infra', 'Auto'],
        'strong_signs': ['Aries', 'Scorpio', 'Capricorn'],
        'weak_signs':   ['Cancer', 'Taurus'],
    },
    'Mercury': {
        'sectors': ['IT', 'Finance', 'Consumer'],
        'strong_signs': ['Gemini', 'Virgo'],
        'weak_signs':   ['Pisces', 'Sagittarius'],
    },
    'Jupiter': {
        'sectors': ['Banking', 'Finance', 'Pharma', 'FMCG'],
        'strong_signs': ['Sagittarius', 'Pisces', 'Cancer'],
        'weak_signs':   ['Capricorn', 'Gemini'],
    },
    'Venus': {
        'sectors': ['Consumer', 'FMCG', 'Auto', 'Finance'],
        'strong_signs': ['Taurus', 'Libra', 'Pisces'],
        'weak_signs':   ['Aries', 'Scorpio', 'Virgo'],
    },
    'Saturn': {
        'sectors': ['Metals', 'Infra', 'Energy', 'IT'],
        'strong_signs': ['Capricorn', 'Aquarius', 'Libra'],
        'weak_signs':   ['Aries', 'Cancer', 'Leo'],
    },
    'Rahu': {
        'sectors': ['IT', 'Pharma', 'Finance'],
        'strong_signs': ['Gemini', 'Virgo', 'Taurus'],
        'weak_signs':   ['Sagittarius', 'Pisces'],
    },
    'Ketu': {
        'sectors': ['Pharma', 'Metals', 'Energy'],
        'strong_signs': ['Scorpio', 'Sagittarius'],
        'weak_signs':   ['Taurus', 'Gemini'],
    },
}

# ── Moon Phase Rules ───────────────────────────────────────────────────────
MOON_PHASE_RULES = {
    'New Moon':        {'bias': 'Neutral',  'risk': 'High',   'note': 'New cycle beginning. Avoid fresh positions.'},
    'Waxing Crescent': {'bias': 'Bullish',  'risk': 'Medium', 'note': 'Energy building. Good for momentum entries.'},
    'First Quarter':   {'bias': 'Bullish',  'risk': 'Medium', 'note': 'Strong momentum phase. Trend trades favored.'},
    'Waxing Gibbous':  {'bias': 'Bullish',  'risk': 'Low',    'note': 'Peak energy building. Strong sector leaders perform.'},
    'Full Moon':       {'bias': 'Volatile', 'risk': 'High',   'note': 'Maximum energy. Reversals possible. Tighten SL.'},
    'Waning Gibbous':  {'bias': 'Neutral',  'risk': 'Medium', 'note': 'Consolidation phase. Selective entries only.'},
    'Last Quarter':    {'bias': 'Bearish',  'risk': 'Medium', 'note': 'Declining energy. Favor defensives.'},
    'Waning Crescent': {'bias': 'Bearish',  'risk': 'High',   'note': 'Weak phase. Avoid aggressive longs.'},
}

# ── Day Ruler Rules ────────────────────────────────────────────────────────
DAY_RULER_RULES = {
    'Sun':     {'favored': ['Energy', 'Infra'],          'avoid': ['IT', 'Finance']},
    'Moon':    {'favored': ['FMCG', 'Consumer'],         'avoid': ['Metals', 'Energy']},
    'Mars':    {'favored': ['Metals', 'Auto', 'Infra'],  'avoid': ['Finance', 'Pharma']},
    'Mercury': {'favored': ['IT', 'Finance'],             'avoid': ['Metals', 'Energy']},
    'Jupiter': {'favored': ['Banking', 'Finance', 'Pharma'], 'avoid': ['Metals']},
    'Venus':   {'favored': ['Consumer', 'FMCG', 'Auto'], 'avoid': ['Metals', 'Infra']},
    'Saturn':  {'favored': ['Metals', 'IT', 'Infra'],    'avoid': ['Consumer', 'FMCG']},
}

# ── Retrograde Rules ───────────────────────────────────────────────────────
RETROGRADE_RULES = {
    'Mercury': {
        'affected_sectors': ['IT', 'Finance', 'Consumer'],
        'bias': 'Bearish',
        'note': 'Mercury Rx: IT and communication stocks under pressure. Avoid new entries in IT.'
    },
    'Venus': {
        'affected_sectors': ['Consumer', 'FMCG', 'Auto'],
        'bias': 'Bearish',
        'note': 'Venus Rx: Consumer discretionary and luxury sectors weak.'
    },
    'Mars': {
        'affected_sectors': ['Metals', 'Auto', 'Energy'],
        'bias': 'Bearish',
        'note': 'Mars Rx: Energy and metals sectors facing headwinds.'
    },
    'Jupiter': {
        'affected_sectors': ['Banking', 'Finance'],
        'bias': 'Cautious',
        'note': 'Jupiter Rx: Financial sector expansion slows. Defensive positioning.'
    },
    'Saturn': {
        'affected_sectors': ['Infra', 'Metals'],
        'bias': 'Cautious',
        'note': 'Saturn Rx: Infrastructure and capital goods sector review.'
    },
}

# ── Aspect Rules ───────────────────────────────────────────────────────────
ASPECT_RULES = {
    ('Jupiter', 'Sun',  'Trine'):      {'bias': 'Bullish', 'sectors': ['Energy', 'Finance'], 'strength': 10},
    ('Jupiter', 'Mars', 'Trine'):      {'bias': 'Bullish', 'sectors': ['Metals', 'Auto'],    'strength': 8},
    ('Jupiter', 'Venus','Trine'):      {'bias': 'Bullish', 'sectors': ['Consumer', 'FMCG'],  'strength': 8},
    ('Saturn',  'Mars', 'Square'):     {'bias': 'Bearish', 'sectors': ['Metals', 'Infra'],   'strength': -8},
    ('Saturn',  'Sun',  'Opposition'): {'bias': 'Bearish', 'sectors': ['Energy', 'Infra'],   'strength': -7},
    ('Mars',    'Rahu', 'Conjunction'):{'bias': 'Volatile','sectors': ['All'],               'strength': -5},
}

# ── Conjunction Rules ──────────────────────────────────────────────────────
CONJUNCTION_RULES = {
    ('Jupiter', 'Venus'): {'bias': 'Bullish', 'sectors': ['Finance', 'Consumer', 'FMCG'], 'note': 'Wealth yoga — strong for finance and consumption.'},
    ('Jupiter', 'Mercury'):{'bias': 'Bullish', 'sectors': ['IT', 'Finance'],               'note': 'Intelligence yoga — IT and banking favored.'},
    ('Saturn', 'Mars'):   {'bias': 'Bearish', 'sectors': ['Metals', 'Infra', 'Auto'],     'note': 'Conflict energy — metals and infrastructure under stress.'},
    ('Sun', 'Mercury'):   {'bias': 'Neutral', 'sectors': ['IT'],                           'note': 'Combust Mercury — IT stocks volatile.'},
    ('Rahu', 'Jupiter'):  {'bias': 'Cautious','sectors': ['Finance', 'Banking'],           'note': 'Rahu amplifies — financial sector speculative.'},
    ('Ketu', 'Mars'):     {'bias': 'Bearish', 'sectors': ['Metals', 'Energy'],             'note': 'Ketu-Mars — sudden reversals in metals/energy.'},
}

# ── Exaltation / Debilitation Table ───────────────────────────────────────
EXALTATION = {
    'Sun': 'Aries', 'Moon': 'Taurus', 'Mars': 'Capricorn',
    'Mercury': 'Virgo', 'Jupiter': 'Cancer', 'Venus': 'Pisces', 'Saturn': 'Libra'
}
DEBILITATION = {
    'Sun': 'Libra', 'Moon': 'Scorpio', 'Mars': 'Cancer',
    'Mercury': 'Pisces', 'Jupiter': 'Capricorn', 'Venus': 'Virgo', 'Saturn': 'Aries'
}

# ── Planet Strength Calculator ────────────────────────────────────────────

def get_planet_strength(planet_name, rashi, is_retrograde):
    """
    Returns: 'Strong', 'Neutral', 'Weak'
    Based on: own sign, exaltation, debilitation, retrograde
    """
    rule = PLANET_SECTOR_MAP.get(planet_name, {})
    strong_signs = rule.get('strong_signs', [])
    weak_signs   = rule.get('weak_signs', [])

    if rashi == EXALTATION.get(planet_name):
        strength = 'Exalted'
    elif rashi == DEBILITATION.get(planet_name):
        strength = 'Debilitated'
    elif rashi in strong_signs:
        strength = 'Strong'
    elif rashi in weak_signs:
        strength = 'Weak'
    else:
        strength = 'Neutral'

    # Retrograde modifies strength
    if is_retrograde and strength in ['Strong', 'Exalted']:
        strength = 'Retrograde-Strong'   # Mixed — power internalized
    elif is_retrograde and strength in ['Neutral']:
        strength = 'Retrograde-Weak'

    return strength

# ── Sector Astro Bias ─────────────────────────────────────────────────────

def calculate_sector_astro_bias(astro_data):
    """
    For each sector, calculates astro bias score (-100 to +100)
    based on all planetary conditions.
    """
    planets    = astro_data['planets']
    retrograde = astro_data['retrograde_planets']
    moon_phase = astro_data['moon_phase']
    day_ruler  = astro_data['day_ruler']
    conjunctions = astro_data.get('conjunctions', [])
    aspects      = astro_data.get('aspects', [])

    # Initialize sector scores
    sector_bias = {sector: 0 for sector in PLANET_SECTOR_MAP['Sun']['sectors']}
    all_sectors = set()
    for p in PLANET_SECTOR_MAP.values():
        all_sectors.update(p['sectors'])
    sector_bias = {s: 0 for s in all_sectors}
    sector_notes = {s: [] for s in all_sectors}

    # ── 1. Planet strength → sector bias ─────────────────────────────────
    for planet_name, planet_data in planets.items():
        rule = PLANET_SECTOR_MAP.get(planet_name)
        if not rule:
            continue

        rashi       = planet_data['rashi']
        is_retro    = planet_data.get('retrograde', False)
        strength    = get_planet_strength(planet_name, rashi, is_retro)

        score_map = {
            'Exalted':          +20,
            'Strong':           +12,
            'Neutral':           0,
            'Weak':             -10,
            'Debilitated':      -18,
            'Retrograde-Strong': +5,
            'Retrograde-Weak':  -8,
        }
        score = score_map.get(strength, 0)

        for sector in rule['sectors']:
            if sector in sector_bias:
                sector_bias[sector] += score
                if score != 0:
                    sector_notes[sector].append(
                        f"{planet_name} {strength} in {rashi}"
                    )

    # ── 2. Retrograde penalties ───────────────────────────────────────────
    for planet_name in retrograde:
        retro_rule = RETROGRADE_RULES.get(planet_name)
        if retro_rule:
            for sector in retro_rule['affected_sectors']:
                if sector in sector_bias:
                    sector_bias[sector] -= 10
                    sector_notes[sector].append(retro_rule['note'])

    # ── 3. Day ruler boost ────────────────────────────────────────────────
    day_rule = DAY_RULER_RULES.get(day_ruler, {})
    for sector in day_rule.get('favored', []):
        if sector in sector_bias:
            sector_bias[sector] += 8
            sector_notes[sector].append(f"Day of {day_ruler} favors {sector}")
    for sector in day_rule.get('avoid', []):
        if sector in sector_bias:
            sector_bias[sector] -= 8

    # ── 4. Moon phase adjustments ─────────────────────────────────────────
    moon_rule = MOON_PHASE_RULES.get(moon_phase, {})
    moon_bias = moon_rule.get('bias', 'Neutral')
    if moon_bias == 'Bullish':
        for s in sector_bias:
            sector_bias[s] += 5
    elif moon_bias == 'Bearish':
        for s in sector_bias:
            sector_bias[s] -= 5
    elif moon_bias == 'Volatile':
        for s in sector_bias:
            sector_bias[s] = sector_bias[s] * 0.8  # Compress scores

    # ── 5. Aspect bonuses/penalties ───────────────────────────────────────
    for aspect in aspects:
        p_pair = tuple(sorted(aspect['planets']))
        asp_type = aspect['aspect']
        for key, rule in ASPECT_RULES.items():
            if set(key[:2]) == set(p_pair) and key[2] == asp_type:
                for sector in rule['sectors']:
                    if sector == 'All':
                        for s in sector_bias:
                            sector_bias[s] += rule['strength']
                    elif sector in sector_bias:
                        sector_bias[sector] += rule['strength']

    # ── 6. Conjunction bonuses ────────────────────────────────────────────
    for conj in conjunctions:
        p_pair = tuple(sorted(conj['planets']))
        for key, rule in CONJUNCTION_RULES.items():
            if set(key) == set(p_pair):
                for sector in rule['sectors']:
                    if sector in sector_bias:
                        sector_bias[sector] += 10 if rule['bias'] == 'Bullish' else -8
                        sector_notes[sector].append(rule['note'])

    # ── Normalize to -100 to +100 ─────────────────────────────────────────
    for s in sector_bias:
        sector_bias[s] = max(-100, min(100, round(sector_bias[s], 1)))

    return sector_bias, sector_notes, moon_rule

# ── Stock Level Rules ─────────────────────────────────────────────────────

def apply_stock_rules(stock, sector_astro_bias, astro_data):
    """
    Applies rules at individual stock level.
    Returns rule flags and confidence modifiers.
    """
    flags = []
    modifier = 0

    sector = stock.get('sector', '')
    astro_bias = sector_astro_bias.get(sector, 0)

    # Rule 1: Strong astro + volume breakout = high confidence
    if astro_bias > 20 and stock['volume_signal'] == 'Volume Breakout':
        flags.append('ASTRO_VOLUME_BREAKOUT')
        modifier += 20

    # Rule 2: Strong astro + strong uptrend = trend continuation
    if astro_bias > 15 and stock['trend'] == 'Strong Uptrend':
        flags.append('ASTRO_TREND_ALIGNED')
        modifier += 15

    # Rule 3: RSI sweet spot (50-65) + positive astro
    if 50 <= stock['rsi'] <= 65 and astro_bias > 10:
        flags.append('RSI_ASTRO_SWEET_SPOT')
        modifier += 10

    # Rule 4: Negative astro overrides technical strength
    if astro_bias < -20 and stock['technical_score'] > 60:
        flags.append('ASTRO_OVERRIDES_TECHNICAL')
        modifier -= 20

    # Rule 5: Mercury retrograde + IT stock = reduce confidence
    if 'Mercury' in astro_data['retrograde_planets'] and sector == 'IT':
        flags.append('MERCURY_RX_IT_CAUTION')
        modifier -= 15

    # Rule 6: Near 52-week high + bullish astro = momentum continuation
    if stock['pct_from_52w_high'] > -3 and astro_bias > 15:
        flags.append('NEAR_52W_HIGH_BULLISH')
        modifier += 10

    # Rule 7: Oversold RSI + waxing moon = potential reversal
    if stock['rsi'] < 35 and astro_data['moon_phase'] in ['Waxing Crescent', 'First Quarter']:
        flags.append('OVERSOLD_WAXING_REVERSAL')
        modifier += 8

    # Rule 8: Full moon + high volatility = caution
    if astro_data['moon_phase'] == 'Full Moon' and abs(stock['change_pct']) > 2:
        flags.append('FULL_MOON_VOLATILE')
        modifier -= 10

    return flags, modifier

# ── Main Rule Engine ──────────────────────────────────────────────────────

def run_rule_engine(astro_data, market_data):
    """
    Master function. Applies all rules.
    Returns enriched data with astro bias per sector and stock.
    """
    print("⚖️  Rule Engine starting...")

    # ── Sector astro bias ─────────────────────────────────────────────────
    sector_astro_bias, sector_notes, moon_rule = calculate_sector_astro_bias(astro_data)

    # ── Label sector bias ─────────────────────────────────────────────────
    def bias_label(score):
        if score >= 30:   return 'Strong Bullish'
        elif score >= 10: return 'Bullish'
        elif score >= -10: return 'Neutral'
        elif score >= -30: return 'Bearish'
        else:              return 'Strong Bearish'

    sector_bias_labeled = {}
    for sector, score in sector_astro_bias.items():
        sector_bias_labeled[sector] = {
            'astro_score': score,
            'bias': bias_label(score),
            'notes': sector_notes[sector][:3]  # Top 3 notes
        }

    # ── Apply stock-level rules ───────────────────────────────────────────
    enriched_stocks = []
    for stock in market_data.get('all_stocks', []):
        flags, modifier = apply_stock_rules(stock, sector_astro_bias, astro_data)
        stock['rule_flags']      = flags
        stock['rule_modifier']   = modifier
        stock['sector_astro_bias'] = sector_astro_bias.get(stock.get('sector', ''), 0)
        enriched_stocks.append(stock)

    # ── Moon phase intelligence ───────────────────────────────────────────
    moon_intelligence = {
        'phase': astro_data['moon_phase'],
        'bias': moon_rule.get('bias', 'Neutral'),
        'risk_level': moon_rule.get('risk', 'Medium'),
        'note': moon_rule.get('note', ''),
    }

    # ── Day ruler intelligence ────────────────────────────────────────────
    day_ruler = astro_data['day_ruler']
    day_rule = DAY_RULER_RULES.get(day_ruler, {})
    day_intelligence = {
        'ruler': day_ruler,
        'favored_sectors': day_rule.get('favored', []),
        'avoid_sectors': day_rule.get('avoid', []),
    }

    return {
        'sector_astro_bias': sector_bias_labeled,
        'enriched_stocks': enriched_stocks,
        'moon_intelligence': moon_intelligence,
        'day_intelligence': day_intelligence,
    }
