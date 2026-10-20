"""External explicit preferences: real fitted transforms, bounded resolution, API and browser parity."""
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
import app as server
from catalog import Catalog
from export_static import build_model
from features import feature_text
from preferences import PreferenceFeatures
from recommender import load_dataset


@pytest.fixture(scope="module")
def engine():
    return load_dataset("tmdb")


def external_movie(engine, index=0, mid=2000000001):
    return {**copy.deepcopy(engine.movies[index]), "id": mid, "tmdb_id": mid, "title": f"External {mid}",
            "full_details": True, "metadata_language": "en-US"}


def aggregate(engine, liked=(), disliked=()):
    vector = {}; genres = {}; tags = {}; seeds = []
    for record, weight in [*((r, 1) for r in liked), *((r, -.5) for r in disliked)]:
        for i, value in record["vector"]:
            vector[i] = vector.get(i, 0) + weight * value
        for name in record["taste"]["genres"]:
            genres[name] = genres.get(name, 0) + weight
        for name in record["taste"]["tags"]:
            tags[name] = tags.get(name, 0) + weight
        if weight > 0:
            seeds.append({"key": record["key"], "title": record["movie"]["title"], "genres": record["movie"]["genres"],
                          "tags": record["movie"]["tags"], "vector": record["vector"]})
    return {"version": 1, "feature_version": engine.feature_version, "vector": [[i, v] for i, v in vector.items() if v],
            "positive_count": len(liked), "negative_count": len(disliked),
            "genres": [{"name": n, "weight": w} for n, w in genres.items()],
            "tags": [{"name": n, "weight": w} for n, w in tags.items()], "seeds": seeds[-2:][::-1]}


def test_normalization_preserves_both_existing_snapshot_models():
    for source in ("curated", "tmdb"):
        e = load_dataset(source)
        for movie in e.movies:
            old = " ".join(movie["genres"] * 2 + movie["tags"] * 2 + movie.get("people", [])).lower() + " " + movie["overview"].lower()
            assert feature_text(movie) == old


def test_external_like_dislike_influence_without_refitting_or_matrix_growth(engine, monkeypatch):
    before = engine.recommend(k=100)
    shapes = [engine.X.shape, engine.content_sim.shape, engine.collab_sim.shape]
    monkeypatch.setattr(engine.vectorizer, "fit_transform", lambda *a: pytest.fail("No per-choice retraining"))
    movie = external_movie(engine)
    record = engine.resolve_preference(movie)
    assert record["status"] == "applied"
    target = engine.by_id[engine.movies[0]["id"]]
    pos = engine.recommend([movie["id"]], k=100, external_preferences=aggregate(engine, [record]))
    neg = engine.recommend([], [movie["id"]], k=100, external_preferences=aggregate(engine, disliked=[record]))
    assert [m["id"] for m in pos["items"]] != [m["id"] for m in before["items"]]
    p = {m["id"]: m for m in pos["items"]}; d = {m["id"]: m for m in neg["items"]}
    assert p[engine.movies[target]["id"]]["breakdown"]["content"] > .8
    assert engine.movies[target]["id"] not in d or d[engine.movies[target]["id"]]["breakdown"]["content"] < .1
    assert all(m["breakdown"]["collab"] == 0 for m in pos["items"])
    assert any(m["because"] and m["because"].get("key") == record["key"] for m in pos["items"])
    assert pos["taste"]["confidence"] == .2
    assert pos["because_rows"][0]["source"]["id"] == movie["id"]
    assert shapes == [engine.X.shape, engine.content_sim.shape, engine.collab_sim.shape]
    assert movie["id"] not in engine.by_id
    # Similar genres are penalized continuously, never categorically excluded.
    assert any(set(m["genres"]) & set(movie["genres"]) for m in neg["items"])
    assert engine.recommend(k=100) == before


def test_missing_vocabulary_is_unavailable_and_missing_keywords_can_use_overview(engine):
    base = external_movie(engine)
    empty = {**base, "genres": [], "tags": [], "people": [], "overview": "zzzzzzzz qqqqqqqq"}
    assert engine.resolve_preference(empty)["status"] == "unavailable"
    partial = {**base, "genres": [], "tags": [], "people": [], "overview": "space travel adventure"}
    assert engine.resolve_preference(partial)["status"] == "applied"


def test_external_related_shelf_is_independent_of_top_picks_filters(engine):
    record = engine.resolve_preference(external_movie(engine))
    disliked = engine.movies[0]["id"]
    request = {"liked": [record["movie"]["id"]], "disliked": [disliked], "external_preferences": aggregate(engine, [record])}
    broad = engine.recommend(**request)
    filtered = engine.recommend(**request, recent_playback_only=True, eligible_keys=[], mood="space")
    assert filtered["items"] == []
    assert filtered["because_rows"] == broad["because_rows"]
    assert filtered["because_rows"][0]["items"]
    assert all(m["id"] != disliked for m in filtered["because_rows"][0]["items"])


