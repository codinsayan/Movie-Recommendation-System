"""S5B dynamic discovery: deterministic mock-TMDB fixtures, no key or network required."""
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import app as server
from catalog import Catalog
from discovery import Discovery, select_seeds
from preferences import PreferenceFeatures
from recommender import load_dataset

DREAM, NEW, SCIFI, STARTER, TOP, LATER, EXT_REL, HORROR = range(910000001, 910000009)


def summary(mid, title, genre_ids, overview, votes=5000, rating=7.6, release="2015-05-01"):
    return {"id": mid, "title": title, "original_title": title, "original_language": "en", "genre_ids": genre_ids,
            "overview": overview, "vote_average": rating, "vote_count": votes, "release_date": release,
            "poster_path": f"/{mid}.jpg", "backdrop_path": f"/{mid}-b.jpg"}


FIXTURES = {
    DREAM: summary(DREAM, "Dream Thieves", [878, 28, 53],
                   "A thief enters dreams to steal secrets in a heist inside the subconscious mind."),
    NEW: summary(NEW, "Orbit Run", [878, 12], "Astronauts race through space to save a failing station.",
                 votes=120, rating=7.1, release="2026-09-01"),
    SCIFI: summary(SCIFI, "Signal Lost", [878], "A scientist decodes an alien signal from deep space."),
    STARTER: summary(STARTER, "Office Party", [35], "Coworkers survive a chaotic office party.", votes=9000, rating=6.9),
    TOP: summary(TOP, "Quiet River", [18], "A family reunites by a river after years apart.", votes=12000, rating=8.6),
    LATER: summary(LATER, "Late Comet", [878], "A comet appears and an astronomer races to warn the world.",
                   votes=80, rating=7.0, release="2026-10-15"),
    EXT_REL: summary(EXT_REL, "Mind Maze", [878, 53], "A heist crew builds a maze of dreams within dreams."),
    HORROR: summary(HORROR, "Night House", [27], "A haunted house traps a family with a demon."),
}


def detail(mid):
    s = FIXTURES[mid]
    return {**{k: v for k, v in s.items() if k != "genre_ids"},
            "genres": [{"name": {878: "Science Fiction", 28: "Action", 53: "Thriller", 12: "Adventure", 35: "Comedy",
                                 18: "Drama", 27: "Horror"}[g]} for g in s["genre_ids"]],
            "keywords": {"keywords": [{"name": "dream"}, {"name": "heist"}, {"name": "subconscious"}] if mid == DREAM else []},
            "credits": {"cast": [{"name": "Test Actor"}], "crew": [{"name": "Test Director", "job": "Director"}]},
            "runtime": 120, "videos": {"results": []}}


class FakeTMDB:
    """Routes the fixed TMDB endpoints; records calls and peak concurrency."""
    def __init__(self, related=None, fail=None):
        self.related = related or {}
        self.fail = fail or {}
        self.calls, self.active, self.peak = [], 0, 0
        self.new_releases = [NEW]
        self.lock = threading.Lock()

    def __call__(self, request):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.calls.append(request.url.path)
        try:
            time.sleep(0.01)  # let concurrent requests overlap so the peak is meaningful
            path, params = request.url.path, request.url.params
            for prefix, status in self.fail.items():
                if path.startswith(prefix):
                    return httpx.Response(status, headers={"Retry-After": "3"})
            if path.endswith("/recommendations"):
                mid = int(path.split("/")[3])
                return httpx.Response(200, json={"results": [FIXTURES[i] for i in self.related.get(mid, [])]})
            if path == "/3/discover/movie":
                if "primary_release_date.gte" in params:
                    ids = self.new_releases
                elif "with_genres" in params:  # taste genres; page 2 repeats page 1 to exercise de-duplication
                    ids = [SCIFI, DREAM]
                elif params["sort_by"] == "popularity.desc":
                    ids = [STARTER, HORROR]
                else:
                    ids = [TOP]
                return httpx.Response(200, json={"results": [FIXTURES[i] for i in ids], "page": 1, "total_pages": 2})
            mid = int(path.rsplit("/", 1)[1])
            return httpx.Response(200, json=detail(mid)) if mid in FIXTURES else httpx.Response(404)
        finally:
            with self.lock:
                self.active -= 1


@pytest.fixture(scope="module")
def engine():
    return load_dataset("tmdb")


@pytest.fixture
def inception(engine):
    return next(m["id"] for m in engine.movies if m["title"] == "Inception")


def make(engine, tmp_path, fake, clock=time.time, configured=True, **budget):
    catalog = Catalog(tmp_path / "cache.sqlite3", token="test-secret" if configured else "",
                      transport=httpx.MockTransport(fake), clock=clock)
    return catalog, Discovery(engine, catalog, budget=budget or None, clock=clock)


