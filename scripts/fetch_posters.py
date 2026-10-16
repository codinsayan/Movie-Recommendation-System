"""Download a poster for every movie from Wikipedia and cache it locally.

Usage:  python scripts/fetch_posters.py [--force]

Posters are saved to frontend/posters/<id>.jpg and the `poster` field in
backend/data/movies.json is updated. Movies without a poster keep the
generated gradient fallback in the UI. No API key required.
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "data" / "movies.json"
OUT = ROOT / "frontend" / "posters"
UA = {"User-Agent": "CinemagicRecommender/0.2 (college project; poster cache)"}
API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

try:  # certifi's CA bundle is often fresher than Python's on Windows
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

# Exact Wikipedia page titles where the obvious guesses are wrong or ambiguous.
OVERRIDES = {
    "WALL·E": "WALL-E",
    "Dune: Part One": "Dune (2021 film)",
    "Indiana Jones: Raiders of the Lost Ark": "Raiders of the Lost Ark",
    "Se7en": "Seven (1995 film)",
    "Pride & Prejudice": "Pride & Prejudice (2005 film)",
}


def get_json(title: str) -> dict | None:
    url = API + urllib.parse.quote(title.replace(" ", "_"), safe="")
    try:
        return json.loads(download(url))
    except Exception:
        return None


def download(url: str, attempts: int = 5) -> bytes:
    """Fetch bytes, backing off when Wikimedia rate-limits us (HTTP 429)."""
    for i in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30, context=SSL_CTX) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == attempts - 1:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 2 ** (i + 1))
    raise RuntimeError("unreachable")


def find_image(movie: dict) -> str | None:
    t, y = movie["title"], movie["year"]
    candidates = [OVERRIDES[t]] if t in OVERRIDES else []
    candidates += [f"{t} ({y} film)", f"{t} (film)", t]
    for c in candidates:
        page = get_json(c)
        if not page or page.get("type") == "disambiguation":
            continue
        desc = (page.get("description") or "").lower()
        img = (page.get("originalimage") or page.get("thumbnail") or {}).get("source")
        if img and ("film" in desc or "movie" in desc):
            return img
    return None


def main(force: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    movies = json.loads(DATA.read_text(encoding="utf-8"))
    missing = []
    for m in movies:
        dest = OUT / f"{m['id']}.jpg"
        if dest.exists() and not force:
            m["poster"] = f"posters/{dest.name}"
            continue
        img = find_image(m)
        if not img:
            missing.append(m["title"])
            m.pop("poster", None)
            continue
        try:
            dest.write_bytes(download(img))
        except Exception as e:
            print(f"  ✗ {m['title']}: {e}")
            missing.append(m["title"])
            m.pop("poster", None)
            continue
        m["poster"] = f"posters/{dest.name}"
        print(f"  ✓ {m['title']}")
        time.sleep(1.0)  # be polite to Wikimedia

    DATA.write_text(
        "[\n" + ",\n".join("  " + json.dumps(m, ensure_ascii=False) for m in movies) + "\n]\n",
        encoding="utf-8",
    )
    print(f"\n{len(movies) - len(missing)}/{len(movies)} posters cached.")
    if missing:
        print("Missing (gradient fallback will be used):", ", ".join(missing))


if __name__ == "__main__":
    main(force="--force" in sys.argv)
