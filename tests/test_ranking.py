"""S5C: versioned sparse features, bounded ranking, external viewing and honest explanations."""
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import sparse
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))
import app as server
from catalog import Catalog
from discovery import Discovery
from features import feature_text
from preferences import PreferenceFeatures
from ranking import RANKING_BUDGET, FeatureStore
from recommender import EXPLAIN_FLOOR, load_dataset
from test_discovery import DREAM, SCIFI, FakeTMDB

OFFSET = 900_000_000


@pytest.fixture(scope="module")
def engine():
    return load_dataset("tmdb")


def synthetic(engine, count, start=0):
    """Realistic discovered films: snapshot metadata under IDs the snapshot does not contain."""
    movies = []
    for p in range(count):
        base = engine.movies[(start + p) % engine.n]
        movies.append({**base, "id": OFFSET + start + p, "tmdb_id": OFFSET + start + p, "title": f"{base['title']} (new {p})",
                       "full_details": True, "metadata_language": "en-US"})
    return movies


class NoCatalog:
    configured = False

    def cached_movie(self, _):
        return None

    def cached_movies(self, _):
        return {}


def extra_for(engine, movies, store=None, related=None):
    disc = Discovery(engine, NoCatalog(), features=store or FeatureStore(engine))
    entries = [{"movie": m, "sources": ["taste"] + (["related"] if related and m["id"] in related else []),
                "related_to": related.get(m["id"], []) if related else []} for m in movies]
    extra = disc._encode(entries, sorted({s for v in (related or {}).values() for s in v}))
    extra.pop("encoding")
    return extra


def test_feature_store_reuses_reencodes_changed_metadata_and_matches_the_fitted_transform(engine):
    store, movies = FeatureStore(engine), synthetic(engine, 30)
    first, stats = store.encode(movies)
    assert sparse.issparse(first) and first.shape == (30, len(engine.vectorizer.vocabulary_))
    assert (stats["misses"], stats["hits"]) == (30, 0)
    expected = normalize(engine.vectorizer.transform([feature_text(m) for m in movies])).toarray()
    assert np.allclose(first.toarray(), expected)

    again, stats = store.encode(movies)
    assert (stats["misses"], stats["hits"]) == (0, 30) and np.allclose(again.toarray(), expected)
    changed = [{**movies[0], "overview": "A brand new plot about haunted pirates."}] + movies[1:]
    _, stats = store.encode(changed)
    assert (stats["reencoded"], stats["hits"]) == (1, 29)        # only the changed metadata is re-encoded


def test_feature_store_never_mixes_feature_versions(engine):
    store = FeatureStore(engine)
    store.encode(synthetic(engine, 10))
    curated = load_dataset("curated")
    assert curated.feature_version != engine.feature_version
    store.bind(curated)
    snap = store.snapshot()
    assert snap["entries"] == 0 and snap["incompatible_dropped"] == 10 and snap["feature_version"] == curated.feature_version
    matrix, stats = store.encode(synthetic(engine, 3))
    assert stats["misses"] == 3 and matrix.shape[1] == len(curated.vectorizer.vocabulary_)


def test_feature_cache_eviction_is_bounded_by_entries_and_bytes_and_rehydrates(engine):
    store = FeatureStore(engine, budget={"feature_cache_entries": 20})
    movies = synthetic(engine, 50)
    store.encode(movies)
    assert store.snapshot()["entries"] == 20 and store.snapshot()["evictions"] == 30
    _, stats = store.encode(movies[:5])                           # evicted: rebuilt from metadata, not lost
    assert stats["misses"] == 5
    small = FeatureStore(engine, budget={"feature_cache_bytes": 20_000})
    small.encode(movies)
    assert small.bytes <= 20_000 and small.snapshot()["entries"] < 50


def test_bounded_rerank_pool_fills_top_k_without_growing_global_matrices(engine):
    shapes = (engine.X.shape, engine.content_sim.shape, engine.collab_sim.shape)
    movies = synthetic(engine, 300)
    extra = extra_for(engine, movies)
    assert sparse.issparse(extra["E"])
    liked = [engine.movies[0]["id"], movies[0]["id"]]
    disliked = [movies[1]["id"], engine.movies[1]["id"]]
    diag = {}
    result = engine.recommend(liked, disliked, k=100, extra=extra, diagnostics=diag)
    found = [m["id"] for m in result["items"]]
    assert len(found) == 100 and len(set(found)) == 100            # a large eligible pool fills top-k
    assert not set(found) & set(liked + disliked)
    assert diag["candidates"] == engine.n + 300 and diag["rerank_pool"] <= RANKING_BUDGET["rerank_pool"]
    assert (engine.X.shape, engine.content_sim.shape, engine.collab_sim.shape) == shapes


