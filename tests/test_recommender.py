import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from recommender import load_default  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    return load_default()


def genres_of(engine, items):
    return [set(m["genres"]) for m in items]


def test_cold_start_returns_popular(engine):
    out = engine.recommend(k=5)
    assert out["mode"] == "popular"
    ratings = [m["rating"] for m in out["items"]]
    assert ratings == sorted(ratings, reverse=True)


def test_liked_items_are_never_recommended(engine):
    liked = [1, 2, 3]
    out = engine.recommend(liked=liked, k=20)
    assert not {m["id"] for m in out["items"]} & set(liked)


def test_scifi_fan_gets_scifi(engine):
    out = engine.recommend(liked=[1, 2, 4], k=5)
    scifi = sum("Sci-Fi" in g for g in genres_of(engine, out["items"]))
    assert scifi >= 3
    assert out["items"][0]["because"] is not None


def test_dislike_pushes_genre_down(engine):
    base = engine.recommend(liked=[9], k=10)
    with_dislike = engine.recommend(liked=[9], disliked=[45, 46, 48], k=10)
    horror = lambda out: sum("Horror" in m["genres"] for m in out["items"])  # noqa: E731
    assert horror(with_dislike) <= horror(base)


def test_mood_search(engine):
    out = engine.recommend(mood="something scary", k=5)
    assert out["mode"] == "mood"
    assert sum("Horror" in m["genres"] for m in out["items"]) >= 3


def test_cozy_mood(engine):
    out = engine.recommend(mood="cozy and heartwarming", k=5)
    assert any("cozy" in m["tags"] or "heartwarming" in m["tags"] for m in out["items"])


def test_match_scores_in_range(engine):
    for m in engine.recommend(liked=[15, 16], k=10)["items"]:
        assert 55 <= m["match"] <= 99


def test_similar_excludes_self(engine):
    sims = engine.similar(16, k=5)
    assert 16 not in {m["id"] for m in sims}
    assert any("Animation" in m["genres"] for m in sims)


def test_taste_profile(engine):
    taste = engine.recommend(liked=[45, 46, 47])["taste"]
    assert taste["genres"][0]["name"] == "Horror"
    assert taste["genres"][0]["weight"] == 1.0


def test_unknown_ids_are_ignored(engine):
    out = engine.recommend(liked=[9999], k=3)
    assert out["mode"] == "popular"


def test_mood_keys_match_word_starts_only(engine):
    # "war" must not fire inside "heartwarming"; "inspir" should still match "inspiring".
    assert "world-war-ii" not in engine.expand_mood("cozy and heartwarming")
    assert "inspirational" in engine.expand_mood("something inspiring")
