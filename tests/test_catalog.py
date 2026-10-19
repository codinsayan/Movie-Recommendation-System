"""Discovery/cache behavior uses mock TMDB responses; no key or network required."""
import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import app as server
from catalog import Catalog, CatalogError

MOVIE = {"id": 47533, "title": "Sintel", "original_title": "Sintel original", "original_language": "nl",
         "overview": "An independent short.", "release_date": "2010-09-27", "genre_ids": [16, 14],
         "genres": [{"name": "Animation"}, {"name": "Fantasy"}], "vote_average": 7.4,
         "alternative_titles": {"titles": [{"title": "Alternate title"}]}, "credits": {"cast": [{"name": "Actor"}]}}


def make_catalog(tmp_path, handler, **kwargs):
    return Catalog(tmp_path / "cache.sqlite3", token="test-secret", transport=httpx.MockTransport(handler), **kwargs)


def search_response(items=None, page=1):
    return httpx.Response(200, json={"results": items if items is not None else [MOVIE], "page": page, "total_pages": 2, "total_results": 21})


def test_search_cache_migration_and_no_model_growth(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-secret"
        assert request.url.params["include_adult"] == "false"
        return search_response()
    catalogue = make_catalog(tmp_path, handler)
    first = catalogue.search("Sintel", 1, "en-US", set())
    second = catalogue.search("  sintel  ", 1, "en-US", {47533})
    assert len(requests) == 1
    assert first["items"][0]["in_model"] is False
    assert second["items"][0]["in_model"] is True  # membership is not cached
    assert second["cached"] is True and second["stale"] is False
    assert first["items"][0]["original_language"] == "nl"
    with sqlite3.connect(catalogue.db_path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_detail_normalization_and_language_cache_separation(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=MOVIE)
    catalogue = make_catalog(tmp_path, handler)
    first = catalogue.movie(47533, "hi-IN", set())
    catalogue.movie(47533, "en-US", set())
    catalogue.movie(47533, "hi-IN", set())
    assert len(requests) == 2
    assert first["full_details"] is True
    assert first["alternative_titles"] == ["Alternate title"]
    assert first["cast"] == ["Actor"]
    assert first["metadata_language"] == "hi-IN"


@pytest.mark.parametrize("status", [429, 401, 503])
def test_expired_cache_survives_upstream_errors(tmp_path, status):
    now = [0]
    response = [search_response()]
    catalogue = make_catalog(tmp_path, lambda _: response[0], clock=lambda: now[0])
    catalogue.search("Sintel", 1, "en-US", set())
    now[0] = 7200
    response[0] = httpx.Response(status, headers={"Retry-After": "5"})
    stale = catalogue.search("Sintel", 1, "en-US", set())
    assert stale["stale"] is True and stale["cached"] is True


def test_timeout_is_sanitized_and_cache_works_without_credentials(tmp_path):
    def timeout(request):
        raise httpx.ReadTimeout("request contained test-secret", request=request)
    catalogue = make_catalog(tmp_path, timeout)
    with pytest.raises(CatalogError) as error:
        catalogue.search("Sintel", 1, "en-US", set())
    assert error.value.status == 502
    assert "test-secret" not in str(error.value)
    catalogue = make_catalog(tmp_path, lambda _: search_response(), clock=lambda: 0)
    catalogue.search("Sintel", 1, "en-US", set())
    offline = Catalog(catalogue.db_path, clock=lambda: 7200)
    assert offline.search("Sintel", 1, "en-US", set())["stale"] is True


def test_rate_limit_and_not_found_routes(tmp_path, monkeypatch):
    current = [429]
    catalogue = make_catalog(tmp_path, lambda _: httpx.Response(current[0], headers={"Retry-After": "10"}))
    monkeypatch.setattr(server, "catalog", catalogue)
    client = TestClient(server.app)
    response = client.get("/api/search", params={"q": "Sintel"})
    assert response.status_code == 429 and response.headers["retry-after"] == "10"
    assert "test-secret" not in response.text
    current[0] = 404
    assert client.get("/api/movies/47533").status_code == 404


def test_api_validation_capability_and_unindexed_details(tmp_path, monkeypatch):
    catalogue = make_catalog(tmp_path, lambda request: search_response() if request.url.path.endswith("/search/movie") else httpx.Response(200, json=MOVIE))
    monkeypatch.setattr(server, "catalog", catalogue)
    client = TestClient(server.app)
    before = server.engine.n
    assert client.get("/api/capabilities").json()["catalogue"]["live_search"] is True
    for params in ({"q": " "}, {"q": "a", "page": 501}, {"q": "a", "page": 0}, {"q": "a", "language": "../secrets"}):
        assert client.get("/api/search", params=params).status_code == 422
    result = client.get("/api/search", params={"q": "Sintel", "language": "hi-IN"})
    assert result.status_code == 200 and result.json()["items"][0]["in_model"] is False
    detail = client.get("/api/movies/47533").json()
    assert detail["tmdb_id"] == 47533 and detail["source"] == "tmdb" and detail["in_model"] is False
    assert server.engine.n == before
    assert client.get("/api/movies/47533/similar").status_code == 404


def test_missing_credentials_does_not_break_existing_catalogue(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "catalog", Catalog(tmp_path / "cache.sqlite3"))
    client = TestClient(server.app)
    assert client.get("/api/capabilities").json()["catalogue"]["live_search"] is False
    assert client.get("/api/search", params={"q": "Sintel"}).status_code == 503
    assert client.get("/api/movies").status_code == 200
    assert client.post("/api/recommend", json={"liked": [1]}).status_code == 200


def test_wrong_identity_and_broken_payload_are_not_successful_metadata(tmp_path):
    catalogue = make_catalog(tmp_path, lambda _: httpx.Response(200, json={**MOVIE, "id": 123}))
    with pytest.raises(CatalogError):
        catalogue.movie(47533, "en-US", set())
    catalogue = make_catalog(tmp_path, lambda _: httpx.Response(200, json={"results": "broken"}))
    with pytest.raises(CatalogError):
        catalogue.search("anything", 1, "en-US", set())
