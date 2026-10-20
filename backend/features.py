"""Shared, versioned movie feature normalization; no per-preference model fitting."""
import hashlib
import json
import unicodedata

FEATURE_SCHEMA = 1
FEATURE_LANGUAGE = "en-US"


def slug(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def normalized_features(movie):
    genres = ["Sci-Fi" if g == "Science Fiction" else g for g in movie.get("genres", []) if g != "TV Movie"]
    people = movie.get("people")
    if people is None:
        people = ([movie["director"]] if movie.get("director") else []) + movie.get("cast", [])[:3]
    return {"genres": genres, "tags": [slug(t) for t in movie.get("tags", []) if slug(t)],
            "people": [slug(p) for p in people if slug(p)],
            "overview": movie.get("feature_overview", movie.get("overview")) or ""}


def feature_text(movie):
    f = normalized_features(movie)
    return " ".join(f["genres"] * 2 + f["tags"] * 2 + f["people"]).lower() + " " + f["overview"].lower()


def feature_version(movies, vectorizer):
    payload = [FEATURE_SCHEMA, FEATURE_LANGUAGE, vectorizer.vocabulary_, vectorizer.idf_.tolist(),
               [[m.get("source"), m["id"], feature_text(m)] for m in movies]]
    return "tfidf-v1-" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
