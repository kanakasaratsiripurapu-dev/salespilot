"""Synthetic geo coordinate generator.

Maps account regions to anchor cities and adds deterministic random noise.
"""

import hashlib

import numpy as np

ANCHOR_CITIES = {
    "san jose": (37.3382, -121.8863),
    "san francisco": (37.7749, -122.4194),
    "sacramento": (38.5816, -121.4944),
    "los angeles": (34.0522, -118.2437),
    "san diego": (32.7157, -117.1611),
    "las vegas": (36.1699, -115.1398),
    "phoenix": (33.4484, -112.0740),
    "reno": (39.5296, -119.8138),
}

# Map common region strings to anchor cities
REGION_MAP = {
    "united states": "san jose",
    "us": "san jose",
    "usa": "san jose",
    "central": "sacramento",
    "east": "san francisco",
    "west": "los angeles",
    "kenya": "phoenix",
    "philipines": "las vegas",
    "philippines": "las vegas",
}


def _match_region(region: str) -> str:
    """Partial string match region to an anchor city key."""
    region_lower = region.strip().lower()
    # Direct match in region map
    if region_lower in REGION_MAP:
        return REGION_MAP[region_lower]
    # Partial match against anchor city names
    for city_key in ANCHOR_CITIES:
        if city_key in region_lower or region_lower in city_key:
            return city_key
    # Partial match against region map keys
    for key, city in REGION_MAP.items():
        if key in region_lower or region_lower in key:
            return city
    return ""


def assign_coordinates(region: str, account_id: int) -> tuple[float, float]:
    """Assign lat/lon for a region with deterministic noise based on account_id."""
    matched = _match_region(region) if region else ""

    if matched and matched in ANCHOR_CITIES:
        base_lat, base_lon = ANCHOR_CITIES[matched]
    else:
        # Hash-based deterministic fallback: pick a city from hash
        h = int(hashlib.md5(str(region).encode()).hexdigest(), 16)
        cities = list(ANCHOR_CITIES.values())
        base_lat, base_lon = cities[h % len(cities)]

    # Deterministic noise seeded by account_id
    rng = np.random.RandomState(seed=int(account_id) % (2**31))
    noise_lat = rng.uniform(-0.05, 0.05)
    noise_lon = rng.uniform(-0.05, 0.05)

    return round(base_lat + noise_lat, 6), round(base_lon + noise_lon, 6)


def enrich_dataframe(df) -> None:
    """Fill null lat/lon in-place using region and account_id columns."""
    for idx in df.index:
        if df.at[idx, "latitude"] is None or (
            isinstance(df.at[idx, "latitude"], float)
            and np.isnan(df.at[idx, "latitude"])
        ):
            region = df.at[idx, "region"] if "region" in df.columns else ""
            account_id = df.at[idx, "account_id"]
            lat, lon = assign_coordinates(str(region), int(account_id))
            df.at[idx, "latitude"] = lat
            df.at[idx, "longitude"] = lon
