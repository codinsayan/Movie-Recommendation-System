"""S5B: bounded retrieval of recommendation candidates beyond the starter snapshot.

TMDB only *retrieves* possible candidates (related titles, taste-genre discovery, new
releases, broad starter pools). The project's own engine still decides their order:
candidates are encoded with the fitted TF-IDF vocabulary (no refit, no matrix growth)
and scored together with the snapshot in Recommender.recommend(extra=...).
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
from threading import BoundedSemaphore, Lock
import time

import numpy as np
from sklearn.preprocessing import normalize

from catalog import CatalogError
from features import FEATURE_LANGUAGE, feature_text

# Retrieval budgets per recommendation request (S5D verifies these; they do not cap
# the discoverable catalogue, only the work done for one request).
BUDGET = {
    "seeds": 4,              # liked films whose related titles are fetched
    "genre_pages": 2,        # taste-genre discovery pages (20 films each)
    "starter_pages": 2,      # broad pools for cold-start / dislike-only profiles
    "new_release_days": 120,
    "pool": 300,             # unique candidates handed to the ranker
    "enrich": 12,            # background detail lookups queued per request (never blocks it)
    "workers": 4,            # concurrent upstream requests
}
# One process-wide limit so many simultaneous refreshes cannot flood TMDB.
UPSTREAM = BoundedSemaphore(BUDGET["workers"])


def select_seeds(positives: list[int], limit: int) -> list[int]:
    """Most recent likes first, then likes spread across older history."""
    recent = list(reversed(positives))
    if len(recent) <= limit:
        return recent
    head = recent[:2]
    rest = recent[2:]
    picks = limit - len(head)
    step = len(rest) / picks
    return head + [rest[int(i * step)] for i in range(picks)]


def taste_genres(engine, positives, external, limit=2) -> list[str]:
    counts = Counter()
    for mid in positives:
        if mid in engine.by_id:
            counts.update(engine.movies[engine.by_id[mid]]["genres"])
    for term in (external or {}).get("genres", []):
        if term["weight"] > 0:
            counts[term["name"]] += term["weight"]
    return [g for g, _ in counts.most_common(limit)]


class Discovery:
    def __init__(self, engine, catalog, budget=None, clock=time.time):
        self.engine, self.catalog = engine, catalog
        self.budget = {**BUDGET, **(budget or {})}
        self.clock = clock
        self._background = ThreadPoolExecutor(max_workers=2, thread_name_prefix="discovery-enrich")
        self._lock = Lock()
        self._inflight: set[int] = set()
        self._pending = []

    @property
    def available(self) -> bool:
        return self.catalog.configured and bool(self.engine.movies) and self.engine.movies[0].get("source") == "tmdb"

    def _plan(self, positives, disliked, external):
        """Return [(source, label, callable)] within the request budget."""
        b, c = self.budget, self.catalog
        tasks = []
        seeds = select_seeds(positives, b["seeds"])
        for seed in seeds:
            tasks.append(("related", seed, lambda s=seed: c.related(s)))
        genres = taste_genres(self.engine, positives, external)
        if genres:
            for page in range(1, b["genre_pages"] + 1):
                # Acclaimed rather than most-voted: the snapshot already holds the most-voted films.
                tasks.append(("taste", "+".join(genres),
                              lambda p=page: c.discover(genres=genres, sort="vote_average.desc", min_votes=1000, page=p)))
        since = (dt.date.fromtimestamp(self.clock()) - dt.timedelta(days=b["new_release_days"])).isoformat()
        tasks.append(("new_release", since, lambda: c.discover(genres=genres, sort="popularity.desc", min_votes=50,
                                                               released_after=since, ttl=c.NEW_RELEASE_TTL)))
        if not positives:
            # Cold start or dislike-only: a broad starter pool; dislikes still apply in ranking.
            for page in range(1, b["starter_pages"] + 1):
                tasks.append(("starter", "popular", lambda p=page: c.discover(sort="popularity.desc", min_votes=500, page=p)))
            tasks.append(("starter", "top_rated", lambda: c.discover(sort="vote_average.desc", min_votes=3000)))
        return seeds, genres, tasks

    def _run(self, fn):
        with UPSTREAM:
            return fn()

    def candidates(self, liked, disliked, external=None):
        """Retrieve, deduplicate and encode candidates. Never raises for upstream failures."""
        disliked_set = set(disliked)
        positives = [m for m in dict.fromkeys(liked) if m not in disliked_set]
        profile = "personal" if positives else ("dislike-only" if disliked_set else "cold-start")
        report = {"status": "off", "profile": profile, "seeds": 0, "genres": [], "sources": {}, "pool": 0,
                  "enriched": 0, "summary_only": 0, "enrich_queued": 0, "upstream_calls": 0, "cache_hits": 0, "stale": False,
                  "failed_sources": 0, "requested_sources": 0}
        if not self.available:
            report["status"] = "unavailable"
            return None, report

        seeds, genres, tasks = self._plan(positives, disliked_set, external)
        report.update(seeds=len(seeds), genres=genres, requested_sources=len(tasks))
        excluded = set(liked) | disliked_set | set(self.engine.by_id)
        pool: dict[int, dict] = {}

        def account(result):
            report["upstream_calls" if not result.get("cached") else "cache_hits"] += 1
            report["stale"] |= bool(result.get("stale"))

        with ThreadPoolExecutor(max_workers=self.budget["workers"]) as executor:
            futures = [(source, label, executor.submit(self._run, fn)) for source, label, fn in tasks]
            for source, label, future in futures:   # submission order keeps the merge deterministic
                try:
                    result = future.result()
                except CatalogError:
                    report["failed_sources"] += 1
                    continue
                account(result)
                for movie in result["items"]:
                    mid = movie["id"]
                    if mid in excluded:
                        continue
                    entry = pool.get(mid)
                    if entry is None:
                        if len(pool) >= self.budget["pool"]:
                            continue
                        entry = pool[mid] = {"movie": movie, "sources": [], "related_to": []}
                    if source not in entry["sources"]:
                        entry["sources"].append(source)
                    if source == "related" and label not in entry["related_to"]:
                        entry["related_to"].append(label)
                    report["sources"][source] = report["sources"].get(source, 0) + 1

        self._enrich(pool, report)
        report["pool"] = len(pool)
        report["status"] = ("unavailable" if report["failed_sources"] == len(tasks)
                            else "partial" if report["failed_sources"] else "ok")
        if not pool:
            return None, report
        return self._encode(list(pool.values()), seeds), report

    def _enrich(self, pool, report):
        """Prefer full cached details; fetch at most `enrich` more for the best-supported candidates."""
        missing = []
        for mid, entry in pool.items():
            cached = self.catalog.cached_movie(mid)
            if cached:
                entry["movie"] = cached
                report["cache_hits"] += 1
            else:
                missing.append(mid)
        missing.sort(key=lambda mid: -len(pool[mid]["related_to"]))   # stable: retrieval order breaks ties
        # Detail lookups never block the response: rank with summaries now, and warm the
        # cache in the background so the next refresh uses keywords and cast.
        report["enrich_queued"] = self._queue_enrichment(missing[: self.budget["enrich"]])
        report["enriched"] = sum(bool(e["movie"].get("full_details")) for e in pool.values())
        report["summary_only"] = len(pool) - report["enriched"]

    def _queue_enrichment(self, targets):
        queued = 0
        with self._lock:
            for mid in targets:
                if mid in self._inflight:
                    continue
                self._inflight.add(mid)
                self._pending.append(self._background.submit(self._fetch_details, mid))
                queued += 1
            self._pending = [f for f in self._pending if not f.done()]
        return queued

    def _fetch_details(self, mid):
        try:
            with UPSTREAM:
                self.catalog.movie(mid, FEATURE_LANGUAGE, set())   # result lands in the shared cache
        except CatalogError:
            pass   # stays summary-only; a later request may retry
        finally:
            with self._lock:
                self._inflight.discard(mid)

    def drain(self, timeout=10):
        """Wait for queued background enrichment (tests and graceful shutdown)."""
        with self._lock:
            pending = list(self._pending)
        for future in pending:
            future.result(timeout=timeout)

    def _encode(self, entries, seeds):
        movies = []
        for entry in entries:
            movie = {k: v for k, v in entry["movie"].items() if k not in ("cached", "updated_at", "in_model")}
            movie.update(source="tmdb", tmdb_id=movie["id"], in_model=False, dynamic=True,
                         discovery={"sources": entry["sources"], "related_to": entry["related_to"],
                                    "features": "full" if movie.get("full_details") else "summary",
                                    "stale": bool(entry["movie"].get("stale"))})
            movies.append(movie)
        # Fitted vocabulary only: unseen words are ignored, nothing is refit or appended.
        E = normalize(self.engine.vectorizer.transform([feature_text(m) for m in movies])).toarray()
        related = np.array([len(m["discovery"]["related_to"]) / len(seeds) if seeds else 0.0 for m in movies])
        seed_titles = {}
        for sid in seeds:
            if sid in self.engine.by_id:
                seed_titles[sid] = self.engine.movies[self.engine.by_id[sid]]["title"]
            else:
                known = self.catalog.cached_movie(sid)
                if known:
                    seed_titles[sid] = known["title"]
        return {"movies": movies, "E": E, "related": related, "quality": self.engine.quality_of(movies),
                "seed_titles": seed_titles}
