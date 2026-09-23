import os
import re
import time
import math
import requests

from urllib.parse import urlparse, parse_qs, unquote


# ============================================================
# DJANGO SETUP
# ============================================================

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "cleaning_manager.settings"
)

import django

django.setup()

from cleaning.models import Site


# ============================================================
# SETTINGS
# ============================================================

REQUEST_TIMEOUT = 20

GEOCODE_DELAY = 1.2

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

USER_AGENT = (
    "SolarCleaningManager/1.0 "
    "(coordinate population)"
)


# ============================================================
# KERALA BOUNDARY
# ============================================================

KERALA_LAT_MIN = 8.0
KERALA_LAT_MAX = 13.5

KERALA_LON_MIN = 74.0
KERALA_LON_MAX = 77.5


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-IN,en;q=0.9",
})


# ============================================================
# COUNTERS
# ============================================================

stats = {
    "google": 0,
    "address": 0,
    "address_without_location": 0,
    "location_district": 0,
    "location": 0,
    "customer_location": 0,
    "failed": 0,
    "blank": 0,
}


# ============================================================
# BASIC TEXT FUNCTIONS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = value.replace(
        "\n",
        " "
    )

    value = value.replace(
        "\r",
        " "
    )

    value = value.replace(
        "\t",
        " "
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def normalize_text(value):

    value = clean_text(
        value
    ).upper()

    value = re.sub(
        r"[^A-Z0-9\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# COORDINATE VALIDATION
# ============================================================

def valid_coordinate(
    lat,
    lon
):

    try:

        lat = float(lat)
        lon = float(lon)

    except (
        TypeError,
        ValueError
    ):

        return False


    if not math.isfinite(lat):
        return False

    if not math.isfinite(lon):
        return False


    if not (
        -90 <= lat <= 90
    ):
        return False


    if not (
        -180 <= lon <= 180
    ):
        return False


    # Kerala / nearby operational area
    if not (
        KERALA_LAT_MIN <= lat <= KERALA_LAT_MAX
        and
        KERALA_LON_MIN <= lon <= KERALA_LON_MAX
    ):
        return False


    return True


# ============================================================
# COORDINATE EXTRACTION FROM URL
# ============================================================

DECIMAL_PAIR_RE = re.compile(
    r"(-?\d{1,3}(?:\.\d+)?)"
    r"\s*[,;]\s*"
    r"(-?\d{1,3}(?:\.\d+)?)"
)


def extract_coordinates_from_url(
    url
):

    candidates = []


    if not url:
        return candidates


    url = clean_text(
        url
    )

    decoded = unquote(
        url
    )


    patterns = [

        (
            r"/@(-?\d+(?:\.\d+)?),"
            r"(-?\d+(?:\.\d+)?)",
            "Google @ coordinate"
        ),

        (
            r"@(-?\d+(?:\.\d+)?),"
            r"(-?\d+(?:\.\d+)?)",
            "Google @ coordinate"
        ),

        (
            r"!3d(-?\d+(?:\.\d+)?)"
            r"!4d(-?\d+(?:\.\d+)?)",
            "Google !3d !4d coordinate"
        ),

    ]


    for pattern, source in patterns:

        matches = re.findall(
            pattern,
            decoded
        )

        for lat, lon in matches:

            if valid_coordinate(
                lat,
                lon
            ):

                candidates.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "source": source,
                })


    # --------------------------------------------------------
    # QUERY PARAMETERS
    # --------------------------------------------------------

    try:

        parsed = urlparse(
            decoded
        )

        params = parse_qs(
            parsed.query
        )

        parameters = [
            "q",
            "query",
            "center",
            "ll",
            "sll",
        ]


        for parameter in parameters:

            for value in params.get(
                parameter,
                []
            ):

                value = unquote(
                    value
                )

                matches = (
                    DECIMAL_PAIR_RE.findall(
                        value
                    )
                )


                for lat, lon in matches:

                    if valid_coordinate(
                        lat,
                        lon
                    ):

                        candidates.append({
                            "lat": float(lat),
                            "lon": float(lon),
                            "source": (
                                f"URL parameter "
                                f"{parameter}"
                            ),
                        })

    except Exception:
        pass


    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique = []

    seen = set()

    for candidate in candidates:

        key = (
            round(
                candidate["lat"],
                7
            ),
            round(
                candidate["lon"],
                7
            )
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            candidate
        )


    return unique