def test_resolution_route_uses_english_complete_metadata_and_cache(engine, tmp_path, monkeypatch):
    calls = []
    def upstream(request):
        calls.append(request)
        assert request.url.params["language"] == "en-US"
        assert "credits" in request.url.params["append_to_response"] and "keywords" in request.url.params["append_to_response"]
        return httpx.Response(200, json={"id": 2000000001, "title": "External", "overview": "Dreams and space travel",
            "genres": [{"name": "Science Fiction"}], "keywords": {"keywords": [{"name": "Time Travel"}]},
            "credits": {"crew": [{"job": "Director", "name": "Christopher Nolan"}], "cast": [{"name": "Léon Actor"}]}})
    catalog = Catalog(tmp_path / "features.sqlite3", token="never-leak-this", transport=httpx.MockTransport(upstream))
    service = PreferenceFeatures(engine, catalog)
    monkeypatch.setattr(server, "engine", engine); monkeypatch.setattr(server, "preference_features", service)
    client = TestClient(server.app)
    first = client.get("/api/preferences/tmdb/2000000001")
    assert first.status_code == 200 and first.json()["status"] == "applied"
    assert first.json()["movie"]["tags"] == ["time-travel"]
    assert first.json()["movie"]["people"] == ["christopher-nolan", "leon-actor"]
    second = client.get("/api/preferences/tmdb/2000000001")
    assert len(calls) == 1 and second.json()["vector"] == first.json()["vector"]
    assert "never-leak-this" not in first.text
    assert client.get("/api/preferences/tmdb/0").status_code == 422
    assert client.get(f"/api/preferences/tmdb/{engine.movies[0]['id']}").status_code == 422
    request = {"liked": [2000000001], "external_preferences": aggregate(engine, [first.json()])}
    assert client.post("/api/recommend", json=request).status_code == 200
    related = client.get("/api/movies/2000000001/similar?k=9")
    assert related.status_code == 200 and related.json()
    assert len(calls) == 1
    assert all(m["id"] != 2000000001 and m["similarity"] > 0 for m in related.json())
    assert client.get("/api/movies/2000000001/similar?k=31").status_code == 422
    request["external_preferences"]["feature_version"] = "obsolete"
    assert client.post("/api/recommend", json=request).status_code == 422


def test_invalid_feature_contracts_cannot_apply_old_or_conflicting_preferences(engine, monkeypatch, tmp_path):
    record = engine.resolve_preference(external_movie(engine))
    valid = {"liked": [record["movie"]["id"]], "external_preferences": aggregate(engine, [record])}
    invalid = []
    for version in (2, True, "1"):
        body = copy.deepcopy(valid); body["external_preferences"]["version"] = version; invalid.append(body)
    for vector in ([[len(engine.vectorizer.vocabulary_), 1]], [[0, 1], [0, .5]], [[True, 1]]):
        body = copy.deepcopy(valid); body["external_preferences"]["vector"] = vector; invalid.append(body)
    body = copy.deepcopy(valid); body["disliked"] = body["liked"]; invalid.append(body)
    body = copy.deepcopy(valid); body["liked"] = []; invalid.append(body)
    body = copy.deepcopy(valid); body["external_preferences"]["feature_version"] = "old-encoder"; invalid.append(body)
    monkeypatch.setattr(server, "engine", engine)
    client = TestClient(server.app)
    for body in invalid:
        assert client.post("/api/recommend", json=body).status_code == 422
    model = tmp_path / "model.json"; model.write_text(json.dumps(build_model(engine)), encoding="utf-8")
    if shutil.which("node"):
        script = """
const E=require(process.argv[1]),e=new E(require(process.argv[2])),cases=JSON.parse(require('fs').readFileSync(0,'utf8'));
for(const c of cases){let rejected=false;try{e.handle('/api/recommend',c)}catch(error){rejected=error.status===422}if(!rejected)throw Error('Invalid external contract accepted')}
"""
        subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "frontend/engine.js"), str(model)],
                       input=json.dumps(invalid), capture_output=True, text=True, check=True)


@pytest.mark.parametrize("status", [404, 429, 503])
def test_failed_feature_resolution_is_sanitized(engine, tmp_path, monkeypatch, status):
    catalog = Catalog(tmp_path / "cache.sqlite3", token="secret", transport=httpx.MockTransport(lambda r: httpx.Response(status)))
    monkeypatch.setattr(server, "engine", engine); monkeypatch.setattr(server, "preference_features", PreferenceFeatures(engine, catalog))
    response = TestClient(server.app).get("/api/preferences/tmdb/2000000001")
    assert response.status_code == (502 if status == 503 else status)
    assert "secret" not in response.text