def test_per_request_work_stays_constant_as_the_feature_cache_grows(engine):
    store = FeatureStore(engine, budget={"feature_cache_entries": 10_000, "feature_cache_bytes": 256 * 1024 * 1024})
    store.encode(synthetic(engine, 3000, start=10_000))             # a large, unrelated cached catalogue
    pool = synthetic(engine, 120)
    _, cold = store.encode(pool)
    _, warm = store.encode(pool)
    assert (cold["misses"], warm["hits"]) == (120, 120)
    assert cold["batches"] == -(-120 // RANKING_BUDGET["encode_batch"]) and warm["batches"] == 0
    diag = {}
    engine.recommend([engine.movies[0]["id"]], k=12, extra=extra_for(engine, pool, store), diagnostics=diag)
    assert diag["candidates"] == engine.n + 120 and diag["rerank_pool"] == 36   # k * 3, independent of cache size


def test_no_fabricated_because_for_weak_links(engine):
    titles = {m["title"]: m["id"] for m in engine.movies}
    liked = [titles[t] for t in ("Toy Story", "Up", "Coco")]
    result = engine.recommend(liked, k=100)
    L = [engine.by_id[i] for i in liked]
    weak = 0
    for item in result["items"]:
        i = engine.by_id[item["id"]]
        link = float(max(engine.content_sim[i, L] + engine.collab_sim[i, L]))
        if item["because"]:
            assert link >= EXPLAIN_FLOOR
        else:
            weak += 1
            assert link < EXPLAIN_FLOOR and item["reason"] == "A well-rated pick to widen your taste"
    assert weak >= 1


def test_zero_vector_candidate_and_all_dislike_profiles_have_documented_fallbacks(engine):
    blank = {"id": OFFSET + 1, "tmdb_id": OFFSET + 1, "source": "tmdb", "title": "Zzxq", "genres": [], "tags": [],
             "people": [], "overview": "qqqq zzzz", "rating": 9.0, "votes": 50000, "full_details": False}
    extra = extra_for(engine, [blank])
    assert extra["E"][0].nnz == 0
    liked = [engine.movies[0]["id"]]
    found = engine.recommend(liked, k=100, extra=extra, eligible_keys=[f"tmdb:{OFFSET + 1}"])["items"]
    assert len(found) == 1 and found[0]["because"] is None
    assert found[0]["component_availability"]["content"] is False and found[0]["component_availability"]["collab"] is False

    disliked = [m["id"] for m in engine.movies[:3]]
    result = engine.recommend([], disliked, k=12)
    assert result["mode"] == "personal" and len(result["items"]) == 12
    assert all(m["because"] is None and m["reason"] == "A crowd favourite to get you started" for m in result["items"])


@pytest.fixture
def api(engine, tmp_path, monkeypatch):
    fake = FakeTMDB()
    catalog = Catalog(tmp_path / "cache.sqlite3", token="test-secret", transport=httpx.MockTransport(fake))
    store = FeatureStore(engine)
    disc = Discovery(engine, catalog, features=store)
    for name, value in {"engine": engine, "catalog": catalog, "discovery": disc, "features": store,
                        "preference_features": PreferenceFeatures(engine, catalog)}.items():
        monkeypatch.setattr(server, name, value)
    monkeypatch.delenv("CINEMAGIC_RANKING", raising=False)
    return TestClient(server.app), catalog, disc, tmp_path


def watched(*ids):
    now = time.time() * 1000
    return {"version": 1, "playback": [],
            "signals": [{"key": f"tmdb:{i}", "watched_seconds": 4000.0, "duration": 6000.0, "plays": 1,
                         "updated_at": now - p} for p, i in enumerate(ids)]}


def test_measured_viewing_of_an_external_film_applies_capped_content_evidence(api):
    client, catalog, disc, _ = api
    catalog.movie(DREAM, "en-US", set())                             # opened in details, so cached
    body = client.post("/api/recommend", json={"use_viewing": True, "viewing": watched(DREAM), "k": 12}).json()
    assert body["viewing_status"] == {"considered": 1, "applied": 1, "pending": 0, "queued": 0}
    assert body["mode"] == "viewing" and body["ranking"]["external_viewing_signals"] == 1
    assert body["watched_rows"][0]["source"]["id"] == DREAM
    assert all(m["breakdown"]["viewing"] <= 0.1 + 1e-9 for m in body["items"])
    linked = [m for m in body["items"] if m["because"]]
    assert linked and all(m["breakdown"]["viewing"] > 0 for m in linked)
    assert all(m["because"] == {"id": DREAM, "title": "Dream Thieves", "type": "watched", "key": f"tmdb:{DREAM}"}
               for m in linked)

    # An explicit dislike outranks the weaker measured signal.
    body = client.post("/api/recommend", json={"disliked": [DREAM], "use_viewing": True, "viewing": watched(DREAM)}).json()
    assert body["viewing_status"]["considered"] == 0 and body["ranking"]["external_viewing_signals"] == 0


def test_uncached_watched_film_is_pending_then_rehydrates_without_blocking(api):
    client, _, disc, _ = api
    first = client.post("/api/recommend", json={"use_viewing": True, "viewing": watched(SCIFI)}).json()
    assert first["viewing_status"] == {"considered": 1, "applied": 0, "pending": 1, "queued": 1}
    assert first["mode"] == "popular"                                  # nothing invented while pending
    disc.drain()
    second = client.post("/api/recommend", json={"use_viewing": True, "viewing": watched(SCIFI)}).json()
    assert second["viewing_status"]["applied"] == 1 and second["mode"] == "viewing"


def test_cold_disposable_cache_recovers(api, engine):
    client, catalog, disc, tmp_path = api
    inception = next(m["id"] for m in engine.movies if m["title"] == "Inception")
    body = {"liked": [inception], "k": 20, "discover": True}
    first = client.post("/api/recommend", json=body).json()
    disc.drain()
    (tmp_path / "cache.sqlite3").unlink()                              # e.g. a restarted Render instance
    server.features.clear()
    again = client.post("/api/recommend", json=body).json()
    assert again["discovery"]["status"] == "ok" and again["discovery"]["upstream_calls"] > 0
    assert again["discovery"]["pool"] == first["discovery"]["pool"]
    assert again["ranking"]["feature_cache"]["entries"] == again["discovery"]["pool"]


def test_snapshot_rollback_mode_disables_live_ranking_inputs(api, monkeypatch, engine):
    client, catalog, _, _ = api
    catalog.movie(DREAM, "en-US", set())
    monkeypatch.setenv("CINEMAGIC_RANKING", "snapshot")
    caps = client.get("/api/capabilities").json()
    assert caps["catalogue"]["dynamic_discovery"] is False and caps["ranking"]["mode"] == "snapshot"
    inception = next(m["id"] for m in engine.movies if m["title"] == "Inception")
    body = client.post("/api/recommend", json={"liked": [inception], "discover": True, "use_viewing": True,
                                               "viewing": watched(DREAM)}).json()
    assert "discovery" not in body and body["ranking"]["mode"] == "snapshot"
    assert body["ranking"]["external_viewing_signals"] == 0
    assert body["items"] == engine.recommend([inception])["items"]     # exactly the snapshot ranking


def test_damaged_or_deleted_cache_file_degrades_to_misses(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"results": [], "page": 1, "total_pages": 0})
    catalog = Catalog(tmp_path / "cache.sqlite3", token="test-secret", transport=httpx.MockTransport(handler))
    catalog.discover(sort="popularity.desc")
    catalog.discover(sort="popularity.desc")
    assert len(calls) == 1                                             # cached
    (tmp_path / "cache.sqlite3").unlink()                              # deleted after the schema was set up
    catalog.discover(sort="popularity.desc")
    assert len(calls) == 2 and catalog.cached_movies([1, 2]) == {}
    (tmp_path / "cache.sqlite3").write_bytes(b"not a database" * 100)  # damaged file
    assert catalog.discover(sort="popularity.desc")["items"] == [] and len(calls) == 3
