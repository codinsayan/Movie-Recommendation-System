"""Check a built local/Render service without extracting streams or printing secrets.

Usage: python scripts/smoke_deployment.py https://YOUR-SERVICE.onrender.com --expected-commit FULL_SHA --live
--live deliberately exercises TMDB search/details/external preferences/dynamic ranking.
Without it, missing credentials are a supported snapshot-only deployment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class SmokeError(RuntimeError):
    pass


def base_url(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ("", "/")):
        raise SmokeError("Use a service origin without credentials, a path, query or fragment")
    if parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SmokeError("Use HTTPS for a hosted service")
    return value.rstrip("/")


def request(base: str, path: str, body=None, timeout=30):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(base + path, data=payload, headers={"Content-Type": "application/json"} if payload else {})
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.headers, response.read(8 * 1024 * 1024)
    except HTTPError as error:
        # Do not echo upstream error bodies or credentials into logs/evidence.
        with error:
            error.read(64 * 1024)  # Drain small error responses and close their sockets.
            return error.code, error.headers, b""
    except (URLError, OSError) as error:
        raise SmokeError(f"Connection failed for {path}: {type(error).__name__}") from None


def check(base: str, *, live=False, expected_commit=None, fetch=None) -> dict:
    base = base_url(base)
    if expected_commit and not re.fullmatch(r"[0-9a-fA-F]{40}", expected_commit):
        raise SmokeError("Expected commit must be a full 40-character Git SHA")
    fetch = fetch or (lambda path, body=None: request(base, path, body))
    checks = []

    def require(condition, label):
        if not condition:
            raise SmokeError(label)
        checks.append(label)

    def read(path, body=None):
        status, headers, raw = fetch(path, body)
        require(status == 200, f"HTTP 200 {path}")
        return headers, raw

    def data(path, body=None):
        headers, raw = read(path, body)
        require("application/json" in headers.get("content-type", "").lower(), f"JSON content type {path}")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise SmokeError(f"Valid JSON required for {path}") from None

    require(data("/api/health") == {"status": "ok"}, "API health contract")
    deployment = data("/api/deployment")
    require(isinstance(deployment.get("release"), str) and bool(deployment["release"]), "Release identity")
    if expected_commit:
        require(deployment.get("commit") == expected_commit.lower(), "Expected deployed Git revision")
    policy = data("/api/playback")
    require(policy.get("release") == deployment["release"], "Matching API/playback release")
    headers, html = read("/")
    require(all(asset in html for asset in (b'playback-config.js', b'app.js', b'providers.js')), "Frontend application shell")
    require("frame-src" in headers.get("content-security-policy", ""), "Frame policy header")
    require(html.index(b'playback-config.js') < html.index(b'providers.js'), "Synchronous playback policy ordering")
    _, script = read("/playback-config.js")
    require(b'CinemagicPlaybackConfig' in script, "Playback bootstrap is JavaScript")
    for asset in ("styles.css", "app.js", "engine.js", "providers.js", "viewing.js", "preferences.js",
                  "catalogue.js", "preference-resolver.js", "source-picker.js", "player.js"):
        _, raw = read("/" + asset)
        require(bool(raw), f"Nonempty asset {asset}")
    movies = data("/api/movies")
    require(isinstance(movies, list) and bool(movies), "Starter catalogue available")
    require(all(m.get("source") == "tmdb" and m.get("tmdb_id") == m["id"] for m in movies), "Explicit TMDB snapshot identities")
    meta = data("/api/meta")
    require(meta.get("movies") == len(movies), "Model/catalogue size agreement")
    model = data("/data/model.json")
    require(model.get("version") == 2 and [m["id"] for m in model.get("movies", [])] == [m["id"] for m in movies], "Static model matches deployed snapshot")
    require(model.get("meta", {}).get("preferences") == meta.get("preferences"), "Static/API feature contract parity")
    # TMDB snapshots can reference local cached posters or the trusted image CDN.
    local_poster = next((m["poster"] for m in movies if m.get("poster", "").startswith("posters/")), None)
    if local_poster:
        _, raw = read("/" + local_poster)
        require(len(raw) > 100, "Local cached poster asset")
    capabilities = data("/api/capabilities")
    require(capabilities.get("catalogue", {}).get("snapshot_source") == "tmdb", "TMDB backend capabilities")
    picks = data("/api/recommend", {"liked": [27205], "disliked": [157336], "k": 6})
    require(bool(picks.get("items")) and all(m["id"] not in (27205, 157336) for m in picks["items"]), "Snapshot recommendations and explicit exclusions")
    if not capabilities["catalogue"].get("live_search"):
        status, _, _ = fetch("/api/search?q=sintel&page=1&language=en-US")
        require(status == 503, "Missing credentials explicitly disable live search")
    for private in ("/.env", "/backend/app.py", "/backend/data/catalogue.sqlite3"):
        status, _, _ = fetch(private)
        require(status == 404, f"Private path absent {private}")
    discovery = None
    if live:
        require(capabilities["catalogue"].get("live_search") is True, "Live metadata credentials configured")
        for page in (1, 2):
            results = data(f"/api/search?q=batman&page={page}&language=en-US")
            require(results.get("page") == page and bool(results.get("items")), f"Live search page {page}")
        movie = data("/api/movies/45745?language=en-US")
        require(movie.get("id") == 45745 and movie.get("full_details") is True, "External movie details")
        preference = data("/api/preferences/tmdb/45745")
        require(preference.get("key") == "tmdb:45745" and preference.get("status") == "applied", "External preference resolution")
        external = {"version": 1, "feature_version": preference["feature_version"], "vector": preference["vector"],
                    "positive_count": 1, "negative_count": 0,
                    "genres": [{"name": g, "weight": 1.0} for g in preference["taste"]["genres"]],
                    "tags": [{"name": t, "weight": 1.0} for t in preference["taste"]["tags"]],
                    "seeds": [{"key": preference["key"], "title": preference["movie"]["title"],
                               "genres": preference["taste"]["genres"], "tags": preference["taste"]["tags"],
                               "vector": preference["vector"]}]}
        dynamic = data("/api/recommend", {"liked": [27205, 45745], "disliked": [157336], "k": 6,
                                          "discover": True, "external_preferences": external})
        require(bool(dynamic.get("items")), "Dynamic recommendation request")
        require(all(m["id"] not in (27205, 45745, 157336) for m in dynamic["items"]), "External preference exclusions")
        discovery = dynamic.get("discovery")
        # Report partial/outage status honestly; a populated snapshot fallback is not proof of discovery.
        require(isinstance(discovery, dict) and discovery.get("status") == "ok" and discovery.get("pool", 0) > 0,
                "Live discovery ready (not partial/snapshot fallback)")
    return {"origin": base, "deployment": deployment, "catalogue_movies": len(movies), "live": live,
            "live_search_configured": capabilities["catalogue"].get("live_search", False),
            "discovery": discovery, "passed": checks,
            "media_playback": "Not tested; verify provider video/audio and device-local state in a browser"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--expected-commit")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--wait-seconds", type=float, default=0, help="Optional wait for an actual JSON API health response after cold start")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        base = base_url(args.url)
        if args.timeout <= 0 or args.wait_seconds < 0:
            raise SmokeError("Timeout must be positive and wait time nonnegative")
        deadline = time.monotonic() + args.wait_seconds
        while args.wait_seconds:
            try:
                status, headers, raw = request(base, "/api/health", timeout=min(args.timeout, max(1, deadline - time.monotonic())))
                healthy = status == 200 and "application/json" in headers.get("content-type", "") and json.loads(raw) == {"status": "ok"}
            except (SmokeError, ValueError, UnicodeDecodeError):
                healthy = False
            if healthy:
                break
            if time.monotonic() >= deadline:
                raise SmokeError("Cold-start wait ended without a healthy JSON API")
            time.sleep(min(3, max(0, deadline - time.monotonic())))
        result = check(base, live=args.live, expected_commit=args.expected_commit,
                       fetch=lambda path, body=None: request(base, path, body, timeout=args.timeout))
    except SmokeError as error:
        parser.exit(1, "Deployment check failed: " + str(error) + "\n")
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
