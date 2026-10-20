"""S5D: reproducible evaluation of dynamic preferences, retrieval and bounded ranking.

Usage:  python scripts/evaluate_dynamic.py [--output docs/evaluation/s5d-results.json]
                                           [--review docs/evaluation/s5d-review.md]

No network or credentials. Two parts:

1. World proxy. The 447-film snapshot is split (seed 2026) into a 70% "starter" catalogue,
   used to build the engine, and a 30% "world" of external films served by a fake TMDB
   (related titles = the bundled TMDB recommendation graph; discovery = genre/vote/date
   filters). Profiles like one starter film and one external film; the hidden target is a
   graph neighbour of the external like, and that edge is removed from the related-title
   responses so retrieval must find it another way. The graph also trains the starter
   engine, so this is a TRANSDUCTIVE PROXY with overlap, not independent user evidence.
   Variants: A snapshot engine (external likes unusable), B dynamic inputs (S5A
   preferences, snapshot candidates), C dynamic retrieval + bounded ranking (S5B/S5C).
   Retrieval recall is reported separately from ranking; calibration policies are
   compared on C's common candidate pool.

2. Live replay. Real TMDB pools recorded by scripts/record_dynamic_fixture.py are ranked
   offline under each calibration policy. There is no ground-truth target here, so it
   reports popularity bias, discovered share, diversity, exact-dislike exclusion and
   explanation fidelity, plus a side-by-side sheet for human relevance review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
from pathlib import Path

import numpy as np
import sklearn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import CatalogError  # noqa: E402
from discovery import Discovery  # noqa: E402
from ranking import FeatureStore  # noqa: E402
from record_dynamic_fixture import external_profile  # noqa: E402
from recommender import DATASETS, DISCOVERY_POLICY, EXPLAIN_FLOOR, Recommender, load_dataset  # noqa: E402

SEED = 2026
K = 10
FIXTURE = ROOT / "docs" / "evaluation" / "s5d-live-fixture.json"
POLICIES = {
    "s5b_snapshot_prior": {"quality_prior": "snapshot", "related_confidence": False, "min_votes": 0},
    "pool_prior": {"quality_prior": "pool", "related_confidence": False, "min_votes": 0},
    "pool_prior_related_confidence": {"quality_prior": "pool", "related_confidence": True, "min_votes": 0},
    "vote_floor_100": {"quality_prior": "snapshot", "related_confidence": False, "min_votes": 100},
    "pool_prior_confidence_floor_50": {"quality_prior": "pool", "related_confidence": True, "min_votes": 50},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- world proxy
def card(movie, full=True):
    """A TMDB-like normalized movie: summaries carry no keywords or people, like real list results."""
    return {"id": movie["id"], "tmdb_id": movie["id"], "source": "tmdb", "title": movie["title"], "year": movie.get("year"),
            "genres": list(movie["genres"]), "tags": list(movie["tags"]) if full else [],
            "people": list(movie.get("people", [])) if full else [], "overview": movie["overview"],
            "feature_overview": movie["overview"], "rating": movie["rating"], "votes": movie["votes"],
            "original_language": movie.get("original_language", "en"), "full_details": full, "metadata_language": "en-US"}


class WorldCatalog:
    """Fake TMDB over the full snapshot. Discovery excludes starter IDs itself, as in production."""
    configured = True
    NEW_RELEASE_TTL = 1

    def __init__(self, world, held_out=(), uncached=()):
        self.world, self.held_out, self.uncached = world, set(held_out), set(uncached)

    def related(self, movie_id, page=1):
        recs = [r for r in self.world.get(movie_id, {}).get("tmdb_recs", []) if r in self.world and (movie_id, r) not in self.held_out]
        return {"items": [card(self.world[r], full=False) for r in recs], "cached": True, "stale": False}

    def discover(self, *, genres=(), sort="vote_count.desc", min_votes=200, released_after=None, page=1, ttl=None):
        pool = [m for m in self.world.values() if m["votes"] >= min_votes and (not genres or set(genres) & set(m["genres"]))
                and (released_after is None or (m.get("year") or 0) >= int(released_after[:4]))]
        key = (lambda m: m["rating"]) if sort == "vote_average.desc" else (lambda m: m["votes"])
        pool.sort(key=lambda m: (-key(m), m["id"]))
        return {"items": [card(m, full=False) for m in pool[(page - 1) * 20: page * 20]], "cached": True, "stale": False}

    def cached_movies(self, ids, language="en-US"):
        return {i: card(self.world[i]) for i in ids if i in self.world and i not in self.uncached}

    def cached_movie(self, movie_id, language="en-US"):
        return self.cached_movies([movie_id]).get(movie_id)

    def movie(self, *_):
        raise CatalogError(503, "offline")


def proxy_profiles(full, starter_ids, rng, limit=80):
    by_id = {m["id"]: m for m in full}
    world_only = [m for m in full if m["id"] not in starter_ids]
    profiles = []
    for w in rng.permutation(len(world_only)):
        w = world_only[int(w)]
        neighbours = sorted(r for r in w.get("tmdb_recs", []) if r in by_id)
        starter_n = [r for r in neighbours if r in starter_ids]
        if len(neighbours) < 2 or not starter_n:
            continue
        s = int(rng.choice(starter_n))
        target = int(rng.choice([r for r in neighbours if r != s]))
        far = [m["id"] for m in world_only if m["id"] not in neighbours and m["id"] != w["id"]
               and not set(m["genres"]) & set(w["genres"])]
        disliked = int(rng.choice(far)) if far and len(profiles) % 2 == 0 else None
        profiles.append({"like_starter": s, "like_external": w["id"], "target": target,
                         "target_in_starter": target in starter_ids, "disliked_external": disliked})
        if len(profiles) >= limit:
            break
    return profiles


def proxy_external(engine, movie, liked, disliked, unfamiliar=False):
    if unfamiliar:   # metadata in words the fitted vocabulary has never seen
        movie = {**movie, "genres": [], "tags": ["zzqx-" + t for t in movie["tags"]], "people": [],
                 "overview": "qwvz " * 12}
    record = engine.resolve_preference(card(movie))
    return external_profile(engine, [record], set(liked), set(disliked)), record["status"]


def rank_metrics(items, target):
    ids = [m["id"] for m in items]
    hit = target in ids[:K]
    return int(hit), (1 / math.log2(ids.index(target) + 2) if hit else 0.0)


def world_proxy(full):
    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(full))
    cut = int(0.7 * len(full))
    starter = [dict(full[i]) for i in sorted(order[:cut])]
    starter_ids = {m["id"] for m in starter}
    engine = Recommender(starter)
    reference = Recommender([dict(m) for m in full])   # common vector space for diversity
    world = {m["id"]: m for m in full}
    profiles = proxy_profiles(full, starter_ids, rng)
    store = FeatureStore(engine)
    results = {"protocol": {"seed": SEED, "starter_films": len(starter), "world_only_films": len(full) - len(starter),
                            "profiles": len(profiles), "k": K, "held_out_edge": "external like -> target removed from related titles",
                            "label": "transductive graph proxy; not independent user evidence"}}

    def diversity(items):
        rows = [reference.by_id[m["id"]] for m in items[:K] if m["id"] in reference.by_id]
        pairs = [1 - reference.content_sim[a, b] for i, a in enumerate(rows) for b in rows[i + 1:]]
        return float(np.mean(pairs)) if pairs else 0.0

    scenarios = {"full_metadata": {}, "summary_only_candidates": {"uncached": True},
                 "unfamiliar_external_like": {"unfamiliar": True}}
    for scenario, flags in scenarios.items():
        acc = {v: {"starter_target": [], "world_target": [], "recall": [], "diversity": [], "dislike_violations": 0,
                   "invalid_because": 0, "coverage": set()} for v in ("A_snapshot", "B_dynamic_inputs", "C_dynamic_retrieval")}
        policy_acc = {p: {"world_target": [], "starter_target": []} for p in POLICIES}
        unavailable = 0
        for prof in profiles:
            liked = [prof["like_starter"], prof["like_external"]]
            disliked = [prof["disliked_external"]] if prof["disliked_external"] else []
            ext, status = proxy_external(engine, world[prof["like_external"]], liked, disliked, flags.get("unfamiliar", False))
            unavailable += status != "applied"
            uncached = set(world) - starter_ids if flags.get("uncached") else ()
            catalog = WorldCatalog(world, held_out={(prof["like_external"], prof["target"])}, uncached=uncached)
            disc = Discovery(engine, catalog, budget={"enrich": 0}, features=store)
            extra, _ = disc.candidates(liked, disliked, ext)
            if extra:
                extra.pop("encoding", None)
            pool_ids = set(starter_ids) | {m["id"] for m in (extra or {"movies": []})["movies"]}
            engine.discovery_policy = dict(DISCOVERY_POLICY)
            runs = {"A_snapshot": engine.recommend([prof["like_starter"]], k=K),
                    "B_dynamic_inputs": engine.recommend(liked, disliked, k=K, external_preferences=ext),
                    "C_dynamic_retrieval": engine.recommend(liked, disliked, k=K, external_preferences=ext, extra=extra)}
            bucket = "starter_target" if prof["target_in_starter"] else "world_target"
            for variant, out in runs.items():
                a = acc[variant]
                a[bucket].append(rank_metrics(out["items"], prof["target"]))
                a["recall"].append(int(prof["target"] in (pool_ids if variant == "C_dynamic_retrieval" else starter_ids)))
                a["diversity"].append(diversity(out["items"]))
                a["coverage"].update(m["id"] for m in out["items"])
                a["dislike_violations"] += sum(m["id"] in disliked for m in out["items"])
                for m in out["items"]:
                    b = m.get("because")
                    if b and b["id"] not in liked:
                        a["invalid_because"] += 1
                    elif b and b.get("evidence") == "tmdb-related" and b["id"] not in m["discovery"]["related_to"]:
                        a["invalid_because"] += 1
            for name, policy in POLICIES.items():   # same retrieved pool, different calibration
                engine.discovery_policy = dict(policy)
                out = engine.recommend(liked, disliked, k=K, external_preferences=ext, extra=extra)
                policy_acc[name][bucket].append(rank_metrics(out["items"], prof["target"]))
            engine.discovery_policy = dict(DISCOVERY_POLICY)

        def summarise(pairs):
            return {"n": len(pairs), "hr@10": round(float(np.mean([h for h, _ in pairs])), 4) if pairs else None,
                    "ndcg@10": round(float(np.mean([g for _, g in pairs])), 4) if pairs else None}
        results[scenario] = {
            "external_like_unavailable": unavailable,
            "variants": {v: {"starter_targets": summarise(a["starter_target"]), "world_targets": summarise(a["world_target"]),
                             "retrieval_recall": round(float(np.mean(a["recall"])), 4),
                             "coverage": round(len(a["coverage"]) / len(full), 4),
                             "diversity": round(float(np.mean(a["diversity"])), 4),
                             "dislike_violations": a["dislike_violations"], "invalid_because": a["invalid_because"]}
                         for v, a in acc.items()},
            "policies_on_common_pool": {p: {"starter_targets": summarise(a["starter_target"]),
                                            "world_targets": summarise(a["world_target"])} for p, a in policy_acc.items()},
        }
    return results


# ---------------------------------------------------------------- live replay
def live_extra(engine, store, profile):
    movies = [{**m, "source": "tmdb", "tmdb_id": m["id"], "in_model": False, "dynamic": True} for m in profile["pool"]]
    if not movies:
        return None
    E, _ = store.encode(movies)
    return {"movies": movies, "E": E, "seed_titles": {int(k): v for k, v in profile["seed_titles"].items()}}


def live_replay(fixture, recommended):
    engine = load_dataset("tmdb")
    if fixture["feature_version"] != engine.feature_version:
        sys.exit("The live fixture was recorded with another feature version; re-record it.")
    store = FeatureStore(engine)
    rows, review = {}, []
    for name, policy in POLICIES.items():
        engine.discovery_policy = dict(policy)
        agg = {"discovered_top10": [], "discovered_top20": [], "median_votes_discovered_top20": [], "under_100_votes_top20": [],
               "under_300_votes_top20": [], "mean_rating_top20": [], "diversity_top10": [], "because_share_top20": [],
               "dislike_violations": 0, "invalid_because": 0}
        for profile in fixture["profiles"]:
            extra = live_extra(engine, store, profile)
            out = engine.recommend(profile["liked"], profile["disliked"], k=20,
                                   external_preferences=profile["external_preferences"], extra=extra)
            items = out["items"]
            n = engine.n
            discovered = [m for m in items if m.get("dynamic")]
            agg["discovered_top10"].append(sum(bool(m.get("dynamic")) for m in items[:10]) / max(1, len(items[:10])))
            agg["discovered_top20"].append(len(discovered) / max(1, len(items)))
            if discovered:
                agg["median_votes_discovered_top20"].append(statistics.median(m["votes"] for m in discovered))
            agg["under_100_votes_top20"].append(sum(m["votes"] < 100 for m in items) / max(1, len(items)))
            agg["under_300_votes_top20"].append(sum(m["votes"] < 300 for m in items) / max(1, len(items)))
            agg["mean_rating_top20"].append(float(np.mean([m["rating"] for m in items])) if items else 0)
            agg["because_share_top20"].append(sum(bool(m["because"]) for m in items) / max(1, len(items)))
            vectors = []
            index = {m["id"]: p for p, m in enumerate(extra["movies"])} if extra else {}
            for m in items[:10]:
                vectors.append(engine.X[engine.by_id[m["id"]]] if m["id"] in engine.by_id
                               else np.asarray(extra["E"][index[m["id"]]].todense()).ravel())
            pairs = [1 - float(a @ b) for i, a in enumerate(vectors) for b in vectors[i + 1:]]
            agg["diversity_top10"].append(float(np.mean(pairs)) if pairs else 0)
            agg["dislike_violations"] += sum(m["id"] in set(profile["disliked"]) for m in items)
            for m in items:
                b = m.get("because")
                if not b:
                    continue
                if b.get("type") != "watched" and b["id"] not in profile["liked"]:
                    agg["invalid_because"] += 1
                if b.get("evidence") == "tmdb-related" and b["id"] not in m["discovery"]["related_to"]:
                    agg["invalid_because"] += 1
            if name in ("s5b_snapshot_prior", recommended):
                review.append((profile["name"], name, items[:10]))
        rows[name] = {k: (round(float(np.mean(v)), 4) if isinstance(v, list) and v else v) for k, v in agg.items()}
    engine.discovery_policy = dict(DISCOVERY_POLICY)
    return rows, review


def vocabulary_coverage(fixture):
    """How much of real discovered metadata the fitted TF-IDF vocabulary can represent (embedding go/no-go input)."""
    engine = load_dataset("tmdb")
    store = FeatureStore(engine)
    movies = {m["id"]: {**m, "source": "tmdb"} for p in fixture["profiles"] for m in p["pool"]}
    E, _ = store.encode(list(movies.values()))
    nnz = np.diff(E.indptr)
    snap = np.count_nonzero(engine.X, axis=1)
    analyzer = engine.vectorizer.build_analyzer()
    vocab = engine.vectorizer.vocabulary_
    from features import feature_text
    known = [sum(t in vocab for t in analyzer(feature_text(m))) / max(1, len(analyzer(feature_text(m))))
             for m in movies.values()]
    langs = {}
    for m in movies.values():
        langs[m.get("original_language") or "?"] = langs.get(m.get("original_language") or "?", 0) + 1
    records = [r for p in fixture["profiles"] for r in p["external_records"]]
    return {"discovered_unique": len(movies), "median_features_discovered": float(np.median(nnz)),
            "median_features_snapshot": float(np.median(snap)), "zero_feature_discovered": int((nnz == 0).sum()),
            "under_10_features_discovered": int((nnz < 10).sum()),
            "median_token_share_in_vocabulary": round(float(np.median(known)), 4),
            "original_languages": dict(sorted(langs.items(), key=lambda kv: -kv[1])[:8]),
            "external_preferences": {"resolved": len(records), "applied": sum(r["status"] == "applied" for r in records),
                                     "median_features": float(np.median([len(r["vector"]) for r in records])) if records else 0}}


def review_sheet(fixture, review, recommended):
    by_profile = {}
    for profile, policy, items in review:
        by_profile.setdefault(profile, {})[policy] = items
    lines = ["# S5D relevance review sheet", "",
             f"Generated by `scripts/evaluate_dynamic.py` from the live fixture recorded {fixture['recorded']}. "
             "For each profile, rate every pick 2 (good), 1 (fine) or 0 (wrong for this taste) in the empty column, "
             "for the S5B baseline and for the proposed calibration. D = discovered outside the snapshot.", ""]
    names = {p["name"]: p for p in fixture["profiles"]}
    for profile, policies in by_profile.items():
        p = names[profile]
        ext = {r["movie"]["id"]: r["movie"]["title"] for r in p["external_records"]}
        liked = [ext.get(i, str(i)) for i in p["liked"]]
        lines += [f"## {profile}", "", f"Likes: {', '.join(liked) or '-'} · Dislikes: {', '.join(ext.get(i, str(i)) for i in p['disliked']) or '-'}", ""]
        snapshot_titles = {m["id"]: m["title"] for m in load_title_index()}
        if p["liked"]:
            lines[-2] = "Likes: " + ", ".join(snapshot_titles.get(i, ext.get(i, str(i))) for i in p["liked"]) + \
                " · Dislikes: " + (", ".join(snapshot_titles.get(i, ext.get(i, str(i))) for i in p["disliked"]) or "-")
        elif p["disliked"]:
            lines[-2] = "Likes: - · Dislikes: " + ", ".join(snapshot_titles.get(i, ext.get(i, str(i))) for i in p["disliked"])
        lines += ["| # | S5B baseline | votes | rating | | Proposed (" + recommended + ") | votes | rating | |",
                  "|---|---|---:|---:|---|---|---:|---:|---|"]
        base, new = policies.get("s5b_snapshot_prior", []), policies.get(recommended, [])
        for r in range(max(len(base), len(new))):
            def cell(items):
                if r >= len(items):
                    return " | | | "
                m = items[r]
                return f"{'D ' if m.get('dynamic') else ''}{m['title']} ({m.get('year') or '?'}) | {m['votes']} | {m['rating']} | "
            lines.append(f"| {r + 1} | {cell(base)}| {cell(new)}|")
        lines.append("")
    return "\n".join(lines)


_TITLES = None


def load_title_index():
    global _TITLES
    if _TITLES is None:
        _TITLES = json.loads(DATASETS["tmdb"].read_text(encoding="utf-8"))
    return _TITLES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evaluation" / "s5d-results.json")
    parser.add_argument("--review", type=Path, default=ROOT / "docs" / "evaluation" / "s5d-review.md")
    parser.add_argument("--recommended", default="pool_prior_related_confidence", choices=sorted(POLICIES))
    args = parser.parse_args()
    full = load_dataset("tmdb").movies
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    proxy = world_proxy(full)
    live, review = live_replay(fixture, args.recommended)
    result = {"version": 1, "seed": SEED, "k": K, "explain_floor": EXPLAIN_FLOOR, "policies": POLICIES,
              "default_policy": DISCOVERY_POLICY, "recommended_policy": args.recommended,
              "inputs": {"snapshot_sha256": sha(DATASETS["tmdb"]), "live_fixture_sha256": sha(FIXTURE),
                         "live_fixture_recorded": fixture["recorded"], "feature_version": fixture["feature_version"]},
              "runtime": {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
              "world_proxy": proxy, "live_replay": live, "vocabulary": vocabulary_coverage(fixture)}
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    args.review.write_text(review_sheet(fixture, review, args.recommended), encoding="utf-8")
    print(json.dumps({"live_replay": live, "vocabulary": result["vocabulary"]}, indent=1))


if __name__ == "__main__":
    main()
