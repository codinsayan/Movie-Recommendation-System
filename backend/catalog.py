"""TMDB discovery with a bounded SQLite metadata cache, separate from the model."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

import certifi
import httpx
from features import FEATURE_LANGUAGE, normalized_features

ROOT = Path(__file__).resolve().parent.parent
GENRES = {28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
          99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
          27: "Horror", 10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Sci-Fi",
          53: "Thriller", 10752: "War", 37: "Western", 10770: "TV Movie"}
GENRE_IDS = {name: gid for gid, name in GENRES.items() if name != "TV Movie"}
DISCOVER_SORTS = {"vote_count.desc", "popularity.desc", "vote_average.desc", "primary_release_date.desc"}


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
    movie = {
        "id": mid, "tmdb_id": mid, "source": "tmdb", "title": data.get("title") or data.get("original_title") or "Untitled",
        "original_title": data.get("original_title") or data.get("title") or "",
        "original_language": data.get("original_language") or "",
        "alternative_titles": sorted({t["title"] for t in (data.get("alternative_titles") or {}).get("titles", []) if t.get("title")}),
        "metadata_language": language, "full_details": full, "year": year, "genres": genres,
        "tags": [k["name"] for k in (data.get("keywords") or {}).get("keywords", [])[:12] if k.get("name")],
        "overview": data.get("overview") or "No overview available in this language.",
        "feature_overview": data.get("overview") or "",
        "rating": round(float(data.get("vote_average") or 0), 1), "votes": int(data.get("vote_count") or 0),
        "poster": f"https://image.tmdb.org/t/p/w342{poster}" if poster else None,
        "backdrop": f"https://image.tmdb.org/t/p/w1280{backdrop}" if backdrop else None,
        "tagline": data.get("tagline") or "", "runtime": data.get("runtime"),
        "cast": cast, "director": director, "trailer": videos[0]["key"] if videos else None,
    }
    features = normalized_features(movie)
    movie.update({k: features[k] for k in ("genres", "tags", "people")})
    return movie


class Catalog:
    SEARCH_TTL = 3600
    MOVIE_TTL = 86400
    RELATED_TTL = 86400      # related titles change slowly
    DISCOVER_TTL = 6 * 3600  # broad discovery pages
    NEW_RELEASE_TTL = 3 * 3600  # new releases should appear without a snapshot rebuild

    def __init__(self, db_path: Path, token: str = "", api_key: str = "", transport=None, clock=time.time):
        self.db_path = Path(db_path)
        self.token, self.api_key, self.transport, self.clock = token, api_key, transport, clock
        self._schema_ready = False

    @classmethod
    def from_environment(cls):
        config = settings()
        path = config["CINEMAGIC_CACHE_PATH"] or str(ROOT / "backend/data/catalogue.sqlite3")
        return cls(Path(path), config["TMDB_READ_ACCESS_TOKEN"], config["TMDB_API_KEY"])

    @property
    def configured(self):
        return bool(self.token or self.api_key)

    def _ensure_schema(self, db):
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise CatalogError(503, "The metadata cache requires a newer application version.")
        db.execute("CREATE TABLE IF NOT EXISTS metadata_cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL NOT NULL)")
        db.execute("PRAGMA user_version = 1")

    def _select(self, keys):
        """Read cache rows. The schema is written once per process; a deleted (disposable)
        cache file is recreated on the next access instead of failing the request."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        marks = ",".join("?" * len(keys))
        for attempt in range(2):
            with closing(sqlite3.connect(self.db_path, timeout=5)) as db, db:
                if not self._schema_ready or attempt:
                    self._ensure_schema(db)
                    self._schema_ready = True
                try:
                    return db.execute(f"SELECT key, payload, updated_at FROM metadata_cache WHERE key IN ({marks})",
                                      list(keys)).fetchall()
                except sqlite3.OperationalError:
                    if attempt:
                        raise
        return []

    def _read_many(self, keys):
        rows = {}
        for start in range(0, len(keys), 500):   # stay well under SQLite's bound-parameter limit
            try:
                found = self._select(keys[start:start + 500])
            except sqlite3.Error:
                found = []   # a locked or damaged derived cache behaves like a miss, never a failed request
            for key, payload, updated_at in found:
                try:
                    rows[key] = (json.loads(payload), updated_at)
                except (ValueError, TypeError):
                    pass
        return rows

    def _read(self, key):
        return self._read_many([key]).get(key)

    def _write(self, key, payload):
        try:
            with closing(sqlite3.connect(self.db_path, timeout=5)) as db, db:
                self._ensure_schema(db)
                db.execute("INSERT OR REPLACE INTO metadata_cache VALUES (?, ?, ?)", (key, json.dumps(payload), self.clock()))
                db.execute("DELETE FROM metadata_cache WHERE key IN (SELECT key FROM metadata_cache ORDER BY updated_at DESC LIMIT -1 OFFSET 5000)")
        except sqlite3.Error:
            pass   # the response is still correct; the next request simply refetches

    def _fetch(self, key, path, params, ttl, kind="detail"):
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
            valid = isinstance(payload, dict) and (isinstance(payload.get("results"), list) if kind == "list" else payload.get("id") == int(path.rsplit("/", 1)[1]))
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
        data, cache = self._fetch(key, "/search/movie", {"query": query, "page": page, "language": language, "include_adult": "false"}, self.SEARCH_TTL, "list")
        items = [normalize_movie(item, language) for item in data["results"] if isinstance(item, dict) and type(item.get("id")) is int and item["id"] > 0 and not item.get("adult")]
        for item in items:
            item["in_model"] = item["id"] in model_ids
        return {"items": items, "page": page, "total_pages": min(500, max(0, int(data.get("total_pages") or 0))),
                "total_results": int(data.get("total_results") or 0), "language": language, **cache}

    def _list(self, data):
        return [normalize_movie(item, FEATURE_LANGUAGE) for item in data["results"]
                if isinstance(item, dict) and type(item.get("id")) is int and item["id"] > 0 and not item.get("adult")]

    def related(self, movie_id: int, page: int = 1):
        """TMDB's audience-driven related titles for one movie (fixed endpoint, validated ID)."""
        if type(movie_id) is not int or not 0 < movie_id <= 2147483647 or page not in (1, 2):
            raise CatalogError(422, "Invalid related-title request.")
        data, cache = self._fetch(f"related:{movie_id}:{page}", f"/movie/{movie_id}/recommendations",
                                  {"language": FEATURE_LANGUAGE, "page": page}, self.RELATED_TTL, "list")
        return {"items": self._list(data), **cache}

    def discover(self, *, genres=(), sort="vote_count.desc", min_votes=200, released_after=None, page=1, ttl=None):
        """TMDB discovery with an allow-listed parameter set; never forwards arbitrary query strings."""
        if sort not in DISCOVER_SORTS or page not in (1, 2, 3) or type(min_votes) is not int or not 0 <= min_votes <= 100000:
            raise CatalogError(422, "Invalid discovery request.")
        genre_ids = sorted({GENRE_IDS[g] for g in genres if g in GENRE_IDS})
        params = {"language": FEATURE_LANGUAGE, "sort_by": sort, "vote_count.gte": min_votes,
                  "include_adult": "false", "include_video": "false", "page": page}
        if genre_ids:
            params["with_genres"] = "|".join(map(str, genre_ids))  # OR: any of the taste genres
        if released_after is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", released_after):
                raise CatalogError(422, "Invalid discovery request.")
            params["primary_release_date.gte"] = released_after
        key = "discover:" + hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        data, cache = self._fetch(key, "/discover/movie", params, ttl or self.DISCOVER_TTL, "list")
        return {"items": self._list(data), **cache}

    def cached_movie(self, movie_id: int, language: str = FEATURE_LANGUAGE):
        """Full details already in the cache (fresh or stale), without any upstream request."""
        return self.cached_movies([movie_id], language).get(movie_id)

    def cached_movies(self, movie_ids, language: str = FEATURE_LANGUAGE):
        """Batch form of cached_movie: one cache query for a whole candidate pool."""
        keys = {f"movie:{mid}:{language}": mid for mid in movie_ids}
        found = {}
        for key, (payload, updated_at) in self._read_many(list(keys)).items():
            try:
                found[keys[key]] = {**normalize_movie(payload, language, full=True), "cached": True,
                                    "stale": self.clock() - updated_at >= self.MOVIE_TTL, "updated_at": updated_at}
            except CatalogError:
                pass
        return found

    def movie(self, movie_id: int, language: str, model_ids: set[int]):
        data, cache = self._fetch(f"movie:{movie_id}:{language}", f"/movie/{movie_id}",
                                  {"language": language, "append_to_response": "credits,videos,keywords,alternative_titles"}, self.MOVIE_TTL)
        movie = normalize_movie(data, language, full=True)
        return {**movie, "in_model": movie_id in model_ids, **cache}
