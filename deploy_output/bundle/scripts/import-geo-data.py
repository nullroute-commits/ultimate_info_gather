#!/usr/bin/env python3
"""Import geographic data (continents, countries, cities) into NetBox.

Uses the GeoNames REST API for country/city data and creates NetBox
Regions (continent → country hierarchy) and Sites (major cities).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pynetbox


# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
NETBOX_URL = os.environ.get("NETBOX_URL", "http://netbox:8080")
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]
GEONAMES_USERNAME = os.environ.get("GEONAMES_USERNAME", "demo")
CACHE_DIR = Path(os.environ.get("DATA_CACHE_DIR", "/app/cache"))
BATCH_SIZE = int(os.environ.get("DATA_BATCH_SIZE", "1000"))
MIN_CITY_POP = int(os.environ.get("DATA_MIN_CITY_POPULATION", "15000"))

GEONAMES_API = "https://secure.geonames.org"

# Continent codes → human names
CONTINENTS = {
    "AF": "Africa",
    "AS": "Asia",
    "EU": "Europe",
    "NA": "North America",
    "SA": "South America",
    "OC": "Oceania",
    "AN": "Antarctica",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _geonames_get(endpoint: str, params: dict) -> dict:
    """Call a GeoNames JSON endpoint with rate-limit back-off."""
    params["username"] = GEONAMES_USERNAME
    qs = urllib.parse.urlencode(params)
    url = f"{GEONAMES_API}/{endpoint}?{qs}"
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or attempt < 3:
                time.sleep(2 * attempt)
                continue
            raise
    return {}


def _slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:100]


def _get_or_create_region(nb, name: str, slug: str, parent_id=None):
    """Get an existing region by slug or create a new one."""
    existing = nb.dcim.regions.get(slug=slug)
    if existing:
        return existing
    data = {"name": name, "slug": slug}
    if parent_id is not None:
        data["parent"] = parent_id
    return nb.dcim.regions.create(data)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def _load_cache(key: str):
    p = _cache_path(key)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _save_cache(key: str, data):
    p = _cache_path(key)
    p.write_text(json.dumps(data, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Embedded fallback country data (used when GeoNames API is unavailable)
# ---------------------------------------------------------------------------
FALLBACK_COUNTRIES = [
    {"countryCode": "AF", "countryName": "Afghanistan", "continent": "AS"},
    {"countryCode": "AL", "countryName": "Albania", "continent": "EU"},
    {"countryCode": "DZ", "countryName": "Algeria", "continent": "AF"},
    {"countryCode": "AR", "countryName": "Argentina", "continent": "SA"},
    {"countryCode": "AU", "countryName": "Australia", "continent": "OC"},
    {"countryCode": "AT", "countryName": "Austria", "continent": "EU"},
    {"countryCode": "BD", "countryName": "Bangladesh", "continent": "AS"},
    {"countryCode": "BE", "countryName": "Belgium", "continent": "EU"},
    {"countryCode": "BR", "countryName": "Brazil", "continent": "SA"},
    {"countryCode": "BG", "countryName": "Bulgaria", "continent": "EU"},
    {"countryCode": "CA", "countryName": "Canada", "continent": "NA"},
    {"countryCode": "CL", "countryName": "Chile", "continent": "SA"},
    {"countryCode": "CN", "countryName": "China", "continent": "AS"},
    {"countryCode": "CO", "countryName": "Colombia", "continent": "SA"},
    {"countryCode": "HR", "countryName": "Croatia", "continent": "EU"},
    {"countryCode": "CZ", "countryName": "Czechia", "continent": "EU"},
    {"countryCode": "DK", "countryName": "Denmark", "continent": "EU"},
    {"countryCode": "EG", "countryName": "Egypt", "continent": "AF"},
    {"countryCode": "ET", "countryName": "Ethiopia", "continent": "AF"},
    {"countryCode": "FI", "countryName": "Finland", "continent": "EU"},
    {"countryCode": "FR", "countryName": "France", "continent": "EU"},
    {"countryCode": "DE", "countryName": "Germany", "continent": "EU"},
    {"countryCode": "GH", "countryName": "Ghana", "continent": "AF"},
    {"countryCode": "GR", "countryName": "Greece", "continent": "EU"},
    {"countryCode": "HK", "countryName": "Hong Kong", "continent": "AS"},
    {"countryCode": "HU", "countryName": "Hungary", "continent": "EU"},
    {"countryCode": "IN", "countryName": "India", "continent": "AS"},
    {"countryCode": "ID", "countryName": "Indonesia", "continent": "AS"},
    {"countryCode": "IR", "countryName": "Iran", "continent": "AS"},
    {"countryCode": "IQ", "countryName": "Iraq", "continent": "AS"},
    {"countryCode": "IE", "countryName": "Ireland", "continent": "EU"},
    {"countryCode": "IL", "countryName": "Israel", "continent": "AS"},
    {"countryCode": "IT", "countryName": "Italy", "continent": "EU"},
    {"countryCode": "JP", "countryName": "Japan", "continent": "AS"},
    {"countryCode": "KE", "countryName": "Kenya", "continent": "AF"},
    {"countryCode": "KR", "countryName": "South Korea", "continent": "AS"},
    {"countryCode": "MY", "countryName": "Malaysia", "continent": "AS"},
    {"countryCode": "MX", "countryName": "Mexico", "continent": "NA"},
    {"countryCode": "MA", "countryName": "Morocco", "continent": "AF"},
    {"countryCode": "NL", "countryName": "Netherlands", "continent": "EU"},
    {"countryCode": "NZ", "countryName": "New Zealand", "continent": "OC"},
    {"countryCode": "NG", "countryName": "Nigeria", "continent": "AF"},
    {"countryCode": "NO", "countryName": "Norway", "continent": "EU"},
    {"countryCode": "PK", "countryName": "Pakistan", "continent": "AS"},
    {"countryCode": "PE", "countryName": "Peru", "continent": "SA"},
    {"countryCode": "PH", "countryName": "Philippines", "continent": "AS"},
    {"countryCode": "PL", "countryName": "Poland", "continent": "EU"},
    {"countryCode": "PT", "countryName": "Portugal", "continent": "EU"},
    {"countryCode": "RO", "countryName": "Romania", "continent": "EU"},
    {"countryCode": "RU", "countryName": "Russia", "continent": "EU"},
    {"countryCode": "SA", "countryName": "Saudi Arabia", "continent": "AS"},
    {"countryCode": "SG", "countryName": "Singapore", "continent": "AS"},
    {"countryCode": "ZA", "countryName": "South Africa", "continent": "AF"},
    {"countryCode": "ES", "countryName": "Spain", "continent": "EU"},
    {"countryCode": "SE", "countryName": "Sweden", "continent": "EU"},
    {"countryCode": "CH", "countryName": "Switzerland", "continent": "EU"},
    {"countryCode": "TW", "countryName": "Taiwan", "continent": "AS"},
    {"countryCode": "TH", "countryName": "Thailand", "continent": "AS"},
    {"countryCode": "TR", "countryName": "Turkey", "continent": "EU"},
    {"countryCode": "UA", "countryName": "Ukraine", "continent": "EU"},
    {"countryCode": "AE", "countryName": "United Arab Emirates", "continent": "AS"},
    {"countryCode": "GB", "countryName": "United Kingdom", "continent": "EU"},
    {"countryCode": "US", "countryName": "United States", "continent": "NA"},
    {"countryCode": "VN", "countryName": "Vietnam", "continent": "AS"},
]


# ---------------------------------------------------------------------------
# Import steps
# ---------------------------------------------------------------------------
def fetch_countries() -> list[dict]:
    """Fetch country info from GeoNames (cached), with embedded fallback."""
    cached = _load_cache("countries")
    if cached:
        print(f"  Using cached country data ({len(cached)} countries)")
        return cached

    print("  Fetching country list from GeoNames...")
    data = _geonames_get("countryInfoJSON", {})
    countries = data.get("geonames", [])
    if countries:
        _save_cache("countries", countries)
        print(f"  Retrieved {len(countries)} countries")
    else:
        if "status" in data:
            print(f"  GeoNames API error: {data['status'].get('message', 'unknown')}")
        print(f"  Using embedded fallback ({len(FALLBACK_COUNTRIES)} countries)")
        countries = FALLBACK_COUNTRIES
        _save_cache("countries", countries)
    return countries


# Major cities per country (fallback when GeoNames is unavailable).
# Values are plain city name lists; fetch_cities() wraps them as dicts.
FALLBACK_CITIES: dict[str, list[str]] = {
    "US": [
        "New York", "Los Angeles", "Chicago", "Houston",
        "Phoenix", "San Francisco", "Seattle", "Dallas",
        "Miami", "Atlanta", "Denver", "Boston", "Washington",
    ],
    "GB": [
        "London", "Manchester", "Birmingham",
        "Edinburgh", "Glasgow", "Bristol", "Leeds",
    ],
    "DE": [
        "Berlin", "Munich", "Frankfurt", "Hamburg",
        "Cologne", "Stuttgart", "Dusseldorf",
    ],
    "FR": [
        "Paris", "Marseille", "Lyon",
        "Toulouse", "Nice", "Strasbourg",
    ],
    "JP": [
        "Tokyo", "Osaka", "Yokohama",
        "Nagoya", "Fukuoka", "Sapporo",
    ],
    "CN": [
        "Shanghai", "Beijing", "Shenzhen", "Guangzhou",
        "Chengdu", "Hangzhou", "Wuhan",
    ],
    "IN": [
        "Mumbai", "Delhi", "Bangalore", "Hyderabad",
        "Chennai", "Kolkata", "Pune",
    ],
    "BR": [
        "Sao Paulo", "Rio de Janeiro", "Brasilia",
        "Salvador", "Fortaleza", "Belo Horizonte",
    ],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "CA": [
        "Toronto", "Montreal", "Vancouver",
        "Calgary", "Ottawa", "Edmonton",
    ],
    "KR": ["Seoul", "Busan", "Incheon", "Daegu"],
    "MX": [
        "Mexico City", "Guadalajara", "Monterrey",
        "Puebla", "Tijuana",
    ],
    "IT": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
    "SE": ["Stockholm", "Gothenburg", "Malmo"],
    "CH": ["Zurich", "Geneva", "Basel", "Bern"],
    "SG": ["Singapore"],
    "IE": ["Dublin", "Cork"],
    "IL": ["Tel Aviv", "Jerusalem", "Haifa"],
    "AE": ["Dubai", "Abu Dhabi"],
    "ZA": ["Johannesburg", "Cape Town", "Durban", "Pretoria"],
    "NG": ["Lagos", "Abuja", "Kano"],
    "EG": ["Cairo", "Alexandria", "Giza"],
    "KE": ["Nairobi", "Mombasa"],
    "PL": ["Warsaw", "Krakow", "Wroclaw", "Gdansk"],
    "RU": ["Moscow", "Saint Petersburg", "Novosibirsk"],
    "TR": ["Istanbul", "Ankara", "Izmir"],
    "SA": ["Riyadh", "Jeddah", "Mecca"],
    "ID": ["Jakarta", "Surabaya", "Bandung"],
    "TH": ["Bangkok", "Chiang Mai"],
    "VN": ["Ho Chi Minh City", "Hanoi"],
    "PH": ["Manila", "Quezon City", "Cebu City"],
    "MY": ["Kuala Lumpur", "Penang"],
    "PK": ["Karachi", "Lahore", "Islamabad"],
    "BD": ["Dhaka", "Chittagong"],
    "AR": ["Buenos Aires", "Cordoba", "Rosario"],
    "CL": ["Santiago", "Valparaiso"],
    "CO": ["Bogota", "Medellin", "Cali"],
    "PE": ["Lima", "Arequipa"],
    "AT": ["Vienna", "Graz", "Salzburg"],
    "BE": ["Brussels", "Antwerp", "Ghent"],
    "DK": ["Copenhagen", "Aarhus"],
    "FI": ["Helsinki", "Espoo", "Tampere"],
    "NO": ["Oslo", "Bergen"],
    "PT": ["Lisbon", "Porto"],
    "GR": ["Athens", "Thessaloniki"],
    "CZ": ["Prague", "Brno"],
    "RO": ["Bucharest", "Cluj-Napoca"],
    "HU": ["Budapest", "Debrecen"],
    "BG": ["Sofia", "Plovdiv"],
    "HR": ["Zagreb", "Split"],
    "UA": ["Kyiv", "Kharkiv", "Odesa", "Lviv"],
    "NZ": ["Auckland", "Wellington", "Christchurch"],
    "HK": ["Hong Kong"],
    "TW": ["Taipei", "Kaohsiung", "Taichung"],
    "IR": ["Tehran", "Isfahan", "Mashhad"],
    "IQ": ["Baghdad", "Basra", "Erbil"],
    "GH": ["Accra", "Kumasi"],
    "MA": ["Casablanca", "Rabat", "Marrakech"],
    "ET": ["Addis Ababa", "Dire Dawa"],
    "DZ": ["Algiers", "Oran"],
    "AF": ["Kabul", "Kandahar"],
}


def fetch_cities(country_code: str, max_rows: int = 50) -> list[dict]:
    """Fetch major cities for a country from GeoNames (cached), with fallback."""
    cache_key = f"cities_{country_code}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    data = _geonames_get("searchJSON", {
        "country": country_code,
        "featureClass": "P",
        "orderby": "population",
        "maxRows": str(max_rows),
        "style": "MEDIUM",
    })
    cities = [
        c for c in data.get("geonames", [])
        if int(c.get("population", 0)) >= MIN_CITY_POP
    ]
    if not cities:
        fallback = FALLBACK_CITIES.get(country_code, [])
        cities = [{"name": c} for c in fallback]
    _save_cache(cache_key, cities)
    return cities


def import_continents(nb) -> dict[str, int]:
    """Create continent-level regions. Returns {code: region_id}."""
    print("\n=== Importing continents as top-level regions ===")
    mapping = {}
    for code, name in CONTINENTS.items():
        region = _get_or_create_region(nb, name, _slug(name))
        mapping[code] = region.id
        print(f"  {name}: id={region.id}")
    return mapping


def import_countries(nb, continent_map: dict[str, int], countries: list[dict]) -> dict[str, int]:
    """Create country-level regions under their continent. Returns {iso2: region_id}."""
    print(f"\n=== Importing {len(countries)} countries as child regions ===")
    country_map = {}
    for c in countries:
        iso = c.get("countryCode", "")
        name = c.get("countryName", "")
        continent_code = c.get("continentName", c.get("continent", ""))

        # Map full continent name back to code if needed
        cont_id = continent_map.get(continent_code)
        if not cont_id:
            for code, cname in CONTINENTS.items():
                if cname == continent_code:
                    cont_id = continent_map.get(code)
                    break
        if not cont_id:
            continue

        slug = _slug(f"{iso}-{name}")
        region = _get_or_create_region(nb, name, slug, parent_id=cont_id)
        country_map[iso] = region.id
    print(f"  Created/verified {len(country_map)} country regions")
    return country_map


def import_cities(nb, country_map: dict[str, int], countries: list[dict]):
    """Create city-level regions under each country region."""
    print(f"\n=== Importing cities as regions (pop >= {MIN_CITY_POP}) ===")
    total = 0
    for i, c in enumerate(countries):
        iso = c.get("countryCode", "")
        region_id = country_map.get(iso)
        if not region_id:
            continue

        cities = fetch_cities(iso)
        for city in cities:
            name = city.get("name", city.get("toponymName", ""))
            slug = _slug(f"{iso}-{name}")
            try:
                _get_or_create_region(nb, name, slug, parent_id=region_id)
                total += 1
            except Exception as exc:
                print(f"  WARN: {name} ({iso}): {exc}")

        # Rate limit: brief pause between countries
        if (i + 1) % 10 == 0:
            time.sleep(1)
            print(f"  ... processed {i + 1}/{len(countries)} countries, {total} cities so far")

    print(f"  Total city regions imported: {total}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"Connecting to NetBox at {NETBOX_URL}")
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

    # Verify connectivity
    try:
        status = nb.status()
        print(f"NetBox version: {status.get('netbox-version', 'unknown')}")
    except Exception as exc:
        print(f"ERROR: Cannot reach NetBox API: {exc}", file=sys.stderr)
        sys.exit(1)

    countries = fetch_countries()
    continent_map = import_continents(nb)
    country_map = import_countries(nb, continent_map, countries)
    import_cities(nb, country_map, countries)

    # Summary
    print("\n=== Import complete ===")
    print(f"  Regions: {nb.dcim.regions.count()}")


if __name__ == "__main__":
    main()