@pytest.mark.skipif(shutil.which("node") is None, reason="node required")
def test_resolver_browser_lifecycle():
    proc = subprocess.run([shutil.which("node"), str(ROOT / "tests/js/test_preference_resolver.cjs")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node required")
def test_app_boot_restores_external_preferences_before_recommending(engine, tmp_path):
    model = tmp_path / "model.json"; model.write_text(json.dumps(build_model(engine)), encoding="utf-8")
    record = engine.resolve_preference(external_movie(engine))
    proc = subprocess.run([shutil.which("node"), str(ROOT / "tests/js/test_preference_boot.cjs"), str(model)],
                          input=json.dumps(record), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node required")
def test_external_python_browser_transform_and_ranking_parity(engine, tmp_path):
    movies = [external_movie(engine), external_movie(engine, 12, 2000000002),
              {**external_movie(engine, 20, 2000000003), "tags": ["Time Travel", "unfamiliar-keyword"],
               "people": None, "director": "Léon Éclair", "cast": ["Zoë Smith"], "overview": "éspace dreams space-travel. Constructor and hasOwnProperty."}]
    records = [engine.resolve_preference(m) for m in movies]
    configs = [([movies[0]["id"]], [], aggregate(engine, [records[0]]), None),
               ([], [movies[0]["id"]], aggregate(engine, disliked=[records[0]]), None),
               ([engine.movies[2]["id"], movies[0]["id"], movies[1]["id"]], [movies[2]["id"]], aggregate(engine, records[:2], [records[2]]), "space"),
               ([movies[2]["id"]], [], aggregate(engine, [records[2]]), None)]
    cases = [{"liked": l, "disliked": d, "mood": mood, "k": 30, "external_preferences": p} for l, d, p, mood in configs]
    # Qualified viewing remains capped below explicit preferences for new titles too.
    cases.append({**cases[0], "use_viewing": True, "now": 1000000000,
                  "viewing": {"version": 1, "signals": [{"key": f"tmdb:{engine.movies[10]['id']}", "watched_seconds": 180,
                              "duration": 600, "plays": 1, "updated_at": 999999999}], "playback": []}})
    cases.append({**cases[-1], "recent_playback_only": True, "eligible_keys": []})
    model = tmp_path / "model.json"; model.write_text(json.dumps(build_model(engine)), encoding="utf-8")
    script = """
const fs=require('fs'), Engine=require(process.argv[1]), Resolver=require(process.argv[3]), assert=require('assert/strict');
const e=new Engine(require(process.argv[2])); const input=JSON.parse(fs.readFileSync(0,'utf8'));
const records=input.movies.map(m=>e.resolvePreference(m));
const results=input.cases.map(c=>{
  const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)};
  const r=new Resolver(e.movies,{storage}); records.forEach(v=>r.records.set(v.key,{...v,resolved_at:Date.now()}));
  r.configure(e.metaInfo.preferences);r.sync(c.liked,c.disliked);r.persist();
  const restored=new Resolver(e.movies,{storage});restored.configure(e.metaInfo.preferences);restored.sync(c.liked,c.disliked);
  assert.deepEqual(restored.payload(),r.payload());
  return e.recommend(c.liked,c.disliked,c.mood,c.k,{...c,external_preferences:restored.payload()});
});
console.log(JSON.stringify({records,results,similar:records.map(r=>e.similarExternal(r,9))}));
"""
    proc = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "frontend/engine.js"), str(model), str(ROOT / "frontend/preference-resolver.js")],
                          input=json.dumps({"movies": movies, "cases": cases}), capture_output=True, text=True, encoding="utf-8", check=True)
    js = json.loads(proc.stdout)
    for py, browser in zip(records, js["records"]):
        assert py["movie"] == browser["movie"]
        assert py["taste"] == browser["taste"]
        assert np.array(py["vector"]) == pytest.approx(np.array(browser["vector"]), abs=1e-12)
    for record, browser in zip(records, js["similar"]):
        py = engine.similar_external(record, 9)
        assert [m["id"] for m in browser] == [m["id"] for m in py]
        assert [m["shared"] for m in browser] == [m["shared"] for m in py]
        assert [m["similarity"] for m in browser] == pytest.approx([m["similarity"] for m in py], abs=1e-4)
    for case, browser in zip(cases, js["results"]):
        py = engine.recommend(**case)
        assert browser["mode"] == py["mode"] and browser["taste"] == py["taste"]
        assert [m["id"] for m in browser["items"]] == [m["id"] for m in py["items"]]
        assert [[m["id"] for m in row["items"]] for row in browser["because_rows"]] == [[m["id"] for m in row["items"]] for row in py["because_rows"]]
        for a, b in zip(browser["items"], py["items"]):
            assert a["score"] == pytest.approx(b["score"], abs=1e-4)
            assert (a["because"], a["shared"], a["reason"]) == (b["because"], b["shared"], b["reason"])
            assert a["breakdown"] == pytest.approx(b["breakdown"], abs=1e-4)
            assert a["breakdown"].get("viewing", 0) <= .1
