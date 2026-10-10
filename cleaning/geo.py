"""
Location helpers for the Location Search (canvassing) page.

- coords_from_text():  pulls latitude/longitude out of a Google Maps link
                       (long or short maps.app.goo.gl links) or "11.25, 75.78".
- geocode_place():     turns a place name / address into approximate
                       coordinates using OpenStreetMap (free, no API key).
- place_names_near():  turns coordinates into nearby area names
                       (village, town, suburb...) - used to find sites that
                       have no coordinates at all.
- distance_km():       straight-line distance between two points.
"""

import math
import re
from functools import lru_cache
from urllib.parse import unquote

import requests
from django.conf import settings


# OpenStreetMap asks every app to identify itself
USER_AGENT = getattr(
    settings,
    'GEOCODER_USER_AGENT',
    'SolarCleanManager/1.0 (solar panel cleaning business)'
)

# Added to place names so "Kakkodi" is looked up in the right region
GEOCODE_REGION = getattr(
    settings,
    'GEOCODE_REGION',
    'Kozhikode, Kerala, India'
)

NOMINATIM_URL = 'https://nominatim.openstreetmap.org'

NUM = r'(-?\d{1,3}\.\d+)'

# Order matters: !3d!4d is the exact pin, @lat,lng is only the map centre
LINK_PATTERNS = [
    re.compile(r'!3d' + NUM + r'!4d' + NUM),
    re.compile(r'[?&](?:q|query|ll|destination|daddr|center)=(?:loc:)?' + NUM + r'(?:,|%2C)\s*\+?' + NUM),
    re.compile(r'/(?:place|search|dir)/' + NUM + r',\s*\+?' + NUM),
    re.compile(r'@' + NUM + r',' + NUM),
]

PLAIN_COORDS = re.compile(r'^\s*' + NUM + r'\s*[, ]\s*' + NUM + r'\s*$')


def _valid(lat, lng):
    return -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0)


def _search_patterns(text):
    text = unquote(text)
    for pattern in LINK_PATTERNS:
        match = pattern.search(text)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if _valid(lat, lng):
                return lat, lng
    return None


def looks_like_link(text):
    text = (text or '').strip().lower()
    return text.startswith('http') or 'goo.gl' in text or 'google.' in text


@lru_cache(maxsize=256)
def _resolve_short_link(url):
    """maps.app.goo.gl / goo.gl links hide the coordinates - follow them."""
    try:
        response = requests.get(
            url,
            allow_redirects=True,
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
    except requests.RequestException:
        return None

    found = _search_patterns(response.url)
    if found:
        return found

    # Some redirects land on a page whose HTML contains the coordinates
    return _search_patterns(response.text[:200000])


def coords_from_text(text):
    """
    Returns (lat, lng) from a Google Maps link or a "lat, lng" string,
    or None if there are no coordinates in it.
    """
    if not text:
        return None

    text = text.strip()

    plain = PLAIN_COORDS.match(text)
    if plain:
        lat, lng = float(plain.group(1)), float(plain.group(2))
        return (lat, lng) if _valid(lat, lng) else None

    found = _search_patterns(text)
    if found:
        return found

    if 'goo.gl' in text or 'maps.app' in text:
        url = text if text.startswith('http') else 'https://' + text
        return _resolve_short_link(url)

    return None


@lru_cache(maxsize=512)
def _nominatim_search(query):
    try:
        response = requests.get(
            NOMINATIM_URL + '/search',
            params={
                'q': query,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'in',
            },
            headers={'User-Agent': USER_AGENT},
            timeout=10,
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not data:
        return None

    return float(data[0]['lat']), float(data[0]['lon'])


def geocode_place(text):
    """
    Approximate coordinates for a place name or address.
    Tries "<text>, Kozhikode, Kerala, India" first, then the text alone.
    """
    text = ' '.join((text or '').split())   # tidy spaces

    if len(text) < 3:
        return None

    return (
        _nominatim_search(f'{text}, {GEOCODE_REGION}')
        or _nominatim_search(text)
    )


@lru_cache(maxsize=256)
def place_names_near(lat, lng):
    """
    Area names around a point, e.g. {'VELLIMADUKUNNU', 'KOZHIKODE'}.
    Used to match sites that have no coordinates by their address text.
    """
    try:
        response = requests.get(
            NOMINATIM_URL + '/reverse',
            params={
                'lat': round(lat, 5),
                'lon': round(lng, 5),
                'format': 'json',
                'zoom': 16,
                'addressdetails': 1,
            },
            headers={'User-Agent': USER_AGENT},
            timeout=10,
        )
        address = response.json().get('address', {})
    except (requests.RequestException, ValueError):
        return frozenset()

    keys = (
        'neighbourhood', 'suburb', 'quarter', 'hamlet',
        'village', 'town', 'city_district', 'locality',
    )

    names = set()

    for key in keys:
        value = address.get(key)
        if value:
            for word in re.findall(r'[A-Za-z]{4,}', value):
                names.add(word.upper())

    # Too general to mean "nearby"
    names -= {'KOZHIKODE', 'CALICUT', 'KERALA', 'INDIA', 'DISTRICT', 'TALUK', 'WARD', 'NORTH', 'SOUTH', 'EAST', 'WEST'}

    return frozenset(names)


def distance_km(lat1, lng1, lat2, lng2):
    """Straight-line (haversine) distance in kilometres."""
    r = 6371.0

    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))

    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )

    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------
