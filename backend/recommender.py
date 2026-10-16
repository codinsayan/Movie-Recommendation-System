"""Hybrid movie recommender.

Combines three signals into one score:
  * content    - TF-IDF over genres, tags, people and overview (what the movie *is*)
  * collab     - item-item collaborative filtering (what *people* co-enjoy), learnt from either
                 TMDB's audience-driven recommendation graph or a simulated ratings matrix
  * quality    - vote-weighted rating (a gentle prior towards good, well-known movies)

The final list is re-ranked with Maximal Marginal Relevance (MMR) so it stays diverse.
See docs/ALGORITHM.md for the full write-up.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

DATA_DIR = Path(__file__).parent / "data"
DATASETS = {"curated": DATA_DIR / "movies.json", "tmdb": DATA_DIR / "tmdb_movies.json"}
DATA_PATH = DATASETS["curated"]

WEIGHTS = {"content": 0.55, "collab": 0.35, "quality": 0.10}
MOOD_WEIGHTS = {"content": 0.80, "collab": 0.0, "quality": 0.20}
DISLIKE_PENALTY = 0.5
MOOD_BOOST = 1.5
MMR_LAMBDA = 0.75

# Everyday words -> vocabulary the catalogues actually use. Each key matches at the
# start of a word ("inspir" -> inspiring, but "war" never fires inside "heartwarming").
# Values mix curated tags, TMDB keywords and genre names; terms missing from the
# active catalogue's vocabulary are simply ignored by TF-IDF.
MOOD_SYNONYMS = {
    "cozy": "cozy heartwarming feel-good whimsical family animation comedy friendship kindness joyful cheerful playful holiday",
    "cosy": "cozy heartwarming feel-good family animation comedy friendship kindness joyful",
    "comfort": "cozy heartwarming feel-good family comedy friendship kindness",
    "chill": "cozy quiet feel-good comedy friendship",
    "wholesome": "heartwarming feel-good family friendship kindness",
    "funny": "comedy quirky witty fun amused dark-comedy absurd parody playful",
    "laugh": "comedy fun witty amused parody spoof absurd",
    "comedy": "comedy fun amused",
    "scary": "horror scary suspense suspenseful demon ghost haunted-house supernatural slasher",
    "scare": "horror scary suspense demon ghost haunted-house supernatural",
    "spooky": "horror scary supernatural ghost haunted-house demon halloween witch curse",
    "horror": "horror scary demon ghost slasher",
    "cry": "emotional bittersweet drama sadness melancholy tragedy loss-of-loved-one dying-and-death grief sentimental",
    "sad": "emotional bittersweet drama sadness melancholy tragedy loss-of-loved-one dying-and-death grief",
    "tear": "emotional bittersweet drama sadness melancholy tragedy loss-of-loved-one",
    "emotional": "emotional heartwarming drama sadness melancholy sentimental loss-of-loved-one",
    "romantic": "romance love romantic falling-in-love first-love love-of-one-s-life love-triangle",
    "romance": "romance love romantic falling-in-love love-of-one-s-life",
    "love": "romance love romantic love-of-one-s-life",
    "date": "romance feel-good witty romantic love comedy",
    "mind": "mind-bending cerebral twist psychological-thriller nonlinear-timeline dreams time-travel",
    "smart": "cerebral clever psychological-thriller investigation",
    "think": "cerebral mind-bending psychological-thriller dreams",
    "twist": "twist psychological psychological-thriller nonlinear-timeline",
    "action": "action adrenaline fight martial-arts",
    "exciting": "adrenaline action thriller excited suspenseful race-against-time",
    "thrill": "thriller suspense suspenseful psychological-thriller intense",
    "epic": "epic adventure heroic quest battle fantasy",
    "hero": "superhero heroic hero super-power",
    "superhero": "superhero based-on-comic super-power",
    "space": "space sci-fi space-travel spacecraft alien space-opera",
    "future": "sci-fi cyberpunk ai future futuristic dystopia artificial-intelligence-a-i android",
    "dark": "dark gritty dark-comedy psychopath serial-killer",
    "kid": "family animation cartoon",
    "family": "family animation heartwarming parent-child-relationship",
    "inspir": "uplifting inspiring mentor inspirational admiring based-on-true-story",
    "motivat": "uplifting inspiring ambition inspirational",
    "magic": "magical fantasy whimsical magic witch fairy-tale school-of-witchcraft",
    "music": "music musical singer dance",
    "history": "history true-story based-on-true-story historical-fiction period-drama biography",
    "true": "true-story based-on-true-story biography",
    "war": "war intense world-war-ii army battle",
    "heist": "heist robbery con-artist caper",
    "revenge": "revenge vigilante assassin",
    "christmas": "holiday christmas family",
    "zombie": "zombie post-apocalyptic-future survival horror",
    "anime": "animation japanese",
    "classic": "classic iconic",
}

TOKEN_PATTERN = r"(?u)\b[a-z0-9][a-z0-9\-]+\b"


def _tokens(movie: dict) -> set[str]:
    return {g.lower() for g in movie["genres"]} | set(movie["tags"]) | set(movie.get("people", []))


def weighted_rating(movies: list[dict]) -> np.ndarray:
    """IMDb-style Bayesian rating: shrink films with few votes towards the mean."""
    r = np.array([m["rating"] for m in movies], dtype=float)
    if not all("votes" in m for m in movies):
        return r
    v = np.array([m["votes"] for m in movies], dtype=float)
    prior = float(np.median(v))
    return v / (v + prior) * r + prior / (v + prior) * r.mean()


def graph_vectors(movies: list[dict]) -> tuple[np.ndarray, int]:
    """Item vectors from TMDB's recommendation graph.

    A[i, j] = 1 when TMDB recommends j for i (or i for j), plus a self-loop so a
    direct link also counts. Cosine between rows = how much two films share
    their audience-driven neighbourhood.
    """
    index = {m["id"]: i for i, m in enumerate(movies)}
    A = np.eye(len(movies))
    for i, m in enumerate(movies):
        for rec_id in m.get("tmdb_recs", []):
            j = index.get(rec_id)
            if j is not None and j != i:
                A[i, j] = A[j, i] = 1.0
    edges = int((A.sum() - len(movies)) // 2)
    return normalize(A), edges


def _minmax(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Scale the masked entries of x to [0, 1]; others become 0."""
    out = np.zeros_like(x)
    if not mask.any():
        return out
    lo, hi = x[mask].min(), x[mask].max()
    out[mask] = (x[mask] - lo) / (hi - lo) if hi > lo else 1.0
    return out


