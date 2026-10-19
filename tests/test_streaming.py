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
