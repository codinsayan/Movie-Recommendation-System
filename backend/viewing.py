"""S5's device-reported viewing contract. Evidence is not an availability guarantee."""
import math
import re

VIEWING_CONFIG = {"version": 1, "minSeconds": 120, "minFraction": 0.30,
                  "baseStrength": 0.15, "repeatStrength": 0.05, "maxStrength": 0.25,
                  "blend": 0.10, "freshnessMs": 7 * 24 * 60 * 60 * 1000}
PROVIDERS = {"cinesrc", "vidlink", "vidsrc"}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def canonical_key(movie):
    return f"{movie.get('source')}:{movie['id']}"


def viewing_evidence(payload, movies, excluded, now):
    """Resolve only indexed, qualified signals; duplicates never multiply strength."""
    if not isinstance(payload, dict) or type(payload.get("version")) is not int or payload["version"] != 1:
        return [], set()
    index = {canonical_key(movie): i for i, movie in enumerate(movies)}
    signals = {}
    for item in (payload.get("signals") if isinstance(payload.get("signals"), list) else [])[:500]:
        if not isinstance(item, dict):
            continue
        i = index.get(item["key"]) if isinstance(item.get("key"), str) else None
        watched, duration, plays = (item.get(k) for k in ("watched_seconds", "duration", "plays"))
        updated = item.get("updated_at", 0)
        if i is None or i in excluded or not all(number(v) for v in (watched, duration, plays, updated)):
            continue
        if not (0 < duration <= 86400 and max(VIEWING_CONFIG["minSeconds"], duration * VIEWING_CONFIG["minFraction"]) <= watched <= duration
                and 1 <= plays <= 100 and int(plays) == plays):
            continue
        strength = min(VIEWING_CONFIG["maxStrength"], VIEWING_CONFIG["baseStrength"] + VIEWING_CONFIG["repeatStrength"] * (plays - 1))
        value = {"index": i, "key": item["key"], "watched_seconds": watched, "duration": duration,
                 "plays": plays, "updated_at": updated, "strength": strength}
        if i not in signals or (strength, updated) > (signals[i]["strength"], signals[i]["updated_at"]):
            signals[i] = value
    # A provider failure invalidates its preceding success, even across duplicate entries.
    playback = {}
    for item in (payload.get("playback") if isinstance(payload.get("playback"), list) else [])[:1500]:
        if not isinstance(item, dict) or item.get("provider") not in PROVIDERS:
            continue
        key = item.get("key")
        success, failure = item.get("verified_at", 0), item.get("failed_at", 0)
        if not isinstance(key, str) or not re.fullmatch(r"(tmdb|curated):[1-9]\d*", key):
            continue
        if not all(number(v) and v >= 0 for v in (success, failure)):
            continue
        pair = (key, item["provider"])
        previous = playback.get(pair, (0, 0))
        playback[pair] = (max(success, previous[0]), max(failure, previous[1]))
    recent = {key for (key, _), (success, failure) in playback.items()
              if success > failure and 0 <= now - success <= VIEWING_CONFIG["freshnessMs"]}
    return sorted(signals.values(), key=lambda s: (-s["updated_at"], s["key"])), recent