def simulate_ratings(movies: list[dict], n_users: int = 600, seed: int = 42) -> np.ndarray:
    """Generate a realistic, sparse user x movie 1-5 ratings matrix (0 = unwatched).

    Each synthetic user has a sparse genre taste (Dirichlet). They are more likely to
    watch and to rate highly the movies matching that taste. Deterministic via seed.
    """
    rng = np.random.default_rng(seed)
    genres = sorted({g for m in movies for g in m["genres"]})
    g_index = {g: i for i, g in enumerate(genres)}
    G = np.zeros((len(movies), len(genres)))
    for i, m in enumerate(movies):
        for g in m["genres"]:
            G[i, g_index[g]] = 1.0
    G /= G.sum(axis=1, keepdims=True)

    taste = rng.dirichlet(np.full(len(genres), 0.3), size=n_users)
    affinity = taste @ G.T
    affinity /= affinity.max(axis=1, keepdims=True)

    quality = np.array([m["rating"] for m in movies])
    quality = (quality - quality.mean()) / quality.std()

    watched = rng.random(affinity.shape) < (0.06 + 0.5 * affinity)
    raw = 1 + 4 * affinity + 0.35 * quality + rng.normal(0, 0.6, affinity.shape)
    return np.clip(np.rint(raw), 1, 5) * watched


