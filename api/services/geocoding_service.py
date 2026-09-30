import os
import csv
import re
import requests
from django.conf import settings

# Bounding box for Continental United States (plus DC, excluding AK/HI for driving routes)
CONTINENTAL_US_BOUNDS = {
    "min_lat": 24.396308,
    "max_lat": 49.384358,
    "min_lon": -125.000000,
    "max_lon": -66.934570,
}

US_STATE_ABBR_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia'
}

NAME_TO_STATE_ABBR = {name.upper(): abbr for abbr, name in US_STATE_ABBR_TO_NAME.items()}


class GeocodingService:
    _instance = None
    _city_db = None
    _cache = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeocodingService, cls).__new__(cls)
            cls._instance._load_city_db()
        return cls._instance

    def _load_city_db(self):
        """Pre-loads US cities database for instant 0-network-call geocoding."""
        self._city_db = {}
        base_dir = settings.BASE_DIR
        uscities_path = base_dir / "data" / "uscities.csv"

        if os.path.exists(uscities_path):
            with open(uscities_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    city = r["city"].strip().upper()
                    city_norm = city.replace(" ", "").replace("-", "").replace(".", "")
                    state_id = r["state_id"].strip().upper()
                    pop = float(r["population"]) if r.get("population") else 0
                    lat = float(r["lat"])
                    lng = float(r["lng"])

                    data = {
                        "latitude": lat,
                        "longitude": lng,
                        "display_name": f"{r['city']}, {state_id}",
                        "city": r["city"],
                        "state": state_id,
                        "population": pop,
                    }

                    # Store best match (highest population) for (city, state)
                    key = (city, state_id)
                    if key not in self._city_db or pop > self._city_db[key]["population"]:
                        self._city_db[key] = data
                        self._city_db[(city_norm, state_id)] = data

                    # Also store by city alone if largest
                    if city not in self._city_db or pop > self._city_db[city]["population"]:
                        self._city_db[city] = data

    @classmethod
    def is_within_continental_us(cls, lat: float, lon: float) -> bool:
        """Checks if coordinate is within Continental USA boundaries."""
        return (
            CONTINENTAL_US_BOUNDS["min_lat"] <= lat <= CONTINENTAL_US_BOUNDS["max_lat"] and
            CONTINENTAL_US_BOUNDS["min_lon"] <= lon <= CONTINENTAL_US_BOUNDS["max_lon"]
        )

    def geocode(self, query: str) -> dict:
        """
        Geocodes a query string into lat/lon coordinates.
        Supports:
          1. Direct coordinates: '34.0522,-118.2437' or '34.0522, -118.2437'
          2. City, State: 'Dallas, TX', 'Austin, Texas', 'New York, NY'
          3. Major City: 'Chicago', 'Seattle', 'Atlanta'
        """
        if not query or not isinstance(query, str):
            raise ValueError("Location query must be a non-empty string.")

        q = query.strip()
        if q in self._cache:
            return self._cache[q]

        # 1. Check if raw coordinates
        coord_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)$", q)
        if coord_match:
            lat = float(coord_match.group(1))
            lon = float(coord_match.group(2))
            if not self.is_within_continental_us(lat, lon):
                raise ValueError(
                    f"Coordinates ({lat}, {lon}) are outside the Continental USA bounds."
                )
            result = {
                "latitude": lat,
                "longitude": lon,
                "display_name": f"{lat:.4f}, {lon:.4f}",
                "city": "",
                "state": "",
            }
            self._cache[q] = result
            return result

        # 2. Parse City and State if formatted with a comma
        parts = [p.strip() for p in q.split(",") if p.strip()]
        city_part = parts[0].upper()
        city_norm = city_part.replace(" ", "").replace("-", "").replace(".", "")

        if len(parts) >= 2:
            state_part = parts[1].upper()
            # If state is full name, convert to abbreviation
            state_abbr = NAME_TO_STATE_ABBR.get(state_part, state_part)

            # Check local DB
            candidates = [
                (city_part, state_abbr),
                (city_norm, state_abbr),
            ]
            for cand in candidates:
                if cand in self._city_db:
                    res = self._city_db[cand]
                    if not self.is_within_continental_us(res["latitude"], res["longitude"]):
                        raise ValueError(f"Location '{query}' is outside Continental USA.")
                    result = {
                        "latitude": res["latitude"],
                        "longitude": res["longitude"],
                        "display_name": res["display_name"],
                        "city": res["city"],
                        "state": res["state"],
                    }
                    self._cache[q] = result
                    return result

        # Check by city name alone in local DB
        if city_part in self._city_db:
            res = self._city_db[city_part]
            if self.is_within_continental_us(res["latitude"], res["longitude"]):
                result = {
                    "latitude": res["latitude"],
                    "longitude": res["longitude"],
                    "display_name": res["display_name"],
                    "city": res["city"],
                    "state": res["state"],
                }
                self._cache[q] = result
                return result

        # 3. Fallback: Query Nominatim (Cached, bounded to USA)
        try:
            url = "https://nominatim.openstreetmap.org/search"
            headers = {"User-Agent": "FuelRoutePlannerDjango/1.0 (contact: test@example.com)"}
            params = {
                "q": q,
                "format": "json",
                "countrycodes": "us",
                "limit": 1,
            }
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    if not self.is_within_continental_us(lat, lon):
                        raise ValueError(f"Location '{query}' is outside Continental USA.")
                    result = {
                        "latitude": lat,
                        "longitude": lon,
                        "display_name": data[0].get("display_name", q),
                        "city": parts[0] if parts else "",
                        "state": "",
                    }
                    self._cache[q] = result
                    return result
        except requests.RequestException:
            pass

        raise ValueError(
            f"Could not resolve location '{query}'. Please provide a valid US city and state (e.g. 'Austin, TX') or coordinates (e.g. '30.2672,-97.7431')."
        )
