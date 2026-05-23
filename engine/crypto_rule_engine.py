"""
COSMO CRYPTO - Rule Engine
Maps planetary conditions to crypto sector bias.
Crypto-specific rules: funding rates, moon phase mania, Rahu-Meme correlation.
"""

CRYPTO_PLANET_SECTOR_MAP = {
    'Sun':     {'sectors': ['L1', 'Infra'],            'strong': ['Leo','Aries'],      'weak': ['Libra','Aquarius']},
    'Moon':    {'sectors': ['Meme', 'Gaming'],          'strong': ['Cancer','Taurus'],  'weak': ['Scorpio','Capricorn']},
    'Mars':    {'sectors': ['L1', 'Gaming', 'Meme'],    'strong': ['Aries','Scorpio','Capricorn'], 'weak': ['Cancer','Taurus']},
    'Mercury': {'sectors': ['DeFi', 'Infra', 'L2'],    'strong': ['Gemini','Virgo'],   'weak': ['Pisces','Sagittarius']},
    'Jupiter': {'sectors': ['L1', 'DeFi', 'L2'],       'strong': ['Sagittarius','Pisces','Cancer'], 'weak': ['Capricorn','Gemini']},
    'Venus':   {'sectors': ['Meme', 'Gaming', 'DeFi'], 'strong': ['Taurus','Libra','Pisces'], 'weak': ['Aries','Scorpio','Virgo']},
    'Saturn':  {'sectors': ['Infra', 'L2', 'DeFi'],    'strong': ['Capricorn','Aquarius','Libra'], 'weak': ['Aries','Cancer','Leo']},
    'Rahu':    {'sectors': ['Meme', 'L1', 'Gaming'],   'strong': ['Gemini','Virgo'],   'weak': ['Sagittarius','Pisces']},
    'Ketu':    {'sectors': ['Infra', 'DeFi'],           'strong': ['Scorpio'],          'weak': ['Taurus']},
}

EXALTATION   = {'Sun':'Aries','Moon':'Taurus','Mars':'Capricorn','Mercury':'Virgo','Jupiter':'Cancer','Venus':'Pisces','Saturn':'Libra'}
DEBILITATION = {'Sun':'Libra','Moon':'Scorpio','Mars':'Cancer','Mercury':'Pisces','Jupiter':'Capricorn','Venus':'Virgo','Saturn':'Aries'}

MOON_PHASE_RULES = {
    'New Moon':        {'bias':'Neutral',  'risk':'High',   'note':'New cycle. Accumulation phase.'},
    'Waxing Crescent': {'bias':'Bullish',  'risk':'Medium', 'note':'Building momentum. Altcoin season energy.'},
    'First Quarter':   {'bias':'Bullish',  'risk':'Medium', 'note':'Strong momentum. Trend entries favored.'},
    'Waxing Gibbous':  {'bias':'Bullish',  'risk':'Low',    'note':'Peak energy. Parabolic moves possible.'},
    'Full Moon':       {'bias':'Volatile', 'risk':'High',   'note':'Maximum speculation. Pump and dump risk.'},
    'Waning Gibbous':  {'bias':'Neutral',  'risk':'Medium', 'note':'Distribution phase. Take profits.'},
    'Last Quarter':    {'bias':'Bearish',  'risk':'Medium', 'note':'Declining energy. Reduce exposure.'},
    'Waning Crescent': {'bias':'Bearish',  'risk':'High',   'note':'Capitulation risk. Avoid longs.'},
}

DAY_RULER_RULES = {
    'Sun':     {'favored': ['L1', 'Infra'],    'avoid': ['Meme', 'Gaming']},
    'Moon':    {'favored': ['Meme', 'Gaming'], 'avoid': ['Infra', 'DeFi']},
    'Mars':    {'favored': ['L1', 'Meme'],     'avoid': ['DeFi', 'L2']},
    'Mercury': {'favored': ['DeFi', 'L2'],     'avoid': ['Meme', 'Gaming']},
    'Jupiter': {'favored': ['L1', 'DeFi'],     'avoid': ['Meme']},
    'Venus':   {'favored': ['Meme', 'Gaming'], 'avoid': ['Infra']},
    'Saturn':  {'favored': ['Infra', 'L2'],    'avoid': ['Meme', 'Gaming']},
}