class Recommender:
    def __init__(self, movies: list[dict], ratings: np.ndarray | None = None):
        self.movies = movies
        self.by_id = {m["id"]: i for i, m in enumerate(movies)}
        n = len(movies)

        # Content model: genres and tags count double, they are the strongest signal.
        docs = [
            " ".join(m["genres"] * 2 + m["tags"] * 2 + m.get("people", [])).lower() + " " + m["overview"].lower()
            for m in movies
        ]
        self.vectorizer = TfidfVectorizer(
            token_pattern=TOKEN_PATTERN, stop_words="english", sublinear_tf=True
        )
        self.X = normalize(self.vectorizer.fit_transform(docs)).toarray()
        self.content_sim = self.X @ self.X.T
        np.fill_diagonal(self.content_sim, 0)

        # Collaborative model: item vectors C whose cosine is the item-item similarity.
        self.ratings = None
        if ratings is None and all("tmdb_recs" in m for m in movies):
            self.collab_source = "tmdb-graph"
            self.C, self.graph_edges = graph_vectors(movies)
        else:
            # Adjusted cosine over a user x movie ratings matrix (simulated unless given).
            self.collab_source = "ratings" if ratings is not None else "simulated"
            self.ratings = simulate_ratings(movies) if ratings is None else ratings
            watched = self.ratings > 0
            counts = np.maximum(watched.sum(axis=1, keepdims=True), 1)
            user_mean = self.ratings.sum(axis=1, keepdims=True) / counts
            centered = np.where(watched, self.ratings - user_mean, 0.0)
            self.C = normalize(centered.T)
        self.collab_sim = self.C @ self.C.T
        np.fill_diagonal(self.collab_sim, 0)

        r = weighted_rating(movies)
        self.quality = (r - r.min()) / (r.max() - r.min()) if r.max() > r.min() else np.ones(n)
        self.n = n

    # ---------- helpers ----------
    def _indices(self, ids) -> list[int]:
        return [self.by_id[i] for i in dict.fromkeys(ids or []) if i in self.by_id]

    def expand_mood(self, mood: str) -> str:
        text = mood.lower()
        extra = [v for k, v in MOOD_SYNONYMS.items() if re.search(rf"(?<![a-z]){re.escape(k)}", text)]
        return " ".join([text, *extra])

    def _mood_terms(self, mood: str) -> set[str]:
        vocab = set(self.vectorizer.vocabulary_)
        return {t for t in self.expand_mood(mood).replace(",", " ").split() if t in vocab}

    def _mmr(self, candidates: list[int], relevance: np.ndarray, k: int) -> list[int]:
        """Maximal Marginal Relevance: trade relevance against redundancy."""
        selected: list[int] = []
        pool = list(candidates)
        while pool and len(selected) < k:
            if selected:
                redundancy = self.content_sim[np.ix_(pool, selected)].max(axis=1)
            else:
                redundancy = np.zeros(len(pool))
            mmr = MMR_LAMBDA * relevance[pool] - (1 - MMR_LAMBDA) * redundancy
            best = pool.pop(int(np.argmax(mmr)))
            selected.append(best)
        return selected

    def _card(self, idx: int, **extra) -> dict:
        return {**self.movies[idx], **extra}

    # ---------- public API ----------
    def recommend(self, liked=(), disliked=(), mood: str | None = None, k: int = 12) -> dict:
        liked_i, disliked_i = self._indices(liked), self._indices(disliked)
        mood = (mood or "").strip()
        n = self.n

        content = np.zeros(n)
        collab = np.zeros(n)
        profile = np.zeros(self.X.shape[1])
        if liked_i:
            profile += self.X[liked_i].sum(axis=0)
            collab += self.collab_sim[liked_i].mean(axis=0)
        if disliked_i:
            profile -= DISLIKE_PENALTY * self.X[disliked_i].sum(axis=0)
            collab -= DISLIKE_PENALTY * self.collab_sim[disliked_i].mean(axis=0)
        if mood:
            q = normalize(self.vectorizer.transform([self.expand_mood(mood)])).toarray()[0]
            profile += MOOD_BOOST * q * max(1, len(liked_i))
        if profile.any():
            content = self.X @ (profile / np.linalg.norm(profile))

        candidates = np.ones(n, dtype=bool)
        candidates[liked_i + disliked_i] = False

        if not liked_i and not disliked_i and not mood:
            weights, mode = {"content": 0, "collab": 0, "quality": 1}, "popular"
        elif mood and not liked_i:
            weights, mode = MOOD_WEIGHTS, "mood"
        else:
            weights, mode = WEIGHTS, "personal"

        parts = {
            "content": _minmax(content, candidates),
            "collab": _minmax(collab, candidates),
            "quality": _minmax(self.quality, candidates),
        }
        score = sum(weights[name] * parts[name] for name in parts)
        if mood:
            # Hard relevance floor so a mood search never returns unrelated films.
            candidates &= content > 0.05

        ranked = [int(i) for i in np.argsort(-score, kind="stable") if candidates[i]][: k * 3]
        chosen = self._mmr(ranked, score, k) if mode != "popular" else ranked[:k]

        mood_terms = self._mood_terms(mood) if mood else set()
        top = score[chosen].max() if chosen else 1.0
        items = []
        for idx in chosen:
            because, shared = None, []
            if liked_i:
                link = self.content_sim[idx, liked_i] + self.collab_sim[idx, liked_i]
                j = liked_i[int(np.argmax(link))]
                because = {"id": self.movies[j]["id"], "title": self.movies[j]["title"]}
                shared = sorted(_tokens(self.movies[idx]) & _tokens(self.movies[j]))
            if mood_terms:
                shared = sorted(set(shared) | (_tokens(self.movies[idx]) & mood_terms))
            if because:
                reason = f"Because you loved {because['title']}"
            elif mood:
                reason = f"Matches “{mood}”"
            else:
                reason = "A crowd favourite to get you started"
            items.append(self._card(
                idx,
                score=round(float(score[idx]), 4),
                match=int(round(55 + 44 * score[idx] / top)) if top > 0 else 55,
                reason=reason,
                because=because,
                shared=shared[:4],
                breakdown={name: round(float(weights[name] * parts[name][idx]), 4) for name in parts},
            ))

        return {"mode": mode, "items": items, "taste": self.taste_profile(liked_i, disliked_i)}

    def taste_profile(self, liked_i: list[int], disliked_i: list[int]) -> dict:
        genre_w: dict[str, float] = {}
        tag_w: dict[str, float] = {}
        for idx, w in [(i, 1.0) for i in liked_i] + [(i, -DISLIKE_PENALTY) for i in disliked_i]:
            for g in self.movies[idx]["genres"]:
                genre_w[g] = genre_w.get(g, 0) + w
            for t in self.movies[idx]["tags"]:
                tag_w[t] = tag_w.get(t, 0) + w
        top = max([v for v in genre_w.values() if v > 0], default=1)
        genres = sorted(((g, v) for g, v in genre_w.items() if v > 0), key=lambda x: -x[1])[:6]
        tags = sorted(((t, v) for t, v in tag_w.items() if v > 0), key=lambda x: -x[1])[:8]
        return {
            "genres": [{"name": g, "weight": round(v / top, 3)} for g, v in genres],
            "tags": [t for t, _ in tags],
            "confidence": round(min(1.0, len(liked_i) / 5), 2),
        }

    def similar(self, movie_id: int, k: int = 6) -> list[dict]:
        if movie_id not in self.by_id:
            raise KeyError(movie_id)
        i = self.by_id[movie_id]
        sim = 0.6 * self.content_sim[i] + 0.4 * self.collab_sim[i]
        order = [int(j) for j in np.argsort(-sim, kind="stable") if j != i][:k]
        base = _tokens(self.movies[i])
        return [
            self._card(j, similarity=round(float(sim[j]), 4), shared=sorted(_tokens(self.movies[j]) & base)[:4])
            for j in order
        ]

    def meta(self) -> dict:
        info = {
            "movies": self.n,
            "collab_source": self.collab_source,
            "vocabulary": len(self.vectorizer.vocabulary_),
            "weights": WEIGHTS,
            "mmr_lambda": MMR_LAMBDA,
            "genres": sorted({g for m in self.movies for g in m["genres"]}),
        }
        if self.ratings is not None:
            watched = self.ratings > 0
            info.update(
                simulated_users=int(self.ratings.shape[0]),
                ratings=int(watched.sum()),
                sparsity=round(1 - float(watched.mean()), 3),
            )
        else:
            info.update(graph_edges=self.graph_edges, avg_degree=round(2 * self.graph_edges / self.n, 1))
        return info


def dataset_name() -> str:
    """CINEMAGIC_DATASET wins; otherwise TMDB when a snapshot exists, else the curated 60."""
    name = os.environ.get("CINEMAGIC_DATASET", "").strip().lower()
    if name in DATASETS:
        return name
    return "tmdb" if DATASETS["tmdb"].exists() else "curated"


def load_dataset(name: str) -> Recommender:
    with open(DATASETS[name], encoding="utf-8") as f:
        return Recommender(json.load(f))


def load_default() -> Recommender:
    return load_dataset(dataset_name())