def ids(result):
    return [m["id"] for m in result["items"]]


def test_fixtures_are_outside_the_snapshot(engine):
    assert not set(FIXTURES) & set(engine.by_id)


def test_discovered_film_is_recommended_explained_and_usable(engine, inception, tmp_path, monkeypatch):
    fake = FakeTMDB(related={inception: [DREAM, EXT_REL]})
    catalog, disc = make(engine, tmp_path, fake)
    monkeypatch.setattr(server, "engine", engine)
    monkeypatch.setattr(server, "catalog", catalog)
    monkeypatch.setattr(server, "discovery", disc)
    monkeypatch.setattr(server, "preference_features", PreferenceFeatures(engine, catalog))
    client = TestClient(server.app)

    first = client.post("/api/recommend", json={"liked": [inception], "k": 20, "discover": True}).json()
    assert next(m for m in first["items"] if m["id"] == DREAM)["discovery"]["features"] == "summary"
    assert first["discovery"]["enrich_queued"] >= 1                   # details fetched off the request path
    disc.drain()
    body = client.post("/api/recommend", json={"liked": [inception], "k": 20, "discover": True}).json()
    dream = next(m for m in body["items"] if m["id"] == DREAM)
    assert dream["dynamic"] is True and dream["in_model"] is False and dream["tmdb_id"] == DREAM
    assert dream["because"] == {"id": inception, "title": "Inception", "evidence": "tmdb-related"}
    assert dream["reason"] == "Because you loved Inception"
    assert dream["discovery"]["features"] == "full"          # the next refresh uses the enriched details
    assert set(dream["breakdown"]) == {"content", "collab", "quality"}
    report = body["discovery"]
    assert report["status"] == "ok" and report["profile"] == "personal" and report["recommended"] >= 1

    # The discovered film opens details and can be liked through S5A without a snapshot rebuild.
    assert client.get(f"/api/movies/{DREAM}").json()["title"] == "Dream Thieves"
    record = client.get(f"/api/preferences/tmdb/{DREAM}").json()
    assert record["status"] == "applied" and engine.n == 447


def test_duplicates_collapse_and_disliked_ids_stay_out_of_every_source(engine, inception, tmp_path):
    fake = FakeTMDB(related={inception: [DREAM, SCIFI, DREAM]})
    _, disc = make(engine, tmp_path, fake)
    extra, report = disc.candidates([inception], [])
    found = [m["id"] for m in extra["movies"]]
    assert len(found) == len(set(found)) and found.count(DREAM) == 1
    assert set(next(m for m in extra["movies"] if m["id"] == DREAM)["discovery"]["sources"]) >= {"related", "taste"}

    extra, _ = disc.candidates([inception], [DREAM])
    assert DREAM not in [m["id"] for m in extra["movies"]]
    result = engine.recommend([inception], [DREAM], k=100, extra=extra)
    assert DREAM not in ids(result)
    # A dislike is a similarity penalty, not a genre ban: other sci-fi discoveries remain eligible.
    assert {SCIFI, NEW} & set(ids(result))


def test_request_budgets_and_concurrency(engine, tmp_path):
    likes = [m["id"] for m in engine.movies[:30]]
    fake = FakeTMDB(related={mid: [DREAM, SCIFI, EXT_REL] for mid in likes})
    _, disc = make(engine, tmp_path, fake, pool=4, enrich=2, workers=2)
    extra, report = disc.candidates(likes, [])
    disc.drain()
    related_calls = [c for c in fake.calls if c.endswith("/recommendations")]
    assert len(related_calls) == 4 == report["seeds"]                  # seed cap, not 30
    assert len(extra["movies"]) <= 4 == report["pool"]                 # pool cap
    assert report["enrich_queued"] <= 2                                # enrichment cap
    assert report["upstream_calls"] <= 4 + 2 + 1                       # seeds + taste pages + new release
    assert len(fake.calls) <= 4 + 2 + 1 + 2                            # ... + the 2 queued background details
    assert fake.peak <= 4                                              # process-wide upstream limit


def test_seed_selection_mixes_recent_and_older_likes():
    assert select_seeds([1, 2, 3], 4) == [3, 2, 1]
    assert select_seeds(list(range(1, 11)), 4) == [10, 9, 8, 4]


