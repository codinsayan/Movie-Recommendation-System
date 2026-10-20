"""S5 ranking, bounded eligibility, API validation and Python/browser parity."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from app import app  # noqa: E402
from export_static import build_model  # noqa: E402
from build_tmdb_catalog import select_model_ids  # noqa: E402
from recommender import Recommender, load_dataset  # noqa: E402
from viewing import VIEWING_CONFIG, canonical_key  # noqa: E402

NOW = 1800000000000


def signal(key, **extra):
    return {"key": key, "watched_seconds": 180, "duration": 600, "plays": 1, "updated_at": NOW, **extra}


def evidence(signals=(), playback=()):
    return {"version": 1, "signals": list(signals), "playback": list(playback)}


def playback(key, **extra):
    return {"key": key, "provider": "cinesrc", "verified_at": NOW - 1000, "failed_at": 0, **extra}


def test_bounded_refresh_prioritizes_explicit_ids_without_growing_the_active_model():
    assert select_model_ids(list(range(1, 1001)), [900, 999, 900], 3) == [900, 999, 1]
    assert len(select_model_ids(list(range(1, 1001)))) == 500
    for included, budget in [([], 0), ([], 501), ([1, 2], 1), ([-1], 5), ([True], 5)]:
        with pytest.raises(ValueError):
            select_model_ids([], included, budget)


def test_api_accepts_supported_viewing_and_preserves_explicit_taste():
    body = {"use_viewing": True, "viewing": evidence([signal("curated:1")]), "k": 4}
    response = TestClient(app).post("/api/recommend", json=body)
    assert response.status_code == 200
    result = response.json()
    assert len(result["items"]) == 4
    assert result["mode"] == "viewing"
    assert result["watched_rows"][0]["source"]["id"] == 1
    assert result["taste"]["confidence"] == 0


@pytest.fixture(scope="module", params=["curated", "tmdb"])
def engine(request):
    return load_dataset(request.param)


def test_viewing_is_opt_in_and_remote_or_wrong_namespace_signals_are_history_only(engine):
    key = canonical_key(engine.movies[0])
    baseline = engine.recommend(k=12)
    assert engine.recommend(k=12, viewing=evidence([signal(key)])) == baseline
    wrong = ("curated:" if key.startswith("tmdb:") else "tmdb:") + str(engine.movies[0]["id"])
    for ignored in ["tmdb:2147483647", wrong]:
        assert engine.recommend(k=12, viewing=evidence([signal(ignored)]), use_viewing=True) == baseline
    assert engine.n == len(engine.movies)  # requests never append metadata to the model


def test_qualified_viewing_has_honest_explanations_and_a_bounded_contribution(engine):
    movie = engine.movies[0]
    key = canonical_key(movie)
    out = engine.recommend(viewing=evidence([signal(key, plays=100)]), use_viewing=True, k=12)
    assert out["mode"] == "viewing"
    assert movie["id"] not in {m["id"] for m in out["items"]}
    assert any(m["reason"] == f"Because you watched {movie['title']}" for m in out["items"])
    assert all(m["because"] is None or m["because"]["type"] == "watched" for m in out["items"])
    assert all(0 <= m["breakdown"]["viewing"] <= VIEWING_CONFIG["blend"] for m in out["items"])
    assert out["taste"]["confidence"] == 0
    assert out["watched_rows"][0]["source"]["id"] == movie["id"]


def test_watched_explanations_never_claim_unrelated_candidates(engine):
    engine = Recommender([{**m, "genres": [f"genre{i}"], "tags": [f"tag{i}"], "people": [],
                           "overview": f"word{i}", "tmdb_recs": []} for i, m in enumerate(engine.movies[:3])])
    source = engine.movies[0]
    relevance = .6 * engine.content_sim[0] + .4 * engine.collab_sim[0]
    unrelated = [canonical_key(m) for i, m in enumerate(engine.movies) if i != 0 and relevance[i] <= 0]
    out = engine.recommend(viewing=evidence([signal(canonical_key(source))]), use_viewing=True, eligible_keys=unrelated)
    assert len(out["items"]) == 2
    assert all(not row["items"] for row in out["watched_rows"])
    assert all(m["because"] is None and not m["reason"].startswith("Because you watched") for m in out["items"])


def test_duplicates_do_not_amplify_viewing_and_repeats_are_capped(engine):
    s = signal(canonical_key(engine.movies[0]))
    once = engine.recommend(viewing=evidence([s]), use_viewing=True)
    assert once == engine.recommend(viewing=evidence([s] * 100), use_viewing=True)
    assert engine.recommend(viewing=evidence([dict(s, plays=3)]), use_viewing=True) == engine.recommend(
        viewing=evidence([dict(s, plays=100)]), use_viewing=True)


@pytest.mark.parametrize("extra", [{"watched_seconds": 119}, {"watched_seconds": 179},
                                  {"watched_seconds": 601}, {"plays": 0}, {"duration": 0},
                                  {"watched_seconds": True}, {"watched_seconds": float("nan")}])
def test_unqualified_completion_or_invalid_measurements_never_become_preferences(engine, extra):
    s = signal(canonical_key(engine.movies[0]), completed=True, **extra)
    assert engine.recommend(viewing=evidence([s]), use_viewing=True) == engine.recommend()


def test_explicit_dislikes_win_and_source_errors_are_not_ratings(engine):
    first, second = engine.movies[:2]
    out = engine.recommend(liked=[first["id"], second["id"]], disliked=[first["id"]], use_viewing=True,
                           viewing=evidence([signal(canonical_key(first))], [playback(canonical_key(second), failed_at=NOW)]))
    assert out["watched_rows"] == []
    assert all(m["because"]["id"] == second["id"] for m in out["items"])
    baseline = engine.recommend(liked=[second["id"]], disliked=[first["id"]])
    assert out == baseline


def test_candidate_constraints_run_before_top_k_and_mmr(engine):
    keys = [canonical_key(m) for m in engine.movies[-20:]]
    watched = evidence([signal(canonical_key(engine.movies[0]))], [playback(key) for key in keys])
    out = engine.recommend(liked=[engine.movies[1]["id"]], viewing=watched, use_viewing=True,
                           recent_playback_only=True, now=NOW, k=12)
    assert len(out["items"]) == 12
    assert all(canonical_key(m) in keys for m in out["items"])
    assert len(out["watched_rows"][0]["items"]) <= 14
    assert all(canonical_key(m) in keys for m in out["watched_rows"][0]["items"])
    assert engine.recommend(eligible_keys=[], k=12)["items"] == []
    assert len(engine.recommend(eligible_keys=keys, k=12)["items"]) == 12


def test_recent_playback_has_freshness_provider_failure_and_future_clock_rules(engine):
    keys = [canonical_key(m) for m in engine.movies[:5]]
    reports = [playback(keys[0]), playback(keys[1], verified_at=NOW - VIEWING_CONFIG["freshnessMs"] - 1),
               playback(keys[2], failed_at=NOW), playback(keys[3], verified_at=NOW + 1),
               playback(keys[4], provider="vidsrc", verified_at=NOW - 2000),
               playback(keys[4], provider="cinesrc", failed_at=NOW)]
    out = engine.recommend(viewing=evidence(playback=reports), recent_playback_only=True, now=NOW)
    assert {canonical_key(m) for m in out["items"]} == {keys[0], keys[4]}
    # Duplicate old successes cannot revive a later failure for the same provider.
    out = engine.recommend(viewing=evidence(playback=[playback(keys[0]), playback(keys[0], failed_at=NOW)]),
                           recent_playback_only=True, now=NOW)
    assert out["items"] == []


INVALID = [
    {"viewing": {"version": 2}}, {"viewing": {"version": True}}, {"viewing": {"signals": []}},
    {"use_viewing": "false"}, {"recent_playback_only": 1}, {"eligible_keys": ["bad:1"]},
    {"viewing": evidence([signal("tmdb:1", watched_seconds="180")])},
    {"viewing": evidence([signal("tmdb:1", plays=True)])},
    {"viewing": evidence([signal("tmdb:1", duration=-1)])},
    {"viewing": evidence([signal("tmdb:1")] * 501)},
    {"viewing": evidence(playback=[playback("tmdb:1", provider="unknown")])},
    {"viewing": {"version": 1, "signals": None}},
    {"viewing": {"version": 1, "playback": None}},
    {"viewing": evidence([signal("tmdb:1", updated_at=None)])},
    {"viewing": evidence(playback=[playback("tmdb:1", verified_at=None)])},
]


@pytest.mark.parametrize("body", INVALID)
def test_api_rejects_invalid_viewing_contracts(body):
    assert TestClient(app).post("/api/recommend", json=body).status_code == 422


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_supported_viewing_has_full_python_js_parity_on_both_catalogues(engine, tmp_path):
    model = tmp_path / "model.json"
    model.write_text(json.dumps(build_model(engine)), encoding="utf-8")
    key = canonical_key(engine.movies[0])
    keys = [canonical_key(m) for m in engine.movies[-20:]]
    payload = evidence([signal(key)], [playback(k) for k in keys])
    cases = [
        {"viewing": payload, "use_viewing": True},
        {"viewing": payload, "use_viewing": True, "liked": [engine.movies[1]["id"]]},
        {"viewing": payload, "use_viewing": True, "mood": "space sci-fi"},
        {"viewing": payload, "use_viewing": True, "disliked": [engine.movies[0]["id"]]},
        {"viewing": payload, "use_viewing": True, "recent_playback_only": True},
        {"viewing": evidence(playback=[playback(key, failed_at=NOW)]), "recent_playback_only": True},
        {"viewing": payload, "use_viewing": True, "eligible_keys": keys},
        {"viewing": payload, "use_viewing": False, "eligible_keys": []},
        {"viewing": evidence([signal("tmdb:2147483647")]), "use_viewing": True},
        {"viewing": evidence([signal(key, plays=3)] * 2), "use_viewing": True},
    ]
    script = """