# ============================================================
# GOOGLE MAPS URL RESOLUTION
# ============================================================

def resolve_url(
    url
):

    try:

        response = session.get(
            url,
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT
        )

        return response.url

    except Exception as exc:

        print(
            "    URL resolution failed:",
            exc
        )

        return None


# ============================================================
# GOOGLE RESULT VALIDATION
# ============================================================

GENERIC_WORDS = {
    "HOUSE",
    "HOME",
    "ROAD",
    "RD",
    "STREET",
    "ST",
    "LANE",
    "PO",
    "POST",
    "POSTOFFICE",
    "DIST",
    "DISTRICT",
    "KERALA",
    "INDIA",
    "KOZHIKODE",
    "CALICUT",
    "ERNAKULAM",
    "KOCHI",
    "KANNUR",
    "MALAPPURAM",
    "PALAKKAD",
    "WAYANAD",
    "THRISSUR",
    "ALAPPUZHA",
    "KOTTAYAM",
    "IDUKKI",
    "PATHANAMTHITTA",
    "KASARAGOD",
    "THIRUVANANTHAPURAM",
    "PIN",
    "CODE",
    "NEAR",
    "OPP",
    "OPPOSITE",
}


def meaningful_words(
    text
):

    text = normalize_text(
        text
    )

    words = text.split()

    result = set()

    for word in words:

        if len(word) < 4:
            continue

        if word in GENERIC_WORDS:
            continue

        if word.isdigit():
            continue

        result.add(
            word
        )

    return result


def google_result_related(
    site,
    final_url
):

    if not final_url:
        return False


    source_text = " ".join([
        clean_text(site.location),
        clean_text(site.address),
    ])


    source_words = meaningful_words(
        source_text
    )


    if not source_words:
        return False


    result_text = unquote(
        final_url
    )


    result_words = meaningful_words(
        result_text
    )


    overlap = (
        source_words
        .intersection(
            result_words
        )
    )


    # --------------------------------------------------------
    # PINCODE MATCH
    # --------------------------------------------------------

    source_pincodes = set(
        re.findall(
            r"\b\d{6}\b",
            source_text
        )
    )

    result_pincodes = set(
        re.findall(
            r"\b\d{6}\b",
            result_text
        )
    )


    if source_pincodes.intersection(
        result_pincodes
    ):

        return True


    # --------------------------------------------------------
    # Strong locality match
    # --------------------------------------------------------

    strong_words = [
        word
        for word in overlap
        if len(word) >= 6
    ]


    if strong_words:

        return True


    # --------------------------------------------------------
    # Two ordinary words matching
    # --------------------------------------------------------

    if len(overlap) >= 2:

        return True


    return False


# ============================================================
# GOOGLE MAPS
# ============================================================

def google_coordinates(
    site
):

    url = clean_text(
        site.google_map_link
    )


    if not url:
        return None


    print(
        "    Google Maps link found"
    )


    # --------------------------------------------------------
    # Original URL
    # --------------------------------------------------------

    candidates = (
        extract_coordinates_from_url(
            url
        )
    )


    if candidates:

        candidate = candidates[0]

        print(
            "    Coordinates found directly in Maps URL"
        )

        return candidate


    # --------------------------------------------------------
    # Resolve short URL
    # --------------------------------------------------------

    final_url = resolve_url(
        url
    )


    if not final_url:
        return None


    print(
        "    Resolved:",
        final_url
    )


    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    if not google_result_related(
        site,
        final_url
    ):

        print(
            "    Google result rejected:"
        )

        print(
            "    Result does not appear related "
            "to this site."
        )

        return None


    candidates = (
        extract_coordinates_from_url(
            final_url
        )
    )


    if not candidates:

        return None


    return candidates[0]


