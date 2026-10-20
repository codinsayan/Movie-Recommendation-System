"""S6 policy/export/API contracts. No third-party network dependency."""
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

import app as server
from export_static import export_playback
from release import REGISTRY, VERSION, frame_policy, playback_config, playback_script


def test_registry_is_fixed_https_and_has_known_adapters():
    assert {p["key"] for p in REGISTRY} == {"cinesrc", "vidlink", "vidsrc"}
    for provider in REGISTRY:
        assert provider["origin"].startswith("https://")
        assert provider["moviePath"].startswith("/")
        assert set(provider["permissions"]) == {"autoplay", "fullscreen", "picture-in-picture", "encrypted-media"}


def test_default_empty_order_and_invalid_provider_configuration(monkeypatch):
    monkeypatch.delenv("CINEMAGIC_PROVIDERS", raising=False)
    assert playback_config()["enabled"] == ["cinesrc", "vidlink", "vidsrc"]
    monkeypatch.setenv("CINEMAGIC_PROVIDERS", "")
    assert playback_config()["enabled"] == []
    assert playback_config("vidsrc, cinesrc")["enabled"] == ["vidsrc", "cinesrc"]
    for value in ("cinecs", "https://untrusted.test", "vidsrc,vidsrc", "CineSrc"):
        with pytest.raises(ValueError, match="registry IDs"):
            playback_config(value)


def test_disabled_origins_are_removed_but_trailers_still_work():
    policy = frame_policy(playback_config("vidsrc"))
    assert "https://vidsrc.sh" in policy
    assert "cinesrc.st" not in policy and "vidlink.pro" not in policy
    assert "https://www.youtube-nocookie.com" in frame_policy(playback_config(""))
    assert "*" not in policy


def test_api_and_bootstrap_use_same_policy_without_secrets(monkeypatch):
    config = playback_config("vidsrc")
    monkeypatch.setattr(server, "playback", config)
    monkeypatch.setenv("TMDB_READ_ACCESS_TOKEN", "private-test-token")
    client = TestClient(server.app)
    api = client.get("/api/playback")
    script = client.get("/playback-config.js")
    html = client.get("/")
    assert api.json() == config
    assert server.app.version == VERSION == config["release"]
    assert script.text == playback_script(config)
    assert "private-test-token" not in api.text + script.text
    assert script.headers["cache-control"] == "no-store"
    assert html.headers["content-security-policy"] == frame_policy(config)
    assert html.headers["cache-control"] == "no-cache"
    assert script.headers["x-content-type-options"] == "nosniff"
    assert html.text.index('src="playback-config.js"') < html.text.index('src="providers.js"')
    for private_path in ("/.env", "/backend/data/catalogue.sqlite3", "/backend/app.py"):
        assert client.get(private_path).status_code == 404


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_static_export_has_the_same_disabled_provider_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("CINEMAGIC_PROVIDERS", "vidlink")
    script = export_playback(tmp_path / "playback-config.js")
    result = subprocess.run([shutil.which("node"), "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(script)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == playback_config()
    assert "meta.httpEquiv='Content-Security-Policy'" in script.read_text()


def test_cache_uses_configured_writable_path_without_exposing_keys(tmp_path, monkeypatch):
    from catalog import Catalog
    cache = tmp_path / "nested" / "metadata.sqlite3"
    monkeypatch.setenv("CINEMAGIC_CACHE_PATH", str(cache))
    monkeypatch.setenv("TMDB_READ_ACCESS_TOKEN", "private-test-token")
    catalogue = Catalog.from_environment()
    assert catalogue.db_path == cache
    assert catalogue._read("release-probe") is None
    catalogue._write("release-probe", {"id": 45745})
    assert catalogue._read("release-probe")[0] == {"id": 45745}
    assert cache.is_file()
    assert b"private-test-token" not in cache.read_bytes()


def test_committed_static_policy_matches_default_registry():
    assert (ROOT / "frontend/playback-config.js").read_text(encoding="utf-8") == playback_script(playback_config("cinesrc,vidlink,vidsrc"))
