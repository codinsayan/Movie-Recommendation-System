"""Record real TMDB discovery pools once, so S5D evaluation is reproducible offline.

Usage:  python scripts/record_dynamic_fixture.py [--output docs/evaluation/s5d-live-fixture.json]

Needs the local TMDB credentials in .env (never written to the fixture). Each profile is
run through the production Discovery code; the fixture stores the profile, the external
preference records it used, and every retrieved candidate's metadata and provenance.
Re-recording gives different pools as TMDB changes, which is why the file is versioned.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from catalog import Catalog, CatalogError  # noqa: E402
from discovery import BUDGET, Discovery  # noqa: E402
from features import FEATURE_LANGUAGE  # noqa: E402
from recommender import DATASETS, load_dataset  # noqa: E402

DEFAULT_OUT = ROOT / "docs" / "evaluation" / "s5d-live-fixture.json"
KEEP = ("id", "title", "original_title", "original_language", "year", "genres", "tags", "people", "overview",
        "feature_overview", "rating", "votes", "full_details", "metadata_language", "director", "cast", "discovery")

# Snapshot titles (liked / disliked) and external TMDB IDs (liked_external / disliked_external).
PROFILES = [
    {"name": "pixar", "liked": ["Toy Story", "Up", "Coco"]},
    {"name": "nolan", "liked": ["Inception", "Interstellar", "The Dark Knight"]},
    {"name": "single-niche-like", "liked": ["Parasite"]},
    {"name": "romance", "liked": ["The Notebook", "La La Land"]},
    {"name": "horror", "liked": ["Get Out", "The Conjuring"]},
    {"name": "multi-interest", "liked": ["Toy Story", "The Dark Knight", "The Notebook"]},
    {"name": "related-dislike", "liked": ["Inception"], "disliked": ["Interstellar"]},
    {"name": "external-like-and-dislike", "liked_external": [14337], "disliked_external": [8373]},  # Primer; Transformers: RotF
    {"name": "foreign-original-language", "liked_external": [491584, 505192]},  # Burning (ko), Shoplifters (ja)
    {"name": "new-release-like", "liked_new_release": True},  # the most popular recent release outside the snapshot
    {"name": "dislike-only", "disliked": ["Toy Story", "Cars"]},
    {"name": "cold-start"},
]


def external_profile(engine, records, liked_ids, disliked_ids):
    """The same aggregate frontend/preference-resolver.js builds from resolved records."""
    vector, genres, tags, seeds = {}, {}, {}, []
    pos = neg = 0
    for record in records:
        if record["status"] != "applied":
            continue
        mid = record["movie"]["id"]
        w = 1.0 if mid in liked_ids else -0.5 if mid in disliked_ids else 0
        if not w:
            continue
        pos, neg = pos + (w > 0), neg + (w < 0)
        for i, v in record["vector"]:
            vector[i] = vector.get(i, 0) + w * v
        for g in record["taste"]["genres"]:
            genres[g] = genres.get(g, 0) + w
        for t in record["taste"]["tags"]:
            tags[t] = tags.get(t, 0) + w
        if w > 0:
            seeds.append({"key": record["key"], "title": record["movie"]["title"], "genres": record["movie"]["genres"],
                          "tags": record["movie"]["tags"][:24], "vector": record["vector"]})
    if not pos and not neg:
        return None
    return {"version": 1, "feature_version": engine.feature_version,
            "vector": [[i, v] for i, v in vector.items() if v], "positive_count": pos, "negative_count": neg,
            "genres": [{"name": k, "weight": v} for k, v in genres.items()],
            "tags": [{"name": k, "weight": v} for k, v in tags.items()], "seeds": seeds[-2:][::-1]}


def retry(fn, attempts=8):
    """The recording network can be flaky; successful responses are cached, so retrying converges."""
    for attempt in range(attempts):
        try:
            return fn()
        except CatalogError as error:
            if error.status == 404 or attempt == attempts - 1:
                raise
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    engine = load_dataset("tmdb")
    catalog = Catalog.from_environment()
    if not catalog.configured:
        sys.exit("TMDB credentials are required to record a fixture (see .env.example).")
    disc = Discovery(engine, catalog, budget={"enrich": 0})
    titles = {m["title"]: m["id"] for m in engine.movies}
    profiles = []
    for spec in PROFILES:
        liked = [titles[t] for t in spec.get("liked", [])] + spec.get("liked_external", [])
        disliked = [titles[t] for t in spec.get("disliked", [])] + spec.get("disliked_external", [])
        if spec.get("liked_new_release"):
            since = (dt.date.today() - dt.timedelta(days=BUDGET["new_release_days"])).isoformat()
            recent = retry(lambda: catalog.discover(sort="popularity.desc", min_votes=50, released_after=since))
            pick = next(m for m in recent["items"] if m["id"] not in engine.by_id)
            spec = {**spec, "liked_external": [pick["id"]]}
            liked = [pick["id"]]
        externals = [m for m in spec.get("liked_external", []) + spec.get("disliked_external", [])]
        records = [engine.resolve_preference(retry(lambda mid=mid: catalog.movie(mid, FEATURE_LANGUAGE, set(engine.by_id))))
                   for mid in externals]
        external = external_profile(engine, records, set(liked), set(disliked))
        # Warm full details for the pool first, as a returning visitor's cache would be.
        for _ in range(8):   # repeat until every source answered (each success is cached)
            extra, report = disc.candidates(liked, disliked, external)
            if report["status"] == "ok":
                break
            time.sleep(2)
        if extra:
            # Warm full details for the pool, as a returning visitor's cache would be.
            for movie in extra["movies"]:
                if not movie.get("full_details"):
                    try:
                        retry(lambda mid=movie["id"]: catalog.movie(mid, FEATURE_LANGUAGE, set()), attempts=4)
                    except CatalogError:
                        pass   # stays summary-only in the fixture
            extra, report = disc.candidates(liked, disliked, external)
        pool = [{k: m[k] for k in KEEP if k in m} for m in (extra or {"movies": []})["movies"]]
        profiles.append({"name": spec["name"], "liked": liked, "disliked": disliked,
                         "external_records": [{k: r[k] for k in ("key", "status", "vector")} | {"movie": {k: r["movie"][k] for k in ("id", "title", "genres", "tags", "original_language")}, "taste": r["taste"]}
                                              for r in records],
                         "external_preferences": external, "seed_titles": (extra or {}).get("seed_titles", {}),
                         "report": {k: report[k] for k in ("status", "profile", "seeds", "genres", "sources", "pool", "enriched", "summary_only")},
                         "pool": pool})
        print(f"{spec['name']}: pool {len(pool)} ({report['status']}), full details {report['enriched']}")
    snapshot = DATASETS["tmdb"].read_bytes()
    fixture = {"version": 1, "recorded": dt.date.today().isoformat(), "source": "TMDB API via backend/discovery.py",
               "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(), "feature_version": engine.feature_version,
               "discovery_budget": BUDGET, "profiles": profiles}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {args.output} ({args.output.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
