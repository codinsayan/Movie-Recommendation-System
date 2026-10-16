"""Build a real-world movie catalogue from the TMDB API.

Usage:
    python scripts/build_tmdb_catalog.py [--pages 20] [--popular-pages 5] [--min-votes 300]

Credentials (either one), read from the environment or a `.env` file in the repo root:
    TMDB_READ_ACCESS_TOKEN=eyJ...   (v4 "API Read Access Token", preferred)
    TMDB_API_KEY=abc123...          (v3 "API Key")

Writes backend/data/tmdb_movies.json: a snapshot the app, the tests and the
GitHub Pages build can use without needing the key at runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "data" / "tmdb_movies.json"
API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/"

# TMDB genre names -> the names the rest of the app (and mood synonyms) use.
GENRE_MAP = {"Science Fiction": "Sci-Fi", "TV Movie": None}

try:  # certifi's CA bundle is often fresher than Python's on Windows
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()


def load_env(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader (KEY=value lines); real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class TMDB:
    def __init__(self, token: str | None = None, api_key: str | None = None):
        if not token and not api_key:
            raise SystemExit("Set TMDB_READ_ACCESS_TOKEN or TMDB_API_KEY (environment or .env). See .env.example.")
        self.token, self.api_key = token, api_key

    def get(self, path: str, **params) -> dict:
        if self.api_key and not self.token:
            params["api_key"] = self.api_key
        url = f"{API}{path}?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    raise SystemExit("TMDB rejected the credentials (401). Check your key/token.") from e
                if e.code != 429 or attempt == 4:
                    raise
                time.sleep(int(e.headers.get("Retry-After") or 0) or 2 ** attempt)
        raise RuntimeError("unreachable")


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "-".join("".join(c if c.isalnum() else " " for c in ascii_text.lower()).split())


def pick_trailer(videos: list[dict]) -> str | None:
    yt = [v for v in videos if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")]
    yt.sort(key=lambda v: (v.get("type") != "Trailer", not v.get("official"), v.get("iso_639_1") != "en"))
    return yt[0]["key"] if yt else None


def normalize_movie(d: dict) -> dict | None:
    """Turn a TMDB /movie/{id} payload (with keywords, credits, videos, recommendations) into our schema."""
    year = (d.get("release_date") or "")[:4]
    if not (d.get("poster_path") and d.get("overview") and year.isdigit()):
        return None
    genres = [GENRE_MAP.get(g["name"], g["name"]) for g in d.get("genres", [])]
    genres = [g for g in genres if g]
    keywords = [slug(k["name"]) for k in (d.get("keywords") or {}).get("keywords", [])][:12]
    crew = (d.get("credits") or {}).get("crew", [])
    cast = [c["name"] for c in (d.get("credits") or {}).get("cast", [])[:5]]
    director = next((c["name"] for c in crew if c.get("job") == "Director"), None)
    return {
        "id": d["id"],
        "title": d["title"],
        "year": int(year),
        "genres": genres,
        "tags": [k for k in keywords if k],
        "people": [slug(n) for n in ([director] if director else []) + cast[:3]],
        "overview": d["overview"],
        "tagline": d.get("tagline") or "",
        "rating": round(float(d.get("vote_average") or 0), 1),
        "votes": int(d.get("vote_count") or 0),
        "runtime": d.get("runtime") or None,
        "director": director,
        "cast": cast,
        "poster": f"{IMG}w342{d['poster_path']}",
        "backdrop": f"{IMG}w1280{d['backdrop_path']}" if d.get("backdrop_path") else None,
        "trailer": pick_trailer((d.get("videos") or {}).get("results", [])),
        "tmdb_recs": [r["id"] for r in (d.get("recommendations") or {}).get("results", [])],
    }


def collect_ids(tmdb: TMDB, pages: int, popular_pages: int, min_votes: int) -> list[int]:
    ids: dict[int, None] = {}
    for p in range(1, pages + 1):  # the most-voted films = the most recognisable
        for m in tmdb.get("/discover/movie", sort_by="vote_count.desc", page=p, include_adult="false")["results"]:
            ids.setdefault(m["id"])
    for p in range(1, popular_pages + 1):  # plus what people are watching right now
        for m in tmdb.get("/movie/popular", page=p)["results"]:
            if m.get("vote_count", 0) >= min_votes:
                ids.setdefault(m["id"])
    return list(ids)


def build(pages: int, popular_pages: int, min_votes: int) -> list[dict]:
    load_env()
    tmdb = TMDB(os.environ.get("TMDB_READ_ACCESS_TOKEN"), os.environ.get("TMDB_API_KEY"))
    ids = collect_ids(tmdb, pages, popular_pages, min_votes)
    print(f"Fetching details for {len(ids)} movies…")
    movies = []
    for n, mid in enumerate(ids, 1):
        detail = tmdb.get(f"/movie/{mid}", append_to_response="keywords,credits,videos,recommendations", language="en-US")
        movie = normalize_movie(detail)
        if movie and movie["votes"] >= min_votes and movie["genres"]:
            movies.append(movie)
        if n % 50 == 0:
            print(f"  {n}/{len(ids)}")
        time.sleep(0.03)  # stay well under TMDB's rate limit

    in_catalog = {m["id"] for m in movies}
    for m in movies:  # keep only graph edges that point inside the catalogue
        m["tmdb_recs"] = [r for r in m["tmdb_recs"] if r in in_catalog]
    return movies


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", type=int, default=20, help="pages of most-voted films (20 per page)")
    ap.add_argument("--popular-pages", type=int, default=5, help="pages of currently popular films")
    ap.add_argument("--min-votes", type=int, default=300, help="minimum TMDB vote count")
    args = ap.parse_args()

    movies = build(args.pages, args.popular_pages, args.min_votes)
    OUT.write_text("[\n" + ",\n".join("  " + json.dumps(m, ensure_ascii=False) for m in movies) + "\n]\n", encoding="utf-8")
    edges = sum(len(m["tmdb_recs"]) for m in movies)
    trailers = sum(1 for m in movies if m["trailer"])
    print(f"\nWrote {len(movies)} movies to {OUT.relative_to(ROOT)} ({edges} recommendation edges, {trailers} trailers).")


if __name__ == "__main__":
    sys.exit(main())
