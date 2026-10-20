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
        "source": "tmdb",
        "tmdb_id": d["id"],
        "title": d["title"],
        "original_title": d.get("original_title") or d["title"],
        "original_language": d.get("original_language") or "",
        "alternative_titles": [t["title"] for t in (d.get("alternative_titles") or {}).get("titles", []) if t.get("title")],
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


def select_model_ids(ids: list[int], include_ids=(), max_movies: int = 500) -> list[int]:
    """Offline refresh budget: prioritize explicit canonical IDs without growing unbounded."""
    if not 1 <= max_movies <= 500:
        raise ValueError("max_movies must be between 1 and 500; measure a larger model before raising this cap")
    include_ids = list(dict.fromkeys(include_ids))
    if len(include_ids) > max_movies or any(type(mid) is not int or not 1 <= mid <= 2147483647 for mid in include_ids):
        raise ValueError("Included TMDB IDs must be positive integers and fit within the model budget")
    return list(dict.fromkeys([*include_ids, *ids]))[:max_movies]


def build(pages: int, popular_pages: int, min_votes: int, max_movies: int = 500, include_ids=()) -> list[dict]:
    # Validate the budget before reading credentials or making any network requests.
    select_model_ids([], include_ids, max_movies)
    load_env()
    tmdb = TMDB(os.environ.get("TMDB_READ_ACCESS_TOKEN"), os.environ.get("TMDB_API_KEY"))
    ids = select_model_ids(collect_ids(tmdb, pages, popular_pages, min_votes), include_ids, max_movies)
    print(f"Fetching details for {len(ids)} movies…")
    movies = []
    for n, mid in enumerate(ids, 1):
        detail = tmdb.get(f"/movie/{mid}", append_to_response="keywords,credits,videos,recommendations,alternative_titles", language="en-US")
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
    ap.add_argument("--max-movies", type=int, default=500, help="active model budget, 1-500 (default: 500)")
    ap.add_argument("--include-tmdb-id", type=int, action="append", default=[],
                    help="prioritize a discovered TMDB ID in the bounded refresh; repeat for more IDs")
    args = ap.parse_args()
    if not 0 <= args.pages <= 500 or not 0 <= args.popular_pages <= 500 or args.min_votes < 0:
        ap.error("pages and popular-pages must be 0-500; min-votes must be nonnegative")
    try:
        select_model_ids([], args.include_tmdb_id, args.max_movies)
    except ValueError as error:
        ap.error(str(error))

    movies = build(args.pages, args.popular_pages, args.min_votes, args.max_movies, args.include_tmdb_id)
    OUT.write_text("[\n" + ",\n".join("  " + json.dumps(m, ensure_ascii=False) for m in movies) + "\n]\n", encoding="utf-8")
    edges = sum(len(m["tmdb_recs"]) for m in movies)
    trailers = sum(1 for m in movies if m["trailer"])
    print(f"\nWrote {len(movies)} movies to {OUT.relative_to(ROOT)} ({edges} recommendation edges, {trailers} trailers).")


if __name__ == "__main__":
    sys.exit(main())