RETROGRADE_RULES = {
    'Mercury': {'sectors': ['DeFi', 'L2', 'Infra'], 'bias': 'Bearish', 'note': 'Mercury Rx — DeFi protocols and Layer 2 under pressure'},
    'Venus':   {'sectors': ['Meme', 'Gaming'],       'bias': 'Bearish', 'note': 'Venus Rx — Meme and gaming sentiment weak'},
    'Mars':    {'sectors': ['L1', 'Meme'],           'bias': 'Bearish', 'note': 'Mars Rx — L1 momentum stalls'},
    'Jupiter': {'sectors': ['L1', 'DeFi'],           'bias': 'Cautious','note': 'Jupiter Rx — expansion phase pauses'},
    'Saturn':  {'sectors': ['Infra', 'L2'],          'bias': 'Cautious','note': 'Saturn Rx — infrastructure projects delayed'},
}

def get_planet_strength(name, rashi, is_retro):
    rule = CRYPTO_PLANET_SECTOR_MAP.get(name, {})
    if rashi == EXALTATION.get(name):          strength = 'Exalted'
    elif rashi == DEBILITATION.get(name):      strength = 'Debilitated'
    elif rashi in rule.get('strong', []):      strength = 'Strong'
    elif rashi in rule.get('weak', []):        strength = 'Weak'
    else:                                       strength = 'Neutral'
    if is_retro and strength in ['Strong','Exalted']: strength = 'Retrograde-Strong'
    elif is_retro and strength == 'Neutral':          strength = 'Retrograde-Weak'
    return strength

def calculate_sector_astro_bias(astro_data):
    planets    = astro_data['planets']
    retrograde = astro_data['retrograde_planets']
    moon_phase = astro_data['moon_phase']
    day_ruler  = astro_data['day_ruler']
    conjunctions = astro_data.get('conjunctions', [])

    all_sectors = set()
    for p in CRYPTO_PLANET_SECTOR_MAP.values():
        all_sectors.update(p['sectors'])

    sector_bias  = {s: 0 for s in all_sectors}
    sector_notes = {s: [] for s in all_sectors}

    score_map = {'Exalted':20,'Strong':12,'Neutral':0,'Weak':-10,'Debilitated':-18,'Retrograde-Strong':5,'Retrograde-Weak':-8}

    for name, data in planets.items():
        rule = CRYPTO_PLANET_SECTOR_MAP.get(name)
        if not rule: continue
        strength = get_planet_strength(name, data['rashi'], data.get('retrograde', False))
        score = score_map.get(strength, 0)
        for sector in rule['sectors']:
            if sector in sector_bias:
                sector_bias[sector] += score
                if score != 0:
                    sector_notes[sector].append(f"{name} {strength} in {data['rashi']}")

    for name in retrograde:
        rule = RETROGRADE_RULES.get(name)
        if rule:
            for sector in rule['affected_sectors'] if 'affected_sectors' in rule else rule.get('sectors', []):
                if sector in sector_bias:
                    sector_bias[sector] -= 10
                    sector_notes[sector].append(rule['note'])

    moon_rule = MOON_PHASE_RULES.get(moon_phase, {})
    moon_bias = moon_rule.get('bias', 'Neutral')
    if moon_bias == 'Bullish':
        for s in sector_bias: sector_bias[s] += 5
    elif moon_bias == 'Bearish':
        for s in sector_bias: sector_bias[s] -= 5
    elif moon_bias == 'Volatile':
        for s in sector_bias: sector_bias[s] = sector_bias[s] * 0.8

    day_rule = DAY_RULER_RULES.get(day_ruler, {})
    for sector in day_rule.get('favored', []):
        if sector in sector_bias:
            sector_bias[sector] += 8
            sector_notes[sector].append(f"Day of {day_ruler} favors {sector}")
    for sector in day_rule.get('avoid', []):
        if sector in sector_bias:
            sector_bias[sector] -= 8

    for s in sector_bias:
        sector_bias[s] = max(-100, min(100, round(sector_bias[s], 1)))

    def bias_label(score):
        if score >= 30:    return 'Strong Bullish'
        elif score >= 10:  return 'Bullish'
        elif score >= -10: return 'Neutral'
        elif score >= -30: return 'Bearish'
        else:              return 'Strong Bearish'

    sector_bias_labeled = {
        s: {'astro_score': score, 'bias': bias_label(score), 'notes': sector_notes[s][:3]}
        for s, score in sector_bias.items()
    }

    return sector_bias_labeled, moon_rule

