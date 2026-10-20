"""Bounded feature resolution and validation for device-reported taste profiles."""
from collections import OrderedDict
from threading import RLock
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from features import FEATURE_LANGUAGE, normalized_features

FiniteWeight = Annotated[float, Field(strict=True, ge=-10000, le=10000, allow_inf_nan=False)]
SparseIndex = Annotated[int, Field(strict=True, ge=0, le=100000)]
SparseVector = Annotated[list[tuple[SparseIndex, FiniteWeight]], Field(max_length=100000)]
TermName = Annotated[str, Field(strict=True, min_length=1, max_length=200)]


class TasteTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    weight: FiniteWeight


class PreferenceSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^tmdb:[1-9]\d*$", max_length=40)
    title: str = Field(min_length=1, max_length=500)
    genres: list[TermName] = Field(default_factory=list, max_length=64)
    tags: list[TermName] = Field(default_factory=list, max_length=24)
    vector: SparseVector


class ExternalProfile(BaseModel):
    """An aggregate of resolved explicit preferences, never a claim of user ratings."""
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    feature_version: str = Field(min_length=1, max_length=80)
    vector: SparseVector
    positive_count: int = Field(strict=True, ge=0, le=10000)
    negative_count: int = Field(strict=True, ge=0, le=10000)
    genres: list[TasteTerm] = Field(default_factory=list, max_length=64)
    tags: list[TasteTerm] = Field(default_factory=list, max_length=10000)
    seeds: list[PreferenceSeed] = Field(default_factory=list, max_length=2)

    @field_validator("version", mode="before")
    @classmethod
    def version_check(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported external preference version")
        return value

    @model_validator(mode="after")
    def unique_fields(self):
        for vector in [self.vector, *(s.vector for s in self.seeds)]:
            indices = [i for i, _ in vector]
            if len(indices) != len(set(indices)):
                raise ValueError("Duplicate feature indices")
        for terms in [self.genres, self.tags]:
            if len({t.name for t in terms}) != len(terms):
                raise ValueError("Duplicate taste terms")
        if len({s.key for s in self.seeds}) != len(self.seeds):
            raise ValueError("Duplicate preference seeds")
        return self


class PreferenceFeatures:
    """Serialize upstream feature hydration; reuse the catalogue TTL and a bounded LRU."""
    def __init__(self, engine, catalog):
        self.engine, self.catalog = engine, catalog
        self.lock = RLock()
        self.cache = OrderedDict()

    def resolve(self, movie_id):
        with self.lock:
            movie = self.catalog.movie(movie_id, FEATURE_LANGUAGE, set(self.engine.by_id))
            key = (movie_id, self.engine.feature_version, movie.get("updated_at"))
            if key in self.cache:
                self.cache.move_to_end(key)
                return {**self.cache[key], "stale": movie.get("stale", False)}
            record = self.engine.resolve_preference(movie)
            self.cache[key] = record
            while len(self.cache) > 512:
                self.cache.popitem(last=False)
            return record


def preference_record(engine, movie):
    f = normalized_features(movie)
    # The vectorizer ignores unseen vocabulary. No fit/refit or matrix append occurs.
    vector = engine.vectorizer.transform([engine.feature_document(movie)]).toarray()[0]
    usable = bool(vector.any())
    return {"version": 1, "feature_version": engine.feature_version, "key": f"tmdb:{movie['id']}",
            "status": "applied" if usable else "unavailable", "feature_language": FEATURE_LANGUAGE,
            "reason": "" if usable else "This movie has no usable features in the current model vocabulary.",
            "vector": [[int(i), float(vector[i])] for i in vector.nonzero()[0]],
            "movie": {**movie, **f},
            "taste": {"genres": [g for g in f["genres"] if g in engine.known_genres],
                      "tags": [t for t in f["tags"] if t in engine.vectorizer.vocabulary_]},
            "stale": movie.get("stale", False)}
