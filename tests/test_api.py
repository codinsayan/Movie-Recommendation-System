import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_movies_and_frontend_served():
    assert len(client.get("/api/movies").json()) == 60
    assert "Cinemagic" in client.get("/").text


def test_every_movie_has_a_cached_poster():
    frontend = Path(__file__).resolve().parent.parent / "frontend"
    for m in client.get("/api/movies").json():
        assert m.get("poster"), m["title"]
        assert (frontend / m["poster"]).is_file(), m["poster"]


def test_score_whole_catalogue():
    body = client.post("/api/recommend", json={"liked": [1], "k": 100}).json()
    assert len(body["items"]) == 59


def test_recommend_endpoint():
    res = client.post("/api/recommend", json={"liked": [1, 2], "mood": "space", "k": 4})
    body = res.json()
    assert res.status_code == 200
    assert len(body["items"]) == 4
    assert body["mode"] == "personal"
    assert {"match", "reason", "breakdown", "shared"} <= body["items"][0].keys()


def test_recommend_validates_k():
    assert client.post("/api/recommend", json={"k": 500}).status_code == 422


def test_similar_404():
    assert client.get("/api/movies/9999/similar").status_code == 404
