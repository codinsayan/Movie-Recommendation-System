"""Offline playback contracts and identity isolation; no external video dependency."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from recommender import load_dataset  # noqa: E402


def test_dataset_identity_is_explicit():
    curated = load_dataset("curated")
    assert all(m["source"] == "curated" and m["tmdb_id"] is None for m in curated.movies)
    tmdb = load_dataset("tmdb")
    assert all(m["source"] == "tmdb" and m["tmdb_id"] == m["id"] for m in tmdb.movies)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_player_and_viewing_contracts():
    proc = subprocess.run(
        [shutil.which("node"), str(ROOT / "tests/js/test_streaming.cjs")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_catalogue_browser_contracts():
    proc = subprocess.run(
        [shutil.which("node"), str(ROOT / "tests/js/test_catalogue.cjs")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_restored_preferences_reproduce_recommendations(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    from export_static import export

    model = export(tmp_path / "model.json")
    script = """
const assert = require('node:assert/strict');
const Engine = require(process.argv[1]);
const Preferences = require(process.argv[2]);
const engine = new Engine(require(process.argv[3]));
const saved = new Map();
const storage = {getItem: key => saved.get(key), setItem: (key, value) => saved.set(key, value)};
const before = {liked: [1,2], disliked: [45], mood: 'space'};
new Preferences(storage).save('curated', before);
const restored = new Preferences(storage).load('curated');
const recommend = p => engine.recommend(p.liked, p.disliked, p.mood, 12);
assert.deepEqual(recommend(restored), recommend(before));
assert.equal(recommend(restored).mode, 'personal');
"""
    proc = subprocess.run(
        [shutil.which("node"), "-e", script, str(ROOT / "frontend/engine.js"),
         str(ROOT / "frontend/preferences.js"), str(model)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
