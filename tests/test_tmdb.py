"""TMDB integration: payload normalisation, graph-based CF, weighted rating, JS parity.

No network or API key needed: everything runs on fixtures.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_tmdb_catalog import normalize_movie, pick_trailer, slug  # noqa: E402
from export_static import build_model  # noqa: E402
from recommender import Recommender, weighted_rating  # noqa: E402

SAMPLE = {
    "id": 27205, "title": "Inception", "release_date": "2010-07-15", "poster_path": "/p.jpg", "backdrop_path": "/b.jpg",
    "overview": "Cobb steals secrets from dreams.", "tagline": "Your mind is the scene of the crime.",
    "vote_average": 8.369, "vote_count": 37000, "runtime": 148,
    "genres": [{"name": "Action"}, {"name": "Science Fiction"}, {"name": "TV Movie"}],
    "keywords": {"keywords": [{"name": "dream"}, {"name": "subconscious mind"}, {"name": "Heist"}]},
    "credits": {
        "cast": [{"name": "Leonardo DiCaprio"}, {"name": "Joseph Gordon-Levitt"}, {"name": "Elliot Page"}, {"name": "Tom Hardy"}],
        "crew": [{"name": "Hans Zimmer", "job": "Original Music Composer"}, {"name": "Christopher Nolan", "job": "Director"}],
    },
    "videos": {"results": [
        {"site": "YouTube", "type": "Teaser", "key": "teaser", "official": True, "iso_639_1": "en"},
        {"site": "YouTube", "type": "Trailer", "key": "trailer", "official": True, "iso_639_1": "en"},
    ]},
    "recommendations": {"results": [{"id": 155}, {"id": 157336}]},
}


def test_normalize_movie():
    m = normalize_movie(SAMPLE)
    assert m["genres"] == ["Action", "Sci-Fi"]  # mapped, TV Movie dropped
    assert m["tags"] == ["dream", "subconscious-mind", "heist"]
    assert m["people"] == ["christopher-nolan", "leonardo-dicaprio", "joseph-gordon-levitt", "elliot-page"]
    assert m["director"] == "Christopher Nolan"
    assert m["trailer"] == "trailer"
    assert m["rating"] == 8.4 and m["votes"] == 37000 and m["year"] == 2010
    assert m["poster"].endswith("/w342/p.jpg") and m["backdrop"].endswith("/w1280/b.jpg")
    assert m["tmdb_recs"] == [155, 157336]


def test_normalize_skips_incomplete():
    assert normalize_movie({**SAMPLE, "poster_path": None}) is None
    assert normalize_movie({**SAMPLE, "release_date": ""}) is None


def test_slug_and_trailer_helpers():
    assert slug("Zoë Saldaña") == "zoe-saldana"
    assert pick_trailer([{"site": "Vimeo", "type": "Trailer", "key": "x"}]) is None


def graph_catalog():
    """Two audience clusters (ids 1-8 and 11-18) that share genres, so only the graph separates them."""
    movies = []
    for cluster, base in ((0, 1), (1, 11)):
        for k in range(8):
            mid = base + k
            neighbours = [base + (k + d) % 8 for d in (1, 2, 3)]
            movies.append({
                "id": mid, "title": f"Film {mid}", "year": 2000 + k, "genres": ["Drama", "Thriller"],
                "tags": [f"theme-{k % 4}", "suspense", f"motif-{mid}"], "people": [f"director-{cluster}-{k % 2}"],
                "overview": f"A story about secrets in chapter {mid}.", "rating": 6.0 + mid / 10, "votes": 300 * mid,
                "tmdb_recs": neighbours,
            })
    return movies


@pytest.fixture(scope="module")
def graph_engine():
    return Recommender(graph_catalog())


def test_graph_collaborative_filtering(graph_engine):
    assert graph_engine.collab_source == "tmdb-graph"
    assert graph_engine.meta()["graph_edges"] > 0
    out = graph_engine.recommend(liked=[1, 2], k=4)
    # The co-recommendation graph should keep picks inside the liked film's audience cluster.
    assert sum(m["id"] < 10 for m in out["items"]) >= 3


def test_people_are_explained(graph_engine):
    out = graph_engine.recommend(liked=[1], k=8)
    assert any("director-0-1" in m["shared"] or "director-0-0" in m["shared"] for m in out["items"])


def test_weighted_rating_shrinks_low_vote_films():
    films = [{"rating": 9.5, "votes": 10}, {"rating": 8.5, "votes": 100000}, {"rating": 6.0, "votes": 5000}]
    wr = weighted_rating(films)
    assert wr[1] > wr[0]  # a 9.5 with 10 votes is less trustworthy than an 8.5 with 100k


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_graph_engine_js_parity(graph_engine, tmp_path):
    model = tmp_path / "model.json"
    model.write_text(json.dumps(build_model(graph_engine)), encoding="utf-8")
    script = (
        "const E=require(process.argv[1]);const e=new E(require(process.argv[2]));"
        "console.log(JSON.stringify([e.recommend([1,2],[13],null,6), e.recommend([],[],'secrets suspense',5), e.similar(5,4)]))"
    )
    js = json.loads(subprocess.run(
        ["node", "-e", script, str(ROOT / "frontend" / "engine.js"), str(model)],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout)
    py = [graph_engine.recommend([1, 2], [13], None, 6), graph_engine.recommend([], [], "secrets suspense", 5)]
    for a, b in zip(js[:2], py):
        assert [m["id"] for m in a["items"]] == [m["id"] for m in b["items"]]
        assert [m["match"] for m in a["items"]] == [m["match"] for m in b["items"]]
    assert [m["id"] for m in js[2]] == [m["id"] for m in graph_engine.similar(5, 4)]
