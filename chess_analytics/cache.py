"""
Owns the opponent resolution cache. This is the single biggest cost saver in
the whole pipeline: without it, a daily cron job would re-resolve the same
2,000+ opponents every single day for no reason. Only opponents not already
in data/opponent_cache.json get a fresh profile lookup.

Nothing outside this file should read or write opponent_cache.json directly —
route through load_cache/save_cache/resolve_new_opponents so the cache format
only has one place it can drift.
"""

import json
import time

from . import config
from .fetch import get_with_retry


def load_cache():
    if config.OPP_CACHE_PATH.exists():
        with open(config.OPP_CACHE_PATH) as f:
            cache = json.load(f)
        print(f"Loaded opponent cache: {len(cache)} known opponents")
        return cache
    return {}


def save_cache(cache):
    with open(config.OPP_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=1)


def resolve_new_opponents(usernames, cache):
    new_usernames = [u for u in usernames if u not in cache]
    print(f"Resolving {len(new_usernames)} new opponents (skipping {len(usernames) - len(new_usernames)} cached)")

    for i, uname in enumerate(new_usernames):
        r = get_with_retry(f"https://api.chess.com/pub/player/{uname}")
        if r.status_code == 200:
            data = r.json()
            country_code = None
            if data.get("country"):
                country_code = data["country"].rstrip("/").split("/")[-1]
            cache[uname] = {
                "country": country_code,
                "opp_joined": data.get("joined"),
                "opp_followers": data.get("followers"),
                "opp_status": data.get("status"),
            }
        else:
            cache[uname] = {"country": None, "opp_joined": None, "opp_followers": None, "opp_status": "unresolved"}

        time.sleep(config.REQUEST_DELAY)
        if i % 100 == 0 and i > 0:
            print(f"  resolved {i}/{len(new_usernames)}")

    return cache


def code_to_name(code):
    if not code or code in config.NON_COUNTRY_CODES:
        return None
    try:
        import pycountry
        c = pycountry.countries.get(alpha_2=code)
        if c:
            return c.name
    except Exception:
        pass
    overrides = {"XK": "Kosovo"}
    return overrides.get(code, None)  # unmapped codes become None, never a fake label
