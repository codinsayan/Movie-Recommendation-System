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
import time
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from viewing import VIEWING_CONFIG, canonical_key, viewing_evidence
from features import feature_text, feature_version
from preferences import ExternalProfile, preference_record

DATA_DIR = Path(__file__).parent / "data"
DATASETS = {"curated": DATA_DIR / "movies.json", "tmdb": DATA_DIR / "tmdb_movies.json"}
DATA_PATH = DATASETS["curated"]

WEIGHTS = {"content": 0.55, "collab": 0.35, "quality": 0.10}
MOOD_WEIGHTS = {"content": 0.80, "collab": 0.0, "quality": 0.20}
DISLIKE_PENALTY = 0.5
MOOD_BOOST = 1.5
MMR_LAMBDA = 0.75
# A newly discovered film that TMDB lists as related to one of your likes gets this much
# collaborative evidence per related like: about the strength of a direct link between two
# films in the snapshot's recommendation graph (2 / (degree + 1) with an average degree near 6).
RELATED_LINK = 0.3

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
        docs = [feature_text(m) for m in movies]
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
        self._quality_scale = (float(r.min()), float(r.max()))
        self._quality_prior = ((float(np.median([m["votes"] for m in movies])), float(np.mean([m["rating"] for m in movies])))
                               if all("votes" in m for m in movies) else None)
        self.n = n
        self.feature_version = feature_version(movies, self.vectorizer)
        self.known_genres = {g for m in movies for g in m["genres"]}

    feature_document = staticmethod(feature_text)

    def resolve_preference(self, movie):
        return preference_record(self, movie)

    def external_profile(self, payload, liked, disliked):
        if payload is None:
            return None
        data = ExternalProfile.model_validate(payload).model_dump()
        if self.movies[0].get("source") != "tmdb" or data["feature_version"] != self.feature_version:
            raise ValueError("External preferences require a compatible TMDB feature version")
        positives = set(liked) - set(disliked) - set(self.by_id)
        negatives = set(disliked) - set(self.by_id)
        if data["positive_count"] > len(positives) or data["negative_count"] > len(negatives):
            raise ValueError("External preference counts do not match the active choices")
        for vector in [data["vector"], *(s["vector"] for s in data["seeds"])]:
            if any(i >= self.X.shape[1] for i, _ in vector):
                raise ValueError("External feature index is outside this vocabulary")
        for seed in data["seeds"]:
            if int(seed["key"].split(":")[1]) not in positives:
                raise ValueError("Explanation seed is not an active external like")
        return data

    def quality_of(self, movies: list[dict]) -> np.ndarray:
        """Quality for titles outside the snapshot, on the snapshot's own scale (clipped to 0-1)."""
        r = np.array([float(m.get("rating") or 0) for m in movies])
        if self._quality_prior:
            prior, mean = self._quality_prior
            v = np.array([float(m.get("votes") or 0) for m in movies])
            r = v / (v + prior) * r + prior / (v + prior) * mean
        lo, hi = self._quality_scale
        return np.clip((r - lo) / (hi - lo), 0, 1) if hi > lo else np.ones(len(movies))

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

    def _mmr_union(self, candidates: list[int], relevance: np.ndarray, k: int, E: np.ndarray) -> list[int]:
        """MMR over snapshot rows plus discovered rows (index >= n refers to E)."""
        if not candidates:
            return []
        n = self.n
        V = np.vstack([self.X[i] if i < n else E[i - n] for i in candidates])
        S = V @ V.T
        snap = [p for p, i in enumerate(candidates) if i < n]
        if snap:  # identical numbers to the snapshot-only path for snapshot pairs
            ids = [candidates[p] for p in snap]
            S[np.ix_(snap, snap)] = self.content_sim[np.ix_(ids, ids)]
        selected: list[int] = []
        pool = list(range(len(candidates)))
        while pool and len(selected) < k:
            redundancy = S[np.ix_(pool, selected)].max(axis=1) if selected else np.zeros(len(pool))
            mmr = MMR_LAMBDA * relevance[[candidates[p] for p in pool]] - (1 - MMR_LAMBDA) * redundancy
            selected.append(pool.pop(int(np.argmax(mmr))))
        return [candidates[p] for p in selected]

    def _extra_explanation(self, j, extra, liked_i, external, external_links, weights, signals, parts, mood):
        """Explain a discovered film with the evidence that actually retrieved/ranked it."""
        n, movie, e = self.n, extra["movies"][j], extra["E"][j]
        info = movie["discovery"]
        because, shared, strength = None, [], 0.0
        seed_tokens = None
        for sid in info["related_to"]:  # most recent seed first
            title = extra["seed_titles"].get(sid)
            if title:
                because = {"id": sid, "title": title, "evidence": "tmdb-related"}
                seed = self.movies[self.by_id[sid]] if sid in self.by_id else next(
                    (s for s in (external or {}).get("seeds", []) if s["key"] == f"tmdb:{sid}"), None)
                seed_tokens = _tokens(seed) if seed else None
                break
        if not because and liked_i:
            link = self.X[liked_i] @ e
            if link.max() > .01:
                src = liked_i[int(np.argmax(link))]
                strength = float(link.max())
                because = {"id": self.movies[src]["id"], "title": self.movies[src]["title"]}
                seed_tokens = _tokens(self.movies[src])
        for seed, similarity in external_links:
            if not (because and because.get("evidence")) and weights["content"] > 0 and similarity[n + j] > max(.01, strength):
                strength = float(similarity[n + j])
                because = {"id": int(seed["key"].split(":")[1]), "title": seed["title"], "key": seed["key"]}
                seed_tokens = _tokens(seed)
        if not because and signals and parts["viewing"][n + j] > 0:
            src = max(signals, key=lambda s: s["strength"] * float(self.X[s["index"]] @ e))["index"]
            because = {"id": self.movies[src]["id"], "title": self.movies[src]["title"], "type": "watched"}
            seed_tokens = _tokens(self.movies[src])
        if seed_tokens:
            shared = sorted(_tokens(movie) & seed_tokens)
        if mood:
            shared = sorted(set(shared) | (_tokens(movie) & self._mood_terms(mood)))
        if because:
            reason = f"Because you {'watched' if because.get('type') == 'watched' else 'loved'} {because['title']}"
        elif mood:
            reason = f"Matches “{mood}”"
        elif "new_release" in info["sources"]:
            reason = "New release that fits your taste" if liked_i or external else "New release"
        elif liked_i or external:
            reason = "Discovered for your taste"
        else:
            reason = "Popular right now"
        return because, shared, reason

    def _card(self, idx: int, **extra) -> dict:
        return {**self.movies[idx], **extra}

    # ---------- public API ----------
    def recommend(self, liked=(), disliked=(), mood: str | None = None, k: int = 12,
                  viewing=None, use_viewing=False, recent_playback_only=False, eligible_keys=None, now=None,
                  external_preferences=None, extra=None) -> dict:
        external = self.external_profile(external_preferences, liked, disliked)
        external_likes = external["positive_count"] if external else 0
        external_dislikes = external["negative_count"] if external else 0
        liked_i, disliked_i = self._indices(liked), self._indices(disliked)
        # An explicit dislike always wins, including conflicting imported profiles.
        liked_i = [i for i in liked_i if i not in disliked_i]
        signals, recent = viewing_evidence(viewing, self.movies, set(liked_i + disliked_i),
                                          time.time() * 1000 if now is None else now)
        signals = signals if use_viewing else []
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
        if external:
            for j, value in external["vector"]:
                profile[j] += value
        if mood:
            q = normalize(self.vectorizer.transform([self.expand_mood(mood)])).toarray()[0]
            profile += MOOD_BOOST * q * max(1, len(liked_i) + external_likes)
        if profile.any():
            content = self.X @ (profile / np.linalg.norm(profile))

        # S5B: discovered titles join the candidate set (index >= n); snapshot rows are unchanged.
        m_extra = len(extra["movies"]) if extra else 0
        quality, movies_all, E = self.quality, self.movies, None
        if m_extra:
            E = extra["E"]
            content = np.concatenate([content, E @ (profile / np.linalg.norm(profile)) if profile.any() else np.zeros(m_extra)])
            hits = np.array([len(m["discovery"]["related_to"]) for m in extra["movies"]], dtype=float)
            collab = np.concatenate([collab, RELATED_LINK * hits / max(1, len(liked_i) + external_likes)])
            quality = np.concatenate([self.quality, extra["quality"]])
            movies_all = self.movies + extra["movies"]
        N = n + m_extra

        candidates = np.ones(N, dtype=bool)
        candidates[liked_i + disliked_i] = False
        candidates[[s["index"] for s in signals]] = False
        if m_extra:  # exact IDs stay excluded whichever source retrieved them
            seen = set(liked) | set(disliked)
            candidates[n:] &= np.array([m["id"] not in seen for m in extra["movies"]])
        if eligible_keys is not None:
            allowed = set(eligible_keys)
            candidates &= np.array([canonical_key(m) in allowed for m in movies_all])
        if recent_playback_only:
            candidates &= np.array([canonical_key(m) in recent for m in movies_all])

        if not liked_i and not disliked_i and not external_likes and not external_dislikes and not mood:
            weights, mode = {"content": 0, "collab": 0, "quality": 1}, "popular"
        elif mood and not liked_i and not external_likes:
            weights, mode = MOOD_WEIGHTS, "mood"
        else:
            weights, mode = WEIGHTS, "personal"

        if external and external_likes + external_dislikes:
            # Only indexed choices have collaborative evidence; external metadata is content.
            weights = dict(weights)
            indexed = len(liked_i) + len(disliked_i)
            weights["collab"] *= indexed / (indexed + external_likes + external_dislikes)
            if not profile.any():
                weights["content"] = 0
            total = sum(weights.values())
            weights = {name: value / total for name, value in weights.items()}

        parts = {
            "content": _minmax(content, candidates),
            "collab": _minmax(collab, candidates),
            "quality": _minmax(quality, candidates),
        }
        if signals:
            # Bound the entire implicit contribution to 10%; explicit baseline retains 90%.
            def viewing_row(i):
                row = 0.6 * self.content_sim[i] + 0.4 * self.collab_sim[i]
                return np.concatenate([row, 0.6 * (E @ self.X[i])]) if m_extra else row
            implicit = sum(s["strength"] / VIEWING_CONFIG["maxStrength"] * viewing_row(s["index"])
                           for s in signals) / len(signals)
            parts["viewing"] = np.clip(implicit, 0, 1)
            weights = {name: weight * (1 - VIEWING_CONFIG["blend"]) for name, weight in weights.items()}
            weights["viewing"] = VIEWING_CONFIG["blend"]
            if mode == "popular":
                mode = "viewing"
        score = sum(weights[name] * parts[name] for name in parts)
        if mood:
            # Hard relevance floor so a mood search never returns unrelated films.
            candidates &= content > 0.05

        ranked = [int(i) for i in np.argsort(-score, kind="stable") if candidates[i]][: k * 3]
        if mode == "popular":
            chosen = ranked[:k]
        else:
            chosen = self._mmr_union(ranked, score, k, E) if m_extra else self._mmr(ranked, score, k)

        mood_terms = self._mood_terms(mood) if mood else set()
        top = score[chosen].max() if chosen else 1.0
        items = []
        external_links = []
        for seed in external["seeds"] if external else []:
            vector = np.zeros(self.X.shape[1])
            for j, value in seed["vector"]:
                vector[j] = value
            length = np.linalg.norm(vector)
            similarity = self.X @ (vector / length) if length else np.zeros(n)
            if m_extra:
                similarity = np.concatenate([similarity, E @ (vector / length) if length else np.zeros(m_extra)])
            external_links.append((seed, similarity))
        for idx in chosen:
            if idx >= n:
                because, shared, reason = self._extra_explanation(idx - n, extra, liked_i, external, external_links,
                                                                  weights, signals, parts, mood)
                items.append({**extra["movies"][idx - n],
                              "score": round(float(score[idx]), 4),
                              "match": int(round(55 + 44 * score[idx] / top)) if top > 0 else 55,
                              "reason": reason, "because": because, "shared": shared[:4],
                              "breakdown": {name: round(float(weights[name] * parts[name][idx]), 4) for name in parts}})
                continue
            because, shared = None, []
            link_strength = 0
            if liked_i:
                link = self.content_sim[idx, liked_i] + self.collab_sim[idx, liked_i]
                j = liked_i[int(np.argmax(link))]
                link_strength = float(max(link))
                because = {"id": self.movies[j]["id"], "title": self.movies[j]["title"]}
                shared = sorted(_tokens(self.movies[idx]) & _tokens(self.movies[j]))
            for seed, similarity in external_links:
                if weights["content"] > 0 and similarity[idx] > max(.01, link_strength):
                    link_strength = float(similarity[idx])
                    because = {"id": int(seed["key"].split(":")[1]), "title": seed["title"], "key": seed["key"]}
                    shared = sorted(_tokens(self.movies[idx]) & _tokens(seed))
            if not because and signals and parts["viewing"][idx] > 0:
                j = max(signals, key=lambda s: s["strength"] *
                        (0.6 * self.content_sim[idx, s["index"]] + 0.4 * self.collab_sim[idx, s["index"]]))["index"]
                because = {"id": self.movies[j]["id"], "title": self.movies[j]["title"], "type": "watched"}
                shared = sorted(_tokens(self.movies[idx]) & _tokens(self.movies[j]))
            if mood_terms:
                shared = sorted(set(shared) | (_tokens(self.movies[idx]) & mood_terms))
            if because:
                verb = "watched" if because.get("type") == "watched" else "loved"
                reason = f"Because you {verb} {because['title']}"
            elif mood:
                reason = f"Matches “{mood}”"
            elif external and external_likes + external_dislikes:
                reason = "Based on your movie preferences"
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
                **({"component_availability": {"content": bool(profile.any()), "collab": bool(liked_i or disliked_i),
                                               "quality": True, "viewing": bool(signals)}} if external else {}),
            ))

        watched_rows = []
        for signal in signals[:2]:
            j = signal["index"]
            relevance = .6 * self.content_sim[j] + .4 * self.collab_sim[j]
            pool = [int(i) for i in np.argsort(-relevance, kind="stable") if candidates[i] and relevance[i] > 0][:42]
            watched_rows.append({"source": self.movies[j], "watched_seconds": signal["watched_seconds"],
                                 "duration": signal["duration"],
                                 "items": [self._card(i) for i in self._mmr(pool, relevance, 14)]})
        result = {"mode": mode, "items": items, "taste": self.taste_profile(liked_i, disliked_i, external),
                  "watched_rows": watched_rows}
        if external:
            result["because_rows"] = []
            related_candidates = np.ones(n, dtype=bool)
            related_candidates[liked_i + disliked_i] = False
            for seed, relevance in external_links:
                # This shelf explains an explicit like, independently of the Top Picks filter/mood.
                relevance = relevance[:n]  # snapshot shelf; discovered titles appear in Top Picks
                pool = [int(i) for i in np.argsort(-relevance, kind="stable") if related_candidates[i] and relevance[i] > .01][:42]
                result["because_rows"].append({"source": {"id": int(seed["key"].split(":")[1]),
                                                        **{k: v for k, v in seed.items() if k != "vector"}},
                                                "items": [self._card(i) for i in self._mmr(pool, relevance, 14)]})
        return result

    def taste_profile(self, liked_i: list[int], disliked_i: list[int], external=None) -> dict:
        genre_w = {t["name"]: t["weight"] for t in external["genres"]} if external else {}
        tag_w = {t["name"]: t["weight"] for t in external["tags"]} if external else {}
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
            "confidence": round(min(1.0, (len(liked_i) + (external["positive_count"] if external else 0)) / 5), 2),
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

    def similar_external(self, record: dict, k: int = 6) -> list[dict]:
        """Related snapshot films from a resolved movie; no candidate/catalogue expansion."""
        if record.get("feature_version") != self.feature_version or record.get("version") != 1:
            raise ValueError("Incompatible external movie features")
        if record.get("status") != "applied":
            return []
        vector = np.zeros(self.X.shape[1])
        for j, value in record["vector"]:
            vector[j] = value
        length = np.linalg.norm(vector)
        relevance = self.X @ (vector / length) if length else np.zeros(self.n)
        source_id = record["movie"]["id"]
        pool = [int(i) for i in np.argsort(-relevance, kind="stable")
                if self.movies[i]["id"] != source_id and relevance[i] > .01][: k * 3]
        tokens = _tokens(record["movie"])
        return [self._card(i, similarity=round(float(relevance[i]), 4),
                           shared=sorted(_tokens(self.movies[i]) & tokens)[:4])
                for i in self._mmr(pool, relevance, k)]

    def meta(self) -> dict:
        info = {
            "movies": self.n,
            "collab_source": self.collab_source,
            "vocabulary": len(self.vectorizer.vocabulary_),
            "weights": WEIGHTS,
            "mmr_lambda": MMR_LAMBDA,
            "viewing": VIEWING_CONFIG,
            "preferences": {"version": 1, "feature_version": self.feature_version, "feature_language": "en-US",
                            "vocabulary_size": self.X.shape[1], "genres": sorted(self.known_genres),
                            "dislike_penalty": DISLIKE_PENALTY},
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
        movies = json.load(f)
    # A curated integer ID is not a TMDB ID. Preserve identity in both the API
    # and static export so playback never resolves a different film by accident.
    for movie in movies:
        movie["source"] = name
        movie["tmdb_id"] = movie["id"] if name == "tmdb" else movie.get("tmdb_id")
    return Recommender(movies)


def load_default() -> Recommender:
    return load_dataset(dataset_name())