def apply_coin_rules(coin, sector_astro_bias, astro_data, market_data):
    flags    = []
    modifier = 0
    sector   = coin.get('sector', '')
    astro_bias = sector_astro_bias.get(sector, {}).get('astro_score', 0)

    # Funding rate rules
    funding = coin.get('funding_rate', {})
    if funding:
        rate = funding.get('rate', 0)
        if rate > 0.1 and astro_bias > 15:
            flags.append('HIGH_FUNDING_BULLISH_ASTRO')
            modifier += 10
        elif rate < -0.05:
            flags.append('NEGATIVE_FUNDING_POTENTIAL_SQUEEZE')
            modifier += 8

    # Long/Short ratio
    ls = coin.get('ls_ratio', {})
    if ls:
        ratio = ls.get('ls_ratio', 1)
        if ratio > 1.5 and astro_bias < 0:
            flags.append('OVERLEVERAGED_LONGS_BEARISH_ASTRO')
            modifier -= 15
        elif ratio < 0.7 and astro_bias > 10:
            flags.append('SHORT_HEAVY_BULLISH_ASTRO')
            modifier += 12

    # Volume spike + bullish astro
    if coin.get('volume_signal') == 'Volume Spike' and astro_bias > 15:
        flags.append('VOLUME_SPIKE_ASTRO_ALIGNED')
        modifier += 18

    # RSI sweet spot
    rsi = coin.get('rsi', 50)
    if 50 <= rsi <= 65 and astro_bias > 10:
        flags.append('RSI_ASTRO_SWEET_SPOT')
        modifier += 10

    # Strong uptrend + bullish astro
    if coin.get('trend') == 'Strong Uptrend' and astro_bias > 15:
        flags.append('TREND_ASTRO_ALIGNED')
        modifier += 12

    # Mercury retrograde + DeFi caution
    if 'Mercury' in astro_data.get('retrograde_planets', []) and sector == 'DeFi':
        flags.append('MERCURY_RX_DEFI_CAUTION')
        modifier -= 12

    # Rahu in tech signs + Meme coins
    rahu_rashi = astro_data.get('planets', {}).get('Rahu', {}).get('rashi', '')
    if rahu_rashi in ['Gemini', 'Virgo'] and sector == 'Meme':
        flags.append('RAHU_TECH_SIGN_MEME_BOOST')
        modifier += 8

    # Full Moon + meme coins = pump risk
    if astro_data.get('moon_phase') == 'Full Moon' and sector == 'Meme':
        flags.append('FULL_MOON_MEME_VOLATILE')
        modifier -= 8

    # Oversold + waxing moon = reversal
    if rsi < 35 and astro_data.get('moon_phase') in ['Waxing Crescent', 'First Quarter']:
        flags.append('OVERSOLD_WAXING_REVERSAL')
        modifier += 8

    return flags, modifier

def run_rule_engine(astro_data, market_data):
    print("⚖️  Crypto Rule Engine starting...")

    sector_astro_bias, moon_rule = calculate_sector_astro_bias(astro_data)

    day_ruler = astro_data['day_ruler']
    day_rule  = DAY_RULER_RULES.get(day_ruler, {})

    enriched_coins = []
    for coin in market_data.get('all_coins', []):
        flags, modifier = apply_coin_rules(coin, sector_astro_bias, astro_data, market_data)
        coin['rule_flags']       = flags
        coin['rule_modifier']    = modifier
        coin['sector_astro_bias'] = sector_astro_bias.get(coin.get('sector', ''), {}).get('astro_score', 0)
        enriched_coins.append(coin)

    return {
        'sector_astro_bias': sector_astro_bias,
        'enriched_coins':    enriched_coins,
        'moon_intelligence': {
            'phase':      astro_data['moon_phase'],
            'bias':       moon_rule.get('bias', 'Neutral'),
            'risk_level': moon_rule.get('risk', 'Medium'),
            'note':       moon_rule.get('note', ''),
        },
        'day_intelligence': {
            'ruler':           day_ruler,
            'favored_sectors': day_rule.get('favored', []),
            'avoid_sectors':   day_rule.get('avoid', []),
        },
    }
