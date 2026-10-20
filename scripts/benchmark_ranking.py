"""S5C benchmark: per-request ranking work against a growing cached catalogue.

Usage:  python scripts/benchmark_ranking.py

Offline and deterministic: a mock TMDB serves synthetic films built from the snapshot's
own metadata under unused IDs, so no key or network is needed. For each cache size it
records cold and warm request latency, upstream calls, feature-cache entries/bytes and
the peak memory allocated while handling one request. The numbers describe this
machine and these budgets; they are not a claim of unlimited scale.
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from catalog import Catalog  # noqa: E402
from discovery import Discovery  # noqa: E402
from ranking import FeatureStore  # noqa: E402
from recommender import load_dataset  # noqa: E402

OFFSET = 950_000_000
CACHE_SIZES = (0, 1_000, 5_000, 20_000)


def summary(engine, n):
    base = engine.movies[n % engine.n]
    genre_ids = {"Action": 28, "Adventure": 12, "Animation": 16, "Comedy": 35, "Crime": 80, "Drama": 18,
                 "Family": 10751, "Fantasy": 14, "Horror": 27, "Romance": 10749, "Sci-Fi": 878, "Thriller": 53}
    return {"id": OFFSET + n, "title": f"{base['title']} #{n}", "original_title": base["title"], "original_language": "en",
            "genre_ids": [genre_ids[g] for g in base["genres"] if g in genre_ids], "overview": base["overview"],
            "vote_average": base["rating"], "vote_count": base["votes"], "release_date": "2020-01-01"}


class SyntheticTMDB:
    """Every list endpoint returns 20 films from a large synthetic catalogue; counts calls."""
    def __init__(self, engine, offset=0):
        self.engine, self.offset, self.calls = engine, offset, 0

    def __call__(self, request):
        self.calls += 1
        path, params = request.url.path, request.url.params
        page = int(params.get("page", 1))
        seed = (int(path.split("/")[3]) if path.endswith("/recommendations") else hash(str(sorted(params.items())))) % 997
        start = self.offset + seed * 40 + (page - 1) * 20
        return httpx.Response(200, json={"results": [summary(self.engine, start + i) for i in range(20)],
                                         "page": page, "total_pages": 5})


def measure(engine, store, liked, offset):
    """Cold then warm request; latency is timed without tracing, peak memory in a traced repeat."""
    def request(disc):
        extra, report = disc.candidates(liked, [])
        diag = {}
        engine.recommend(liked, k=100, extra=extra, diagnostics=diag)
        return report, diag

    runs = {}
    with tempfile.TemporaryDirectory() as tmp:
        fake = SyntheticTMDB(engine, offset)
        catalog = Catalog(Path(tmp) / "cache.sqlite3", token="bench", transport=httpx.MockTransport(fake))
        disc = Discovery(engine, catalog, features=store, budget={"enrich": 0})
        for label in ("cold", "warm"):
            calls = fake.calls
            started = time.perf_counter()
            report, diag = request(disc)
            runs[label] = {"ms": round((time.perf_counter() - started) * 1000, 1), "upstream_calls": fake.calls - calls,
                           "pool": report["pool"], "encoded": report["features"]["misses"] + report["features"]["reencoded"],
                           "rerank_pool": diag["rerank_pool"]}
        tracemalloc.start()
        request(disc)
        runs["warm"]["peak_request_mb"] = round(tracemalloc.get_traced_memory()[1] / 2**20, 2)
        tracemalloc.stop()
    return runs


def main():
    engine = load_dataset("tmdb")
    titles = {m["title"]: m["id"] for m in engine.movies}
    liked = [titles[t] for t in ("Inception", "Interstellar", "The Dark Knight") if t in titles]
    dense_mb = 300 * len(engine.vectorizer.vocabulary_) * 8 / 2**20
    results = []
    for size in CACHE_SIZES:
        store = FeatureStore(engine, budget={"feature_cache_entries": 50_000, "feature_cache_bytes": 512 * 2**20})
        if size:
            store.encode([{**engine.movies[i % engine.n], "id": OFFSET + 10_000_000 + i} for i in range(size)])
        samples = [measure(engine, store, liked, offset=100_000 * (r + 1)) for r in range(3)]
        row = {"cached_entries_before": size,
               "cache_entries_after": store.snapshot()["entries"],
               "cache_mb_after": round(store.snapshot()["bytes"] / 2**20, 2)}
        for label in ("cold", "warm"):
            row[label] = {**samples[-1][label], "ms": round(statistics.median(s[label]["ms"] for s in samples), 1)}
        results.append(row)
    print(json.dumps({"dense_pool_matrix_mb_before_S5C": round(dense_mb, 1), "results": results}, indent=2))


if __name__ == "__main__":
    main()