@pytest.mark.parametrize("fail", [{"/3/movie/": 429, "/3/discover": 500}, {"/3/discover": 503}])
def test_upstream_failures_keep_a_usable_result(engine, inception, tmp_path, monkeypatch, fail):
    fake = FakeTMDB(related={inception: [DREAM]}, fail=fail)
    catalog, disc = make(engine, tmp_path, fake)
    monkeypatch.setattr(server, "engine", engine)
    monkeypatch.setattr(server, "discovery", disc)
    body = TestClient(server.app).post("/api/recommend", json={"liked": [inception], "discover": True}).json()
    assert len(body["items"]) == 12                                    # snapshot fallback still ranks
    assert body["discovery"]["status"] in ("partial", "unavailable")
    assert body["discovery"]["failed_sources"] >= 1


def test_missing_credentials_and_stale_cache(engine, inception, tmp_path, monkeypatch):
    fake = FakeTMDB(related={inception: [DREAM]})
    _, disc = make(engine, tmp_path, fake, configured=False)
    extra, report = disc.candidates([inception], [])
    assert extra is None and report["status"] == "unavailable" and fake.calls == []
    monkeypatch.setattr(server, "engine", engine)
    monkeypatch.setattr(server, "discovery", disc)
    plain = TestClient(server.app).post("/api/recommend", json={"liked": [inception]}).json()
    with_flag = TestClient(server.app).post("/api/recommend", json={"liked": [inception], "discover": True}).json()
    assert ids(plain) == ids(with_flag)                               # unavailable discovery changes nothing

    now = [1_800_000_000.0]
    fake = FakeTMDB(related={inception: [DREAM]})
    catalog, disc = make(engine, tmp_path / "s", fake, clock=lambda: now[0])
    disc.candidates([inception], [])
    now[0] += 2 * 86400                                               # everything expired
    fake.fail = {"/3/": 502}
    extra, report = disc.candidates([inception], [])
    assert DREAM in [m["id"] for m in extra["movies"]] and report["stale"] is True


def test_new_release_becomes_eligible_after_refresh(engine, inception, tmp_path):
    now = [1_800_000_000.0]
    fake = FakeTMDB(related={inception: []})
    _, disc = make(engine, tmp_path, fake, clock=lambda: now[0])
    first, _ = disc.candidates([inception], [])
    fake.new_releases = [NEW, LATER]
    cached, _ = disc.candidates([inception], [])
    assert LATER not in [m["id"] for m in first["movies"]] + [m["id"] for m in cached["movies"]]
    now[0] += 4 * 3600                                                # past the 3-hour new-release TTL
    fresh, _ = disc.candidates([inception], [])
    later = next(m for m in fresh["movies"] if m["id"] == LATER)
    assert "new_release" in later["discovery"]["sources"]
    assert LATER in ids(engine.recommend([inception], k=1000, extra=fresh))   # ranked, not filtered out


def test_cold_start_and_dislike_only_profiles(engine, inception, tmp_path):
    fake = FakeTMDB()
    _, disc = make(engine, tmp_path, fake)
    extra, report = disc.candidates([], [])
    assert report["profile"] == "cold-start" and report["seeds"] == 0
    assert {STARTER, TOP} <= {m["id"] for m in extra["movies"]}
    assert engine.recommend(k=100, extra=extra)["mode"] == "popular"

    extra, report = disc.candidates([], [HORROR])
    assert report["profile"] == "dislike-only"
    result = engine.recommend([], [HORROR], k=1000, extra=extra)            # whole eligible pool
    assert HORROR not in ids(result) and STARTER in ids(result)


def test_external_like_seeds_discovery_of_its_related_titles(engine, tmp_path):
    fake = FakeTMDB(related={DREAM: [EXT_REL]})
    catalog, disc = make(engine, tmp_path, fake)
    record = PreferenceFeatures(engine, catalog).resolve(DREAM)
    external = {"version": 1, "feature_version": engine.feature_version, "vector": record["vector"],
                "positive_count": 1, "negative_count": 0, "genres": [], "tags": [],
                "seeds": [{"key": f"tmdb:{DREAM}", "title": "Dream Thieves", "genres": record["taste"]["genres"],
                           "tags": record["taste"]["tags"], "vector": record["vector"]}]}
    extra, report = disc.candidates([DREAM], [], external)
    result = engine.recommend([DREAM], [], k=30, external_preferences=external, extra=extra)
    maze = next(m for m in result["items"] if m["id"] == EXT_REL)
    assert maze["because"]["title"] == "Dream Thieves" and DREAM not in ids(result)


def test_snapshot_only_results_are_unchanged_by_the_extension(engine, inception):
    base = engine.recommend([inception], k=30)
    assert ids(base) == ids(engine.recommend([inception], k=30, extra=None))
    assert not any(m.get("dynamic") for m in base["items"])