const E = require(process.argv[1]), Store = require(process.argv[2]);
const engine = new E(require(process.argv[3]));
const { cases, invalid, now } = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const results = cases.map(c => engine.recommend(c.liked, c.disliked, c.mood, 12, {...c, now}));
for (const bad of invalid) {
  let rejected = false;
  try { engine.handle('/api/recommend', bad); } catch(e) { rejected = e.status === 422; }
  if (!rejected) throw Error('Invalid contract accepted: ' + JSON.stringify(bad));
}
for (const [key, value] of Object.entries(Store.policy)) {
  if (engine.cfg.viewing[key] !== value) throw Error('Viewing policy mismatch: ' + key);
}
console.log(JSON.stringify(results));
"""
    proc = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "frontend/engine.js"),
                           str(ROOT / "frontend/viewing.js"), str(model)],
                          input=json.dumps({"cases": cases, "invalid": INVALID, "now": NOW}),
                          capture_output=True, text=True, encoding="utf-8", check=True)
    js = json.loads(proc.stdout)
    for case, browser in zip(cases, js):
        py = engine.recommend(**case, k=12, now=NOW)
        assert browser["mode"] == py["mode"]
        assert browser["taste"] == py["taste"]
        assert browser["watched_rows"] == py["watched_rows"]
        assert [m["id"] for m in browser["items"]] == [m["id"] for m in py["items"]]
        for a, b in zip(browser["items"], py["items"]):
            assert (a["match"], a["reason"], a["because"], a["shared"]) == (b["match"], b["reason"], b["because"], b["shared"])
            assert a["score"] == pytest.approx(b["score"], abs=1e-4)
            assert a["breakdown"] == pytest.approx(b["breakdown"], abs=1e-4)
