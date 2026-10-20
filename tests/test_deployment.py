"""S7 deployment contracts and false-positive smoke-check prevention; offline."""
import json
from pathlib import Path
import sys

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from app import app
from release import VERSION
from smoke_deployment import SmokeError, base_url, check


def test_blueprint_preserves_full_project_and_private_runtime_contract():
    config = yaml.safe_load((ROOT / "render.yaml").read_text())
    assert len(config["services"]) == 1 and "databases" not in config
    service = config["services"][0]
    assert (service["type"], service["runtime"], service["plan"]) == ("web", "python", "free")
    assert service["branch"] == "main" and service.get("rootDir", ".") == "."
    assert service["autoDeployTrigger"] == "off"  # Quote YAML 1.1's boolean-like word.
    assert service["healthCheckPath"] == "/api/health" and "disk" not in service
    assert "requirements-runtime.txt" in service["buildCommand"] and "export_static.py" in service["buildCommand"]
    assert "build_tmdb" not in service["buildCommand"]
    assert "--host 0.0.0.0" in service["startCommand"] and "--port $PORT" in service["startCommand"]
    assert "--workers 1" in service["startCommand"] and "run.py" not in service["startCommand"]
    env = {item["key"]: item for item in service["envVars"]}
    assert env["TMDB_READ_ACCESS_TOKEN"] == {"key": "TMDB_READ_ACCESS_TOKEN", "sync": False}
    assert env["CINEMAGIC_DATASET"]["value"] == "tmdb"
    assert env["CINEMAGIC_CACHE_PATH"]["value"].startswith("/tmp/")
    assert env["CINEMAGIC_PROVIDERS"]["value"] == "cinesrc,vidlink,vidsrc"
    assert (ROOT / ".python-version").read_text().strip() == "3.13.5"
    runtime = (ROOT / "requirements-runtime.txt").read_text()
    assert "pytest" not in runtime and "PyYAML" not in runtime
    assert all("==" in line for line in runtime.splitlines() if line and not line.startswith("#"))


def test_deployment_identity_exposes_only_public_revision(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("TMDB_READ_ACCESS_TOKEN", "private-test-token")
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    assert client.get("/api/deployment").json() == {"release": VERSION, "commit": None}
    monkeypatch.setenv("RENDER_GIT_COMMIT", "A" * 40)
    assert client.get("/api/deployment").json() == {"release": VERSION, "commit": "a" * 40}
    monkeypatch.setenv("RENDER_GIT_COMMIT", "not-a-sha-private-test-token")
    assert "private-test-token" not in client.get("/api/deployment").text
    assert client.get("/api/deployment").json()["commit"] is None


@pytest.mark.parametrize("url", ["https://user:secret@example.com", "https://example.com/?token=secret",
                                  "https://example.com/subpath", "http://example.com", "file:///tmp/app"])
def test_smoke_rejects_credential_urls_wrong_origins_and_insecure_hosted_urls(url):
    with pytest.raises(SmokeError):
        base_url(url)


def smoke_fixture():
    movies = [{"id": 1, "tmdb_id": 1, "source": "tmdb"}, {"id": 2, "tmdb_id": 2, "source": "tmdb"}]
    meta = {"movies": 2, "preferences": {"feature_version": "fixture-v1"}}
    records = {
        "/api/health": {"status": "ok"},
        "/api/deployment": {"release": VERSION, "commit": "a" * 40},
        "/api/playback": {"release": VERSION, "enabled": ["cinesrc"]},
        "/api/movies": movies, "/api/meta": meta,
        "/data/model.json": {"version": 2, "movies": movies, "meta": meta},
        "/api/capabilities": {"catalogue": {"snapshot_source": "tmdb", "live_search": True}},
        "/api/recommend": {"items": [{"id": 3}], "discovery": {"status": "ok", "pool": 1}},
        "/api/movies/45745?language=en-US": {"id": 45745, "full_details": True},
        "/api/preferences/tmdb/45745": {"key": "tmdb:45745", "status": "applied", "feature_version": "fixture-v1",
                                       "vector": [[0, 1.0]], "movie": {"title": "Sintel"}, "taste": {"genres": [], "tags": []}},
    }
    for page in (1, 2):
        records[f"/api/search?q=batman&page={page}&language=en-US"] = {"page": page, "items": [{"id": 3}]}
    calls = []

    def fetch(path, body=None):
        calls.append((path, body))
        if path.startswith(("/.env", "/backend/")):
            return 404, {}, b""
        if path in records:
            return 200, {"content-type": "application/json"}, json.dumps(records[path]).encode()
        if path == "/":
            return 200, {"content-security-policy": "frame-src 'self'"}, b'<script src="playback-config.js"></script><script src="providers.js"></script><script src="app.js"></script>'
        if path == "/playback-config.js":
            return 200, {"content-type": "text/javascript"}, b"globalThis.CinemagicPlaybackConfig={};"
        return 200, {}, b"fixture asset"

    return records, calls, fetch


def test_smoke_checks_exact_revision_and_can_run_without_live_metadata():
    _, calls, fetch = smoke_fixture()
    report = check("https://example.com/", expected_commit="a" * 40, fetch=fetch)
    assert report["catalogue_movies"] == 2 and report["live"] is False
    assert not any(path.startswith("/api/search") for path, _ in calls)
    with pytest.raises(SmokeError, match="Git revision"):
        check("https://example.com", expected_commit="b" * 40, fetch=fetch)


def test_smoke_rejects_static_html_health_and_mismatched_model():
    records, _, fetch = smoke_fixture()
    def static_fallback(path, body=None):
        return (200, {"content-type": "text/html"}, b"loading page") if path == "/api/health" else fetch(path, body)
    with pytest.raises(SmokeError, match="JSON content type"):
        check("http://127.0.0.1:8765", fetch=static_fallback)
    records["/data/model.json"]["movies"] = []
    with pytest.raises(SmokeError, match="Static model"):
        check("http://127.0.0.1:8765", fetch=fetch)


def test_credential_free_smoke_requires_explicit_search_unavailability():
    records, _, fetch = smoke_fixture()
    records["/api/capabilities"]["catalogue"]["live_search"] = False
    def without_credentials(path, body=None):
        return (503, {}, b"") if path.startswith("/api/search") else fetch(path, body)
    report = check("https://example.com", fetch=without_credentials)
    assert report["live_search_configured"] is False
    with pytest.raises(SmokeError, match="Missing credentials"):
        check("https://example.com", fetch=fetch)


def test_live_smoke_applies_external_preference_and_rejects_partial_discovery():
    records, calls, fetch = smoke_fixture()
    check("https://example.com", live=True, fetch=fetch)
    payload = next(body for path, body in reversed(calls) if path == "/api/recommend")
    assert payload["external_preferences"]["positive_count"] == 1 and 45745 in payload["liked"]
    records["/api/recommend"]["discovery"]["status"] = "partial"
    with pytest.raises(SmokeError, match="not partial"):
        check("https://example.com", live=True, fetch=fetch)