# Spelling-tolerant matching for Malayalam place names
#   VELLIMADUKUNNU = Velimadkunnu = vellimadukunu
#   KOZHIKODE      = Kozikode
#   KARAPARAMBA    = Karaparambu
# ---------------------------------------------------------------------

from difflib import SequenceMatcher

_SOUND_REPLACEMENTS = (
    ('ZH', 'L'),     # Kozhikode / Kolikode
    ('TH', 'T'),
    ('DH', 'D'),
    ('PH', 'F'),
    ('BH', 'B'),
    ('KH', 'K'),
    ('GH', 'G'),
    ('CH', 'C'),
    ('SH', 'S'),
    ('W', 'V'),
    ('Y', 'I'),
)


def _normalise_word(word):
    """Upper-case letters only, doubled letters collapsed: VELLIMADUKUNNU -> VELIMADUKUNU."""
    word = re.sub(r'[^A-Z]', '', word.upper())
    return re.sub(r'(.)\1+', r'\1', word)


def _sound_key(word):
    """Consonant skeleton: VELLIMADUKUNNU and VELIMADKUNNU both -> VLMDKN."""
    word = _normalise_word(word)
    if not word:
        return ''
    for old, new in _SOUND_REPLACEMENTS:
        word = word.replace(old, new)
    first, rest = word[0], word[1:]
    rest = re.sub(r'[AEIOUH]', '', rest)
    return re.sub(r'(.)\1+', r'\1', first + rest)


def _words(text):
    return [w for w in re.findall(r'[A-Za-z]+', text or '') if len(w) >= 3]


def word_matches(a, b):
    """True if two words are probably the same name spelt differently."""
    na, nb = _normalise_word(a), _normalise_word(b)

    if not na or not nb:
        return False

    if na == nb:
        return True

    # one is the start of the other: "Vellimad" finds "Vellimadukunnu"
    if len(na) >= 4 and len(nb) >= 4 and (na.startswith(nb) or nb.startswith(na)):
        return True

    ka, kb = _sound_key(a), _sound_key(b)
    if len(ka) >= 3 and ka == kb:
        return True

    # small typos in longer words
    if min(len(na), len(nb)) >= 5 and SequenceMatcher(None, na, nb).ratio() >= 0.82:
        return True

    return False


def text_matches(query, text):
    """
    True if every word of the search (3+ letters) roughly appears in the text.
    "velimadkunnu" matches "VELLIMADUKUNNU, Kozhikode".
    """
    query_words = _words(query)
    text_words = _words(text)

    if not query_words or not text_words:
        return False

    return all(
        any(word_matches(q, t) for t in text_words)
        for q in query_words
    )