"""TMDB discovery with a bounded SQLite metadata cache, separate from the model."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

import certifi
import httpx

ROOT = Path(__file__).resolve().parent.parent
GENRES = {28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
          99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
          27: "Horror", 10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Sci-Fi",
          53: "Thriller", 10752: "War", 37: "Western", 10770: "TV Movie"}


class CatalogError(Exception):
    def __init__(self, status: int, message: str, retry_after: str | None = None):
        super().__init__(message)
        self.status, self.message, self.retry_after = status, message, retry_after


def settings() -> dict:
    """Read only catalogue settings; never put credential values in responses/logs."""
    names = ("TMDB_READ_ACCESS_TOKEN", "TMDB_API_KEY", "CINEMAGIC_CACHE_PATH")
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() in names:
                    values[key.strip()] = value.strip().strip('"').strip("'")
    return {key: os.environ.get(key, values.get(key, "")).strip() for key in names}


def normalize_movie(data: dict, language: str, full: bool = False) -> dict:
    mid = data.get("id")
    if type(mid) is not int or mid <= 0:
        raise CatalogError(502, "Movie metadata is temporarily unavailable.")
    release = data.get("release_date") or ""
    year = int(release[:4]) if release[:4].isdigit() else None
    genres = [g.get("name", "") for g in data.get("genres", [])] if full else [GENRES[g] for g in data.get("genre_ids", []) if g in GENRES]
    genres = ["Sci-Fi" if g == "Science Fiction" else g for g in genres if g]
    credits = data.get("credits") or {}
    cast = [c["name"] for c in credits.get("cast", [])[:5] if c.get("name")]
    director = next((c.get("name") for c in credits.get("crew", []) if c.get("job") == "Director"), None)
    videos = [v for v in (data.get("videos") or {}).get("results", [])
              if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser") and v.get("key")]
    videos.sort(key=lambda v: (v.get("type") != "Trailer", not v.get("official")))
    poster, backdrop = data.get("poster_path"), data.get("backdrop_path")
    return {
        "id": mid, "tmdb_id": mid, "source": "tmdb", "title": data.get("title") or data.get("original_title") or "Untitled",
        "original_title": data.get("original_title") or data.get("title") or "",
        "original_language": data.get("original_language") or "",
        "alternative_titles": sorted({t["title"] for t in (data.get("alternative_titles") or {}).get("titles", []) if t.get("title")}),
        "metadata_language": language, "full_details": full, "year": year, "genres": genres,
        "tags": [k["name"] for k in (data.get("keywords") or {}).get("keywords", [])[:12] if k.get("name")],
        "overview": data.get("overview") or "No overview available in this language.",
        "rating": round(float(data.get("vote_average") or 0), 1), "votes": int(data.get("vote_count") or 0),
        "poster": f"https://image.tmdb.org/t/p/w342{poster}" if poster else None,
        "backdrop": f"https://image.tmdb.org/t/p/w1280{backdrop}" if backdrop else None,
        "tagline": data.get("tagline") or "", "runtime": data.get("runtime"),
        "cast": cast, "director": director, "trailer": videos[0]["key"] if videos else None,
    }


class Catalog:
    SEARCH_TTL = 3600
    MOVIE_TTL = 86400

    def __init__(self, db_path: Path, token: str = "", api_key: str = "", transport=None, clock=time.time):
        self.db_path = Path(db_path)
        self.token, self.api_key, self.transport, self.clock = token, api_key, transport, clock

    @classmethod
    def from_environment(cls):
        config = settings()
        path = config["CINEMAGIC_CACHE_PATH"] or str(ROOT / "backend/data/catalogue.sqlite3")
        return cls(Path(path), config["TMDB_READ_ACCESS_TOKEN"], config["TMDB_API_KEY"])

    @property
    def configured(self):
        return bool(self.token or self.api_key)

    def _read(self, key):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path, timeout=5)) as db, db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise CatalogError(503, "The metadata cache requires a newer application version.")
            db.execute("CREATE TABLE IF NOT EXISTS metadata_cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL NOT NULL)")
            db.execute("PRAGMA user_version = 1")
            row = db.execute("SELECT payload, updated_at FROM metadata_cache WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                return json.loads(row[0]), row[1]
            except (ValueError, TypeError):
                pass
        return None

    def _write(self, key, payload):
        with closing(sqlite3.connect(self.db_path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO metadata_cache VALUES (?, ?, ?)", (key, json.dumps(payload), self.clock()))
            db.execute("DELETE FROM metadata_cache WHERE key IN (SELECT key FROM metadata_cache ORDER BY updated_at DESC LIMIT -1 OFFSET 5000)")

    def _fetch(self, key, path, params, ttl):
        cached = self._read(key)
        if cached and self.clock() - cached[1] < ttl:
            return cached[0], {"cached": True, "stale": False, "updated_at": cached[1]}
        try:
            if not self.configured:
                raise CatalogError(503, "Live movie search is not configured. The downloaded catalogue is still available.")
            headers = {"Accept": "application/json"}
            params = dict(params)
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            else:
                params["api_key"] = self.api_key
            # No exception includes the request URL: v3 keys can appear in it.
            with httpx.Client(timeout=httpx.Timeout(8, connect=3), verify=certifi.where(), transport=self.transport) as client:
                response = client.get(f"https://api.themoviedb.org/3{path}", params=params, headers=headers)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After", "5")
                retry = str(min(60, max(1, int(retry)))) if retry.isdigit() else "5"
                raise CatalogError(429, "Movie search is busy. Please try again shortly.", retry)
            if response.status_code in (401, 403):
                raise CatalogError(503, "Live movie search is temporarily unavailable. The downloaded catalogue is still available.")
            if response.status_code == 404:
                raise CatalogError(404, "Movie not found.")
            if response.status_code != 200:
                raise CatalogError(502, "Movie metadata is temporarily unavailable.")
            payload = response.json()
            valid = isinstance(payload, dict) and (isinstance(payload.get("results"), list) if path == "/search/movie" else payload.get("id") == int(path.rsplit("/", 1)[1]))
            if not valid:
                raise CatalogError(502, "Movie metadata is temporarily unavailable.")
            self._write(key, payload)
            return payload, {"cached": False, "stale": False, "updated_at": self.clock()}
        except (httpx.HTTPError, ValueError):
            error = CatalogError(502, "Movie metadata is temporarily unavailable.")
        except CatalogError as exc:
            error = exc
        if cached and error.status != 404:
            return cached[0], {"cached": True, "stale": True, "updated_at": cached[1]}
        raise error from None

    def search(self, query: str, page: int, language: str, model_ids: set[int]):
        query = " ".join(query.split())
        key = "search:" + hashlib.sha256(json.dumps([query.casefold(), page, language], ensure_ascii=False).encode()).hexdigest()
        data, cache = self._fetch(key, "/search/movie", {"query": query, "page": page, "language": language, "include_adult": "false"}, self.SEARCH_TTL)
        items = [normalize_movie(item, language) for item in data["results"] if isinstance(item, dict) and type(item.get("id")) is int and item["id"] > 0 and not item.get("adult")]
        for item in items:
            item["in_model"] = item["id"] in model_ids
        return {"items": items, "page": page, "total_pages": min(500, max(0, int(data.get("total_pages") or 0))),
                "total_results": int(data.get("total_results") or 0), "language": language, **cache}

    def movie(self, movie_id: int, language: str, model_ids: set[int]):
        data, cache = self._fetch(f"movie:{movie_id}:{language}", f"/movie/{movie_id}",
                                  {"language": language, "append_to_response": "credits,videos,keywords,alternative_titles"}, self.MOVIE_TTL)
        movie = normalize_movie(data, language, full=True)
        return {**movie, "in_model": movie_id in model_ids, **cache}