# ============================================================
# NOMINATIM
# ============================================================

def nominatim(
    query,
    label
):

    query = clean_text(
        query
    )


    if not query:

        return None


    # --------------------------------------------------------
    # SAFETY:
    # NEVER query just Kerala India.
    # --------------------------------------------------------

    normalized = normalize_text(
        query
    )


    forbidden_generic_queries = {
        "KERALA INDIA",
        "KERALA",
        "INDIA",
    }


    if normalized in (
        forbidden_generic_queries
    ):

        print(
            "    SKIPPED generic query:",
            query
        )

        return None


    print(
        f"    Geocoding ({label}):"
    )

    print(
        f"    {query}"
    )


    try:

        response = session.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 5,
                "countrycodes": "in",
                "addressdetails": 1,
            },
            timeout=REQUEST_TIMEOUT
        )


        response.raise_for_status()

        results = response.json()


    except Exception as exc:

        print(
            "    Geocoding failed:",
            exc
        )

        time.sleep(
            GEOCODE_DELAY
        )

        return None


    time.sleep(
        GEOCODE_DELAY
    )


    if not results:

        print(
            "    No result"
        )

        return None


    # --------------------------------------------------------
    # Find valid Kerala result
    # --------------------------------------------------------

    for result in results:

        try:

            lat = float(
                result["lat"]
            )

            lon = float(
                result["lon"]
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            continue


        if not valid_coordinate(
            lat,
            lon
        ):

            continue


        display_name = clean_text(
            result.get(
                "display_name",
                ""
            )
        )


        return {
            "lat": lat,
            "lon": lon,
            "source": label,
            "display_name": display_name,
        }


    return None


# ============================================================
# ADDRESS BUILDING
# ============================================================

def get_location(
    site
):

    return clean_text(
        site.location
    )


def get_address(
    site
):

    return clean_text(
        site.address
    )


def get_customer(
    site
):

    if not site.customer:
        return ""

    return clean_text(
        site.customer.name
    )


# ============================================================
# DISTRICT DETECTION
# ============================================================

def detect_district(
    site
):

    text = " ".join([
        get_location(site),
        get_address(site),
    ])


    text = normalize_text(
        text
    )


    districts = [

        (
            "KOZHIKODE",
            "Kozhikode"
        ),

        (
            "CALICUT",
            "Kozhikode"
        ),

        (
            "KANNUR",
            "Kannur"
        ),

        (
            "ERNAKULAM",
            "Ernakulam"
        ),

        (
            "KOCHI",
            "Ernakulam"
        ),

        (
            "MALAPPURAM",
            "Malappuram"
        ),

        (
            "PALAKKAD",
            "Palakkad"
        ),

        (
            "WAYANAD",
            "Wayanad"
        ),

        (
            "THRISSUR",
            "Thrissur"
        ),

        (
            "KOTTAYAM",
            "Kottayam"
        ),

        (
            "ALAPPUZHA",
            "Alappuzha"
        ),

        (
            "PATHANAMTHITTA",
            "Pathanamthitta"
        ),

        (
            "KASARAGOD",
            "Kasaragod"
        ),

        (
            "IDUKKI",
            "Idukki"
        ),

        (
            "THIRUVANANTHAPURAM",
            "Thiruvananthapuram"
        ),
    ]


    for keyword, district in districts:

        if keyword in text:

            return district


    return None


# ============================================================
# QUERY BUILDER
# ============================================================

def build_queries(
    site
):

    location = get_location(
        site
    )

    address = get_address(
        site
    )

    customer = get_customer(
        site
    )

    district = detect_district(
        site
    )


    queries = []


    # ========================================================
    # QUERY 1
    # Full location + address
    # ========================================================

    if location and address:

        queries.append({
            "query": (
                f"{location}, "
                f"{address}, "
                f"Kerala, India"
            ),
            "label": "full address",
            "stat": "address",
        })


    # ========================================================
    # QUERY 2
    # Address only
    # ========================================================

    if address:

        queries.append({
            "query": (
                f"{address}, "
                f"Kerala, India"
            ),
            "label": "address without location",
            "stat": "address_without_location",
        })


    # ========================================================
    # QUERY 3
    # Location + district
    # ========================================================

    if location and district:

        queries.append({
            "query": (
                f"{location}, "
                f"{district}, "
                f"Kerala, India"
            ),
            "label": "location + district",
            "stat": "location_district",
        })


    # ========================================================
    # QUERY 4
    # Location only
    # ========================================================

    if location:

        queries.append({
            "query": (
                f"{location}, "
                f"Kerala, India"
            ),
            "label": "locality",
            "stat": "location",
        })


    # ========================================================
    # QUERY 5
    # Customer + location
    # ========================================================

    if customer and location:

        queries.append({
            "query": (
                f"{customer}, "
                f"{location}, "
                f"Kerala, India"
            ),
            "label": "customer + location",
            "stat": "customer_location",
        })


    return queries


# ============================================================
# RESULT SAFETY CHECK
# ============================================================

def result_is_too_generic(
    result,
    query
):

    if not result:
        return True


    display = normalize_text(
        result.get(
            "display_name",
            ""
        )
    )


    query_words = meaningful_words(
        query
    )


    display_words = meaningful_words(
        display
    )


    # --------------------------------------------------------
    # Must have some meaningful relationship
    # --------------------------------------------------------

    overlap = (
        query_words
        .intersection(
            display_words
        )
    )


    if not overlap:

        print(
            "    Rejected generic/unrelated result:"
        )

        print(
            f"    {result.get('display_name', '')}"
        )

        return True


    return False


# ============================================================
# SAVE
# ============================================================

def save_coordinates(
    site,
    result
):

    site.latitude = result["lat"]

    site.longitude = result["lon"]

    site.save(
        update_fields=[
            "latitude",
            "longitude",
        ]
    )


# ============================================================
# PROCESS ONE SITE
# ============================================================

def process_site(
    site
):

    print()
    print(
        "-" * 60
    )

    print(
        f"Site ID: {site.id}"
    )

    print(
        f"Customer: {get_customer(site)}"
    )

    print(
        f"Location: {get_location(site)}"
    )

    print(
        f"Address: {get_address(site)}"
    )

    print(
        f"Map: {clean_text(site.google_map_link)}"
    )


    # ========================================================
    # CHECK WHETHER THERE IS ANY INFORMATION
    # ========================================================

    location = get_location(
        site
    )

    address = get_address(
        site
    )

    customer = get_customer(
        site
    )

    map_link = clean_text(
        site.google_map_link
    )


    if not (
        location
        or address
        or map_link
    ):

        stats["blank"] += 1

        print(
            "    SKIPPED:"
        )

        print(
            "    No location, address or Maps link."
        )

        return False


    # ========================================================
    # 1. GOOGLE MAPS
    # ========================================================

    if map_link:

        result = google_coordinates(
            site
        )


        if result:

            save_coordinates(
                site,
                result
            )

            stats["google"] += 1

            print(
                f"    SAVED: "
                f"{result['lat']}, "
                f"{result['lon']}"
            )

            print(
                "    SOURCE: Google Maps"
            )

            return True


    # ========================================================
    # 2. NOMINATIM QUERIES
    # ========================================================

    queries = build_queries(
        site
    )


    for query_info in queries:

        result = nominatim(
            query_info["query"],
            query_info["label"]
        )


        if not result:

            continue


        # ----------------------------------------------------
        # Safety check
        # ----------------------------------------------------

        if result_is_too_generic(
            result,
            query_info["query"]
        ):

            continue


        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        save_coordinates(
            site,
            result
        )


        stats[
            query_info["stat"]
        ] += 1


        print(
            f"    SAVED: "
            f"{result['lat']}, "
            f"{result['lon']}"
        )

        print(
            f"    SOURCE: "
            f"{result['source']}"
        )

        print(
            f"    RESULT: "
            f"{result['display_name']}"
        )


        return True


    # ========================================================
    # FAILED
    # ========================================================

    stats["failed"] += 1

    print(
        "    COORDINATES NOT FOUND"
    )

    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 60
    )

    print(
        "SOLAR CLEANING MANAGER"
    )

    print(
        "COORDINATE POPULATION - VERSION 5"
    )

    print(
        "=" * 60
    )


    # ========================================================
    # ONLY MISSING COORDINATES
    # ========================================================

    sites = (
        Site.objects
        .filter(
            latitude__isnull=True,
            longitude__isnull=True
        )
        .select_related(
            "customer"
        )
        .order_by(
            "id"
        )
    )


    total = sites.count()


    print()
    print(
        f"Sites to process: {total}"
    )


    if total == 0:

        print()
        print(
            "No sites are missing coordinates."
        )

        return


    saved = 0


    # ========================================================
    # PROCESS
    # ========================================================

    for index, site in enumerate(
        sites,
        start=1
    ):

        print()

        print(
            f"[{index}/{total}]"
        )


        before_lat = site.latitude

        before_lon = site.longitude


        process_site(
            site
        )


        # ----------------------------------------------------
        # Detect whether it was saved
        # ----------------------------------------------------

        site.refresh_from_db(
            fields=[
                "latitude",
                "longitude",
            ]
        )


        if (
            before_lat is None
            and
            before_lon is None
            and
            site.latitude is not None
            and
            site.longitude is not None
        ):

            saved += 1


    # ========================================================
    # FINAL REPORT
    # ========================================================

    print()
    print(
        "=" * 60
    )

    print(
        "POPULATION COMPLETE"
    )

    print(
        "=" * 60
    )


    print(
        f"Successfully saved: {saved}"
    )


    print()
    print(
        "BREAKDOWN"
    )

    print(
        f"  Google Maps:              "
        f"{stats['google']}"
    )

    print(
        f"  Full address:             "
        f"{stats['address']}"
    )

    print(
        f"  Address without location: "
        f"{stats['address_without_location']}"
    )

    print(
        f"  Location + district:      "
        f"{stats['location_district']}"
    )

    print(
        f"  Locality fallback:        "
        f"{stats['location']}"
    )

    print(
        f"  Customer + location:      "
        f"{stats['customer_location']}"
    )

    print(
        f"  Blank records:            "
        f"{stats['blank']}"
    )

    print(
        f"  Failed/not found:         "
        f"{stats['failed']}"
    )


    print()
    print(
        f"Total processed: {total}"
    )

    print(
        "=" * 60
    )


    # ========================================================
    # DATABASE STATUS
    # ========================================================

    total_coordinates = (
        Site.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).count()
    )


    missing_latitude = (
        Site.objects.filter(
            latitude__isnull=True
        ).count()
    )


    missing_longitude = (
        Site.objects.filter(
            longitude__isnull=True
        ).count()
    )


    missing_both = (
        Site.objects.filter(
            latitude__isnull=True,
            longitude__isnull=True
        ).count()
    )


    print()
    print(
        "DATABASE STATUS"
    )

    print(
        "=" * 60
    )

    print(
        "Total sites with coordinates:",
        total_coordinates
    )

    print(
        "Missing latitude:",
        missing_latitude
    )

    print(
        "Missing longitude:",
        missing_longitude
    )

    print(
        "Missing both:",
        missing_both
    )

    print(
        "=" * 60
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()