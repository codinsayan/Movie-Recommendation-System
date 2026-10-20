"""Reproducible S5 proxy evaluation, runtime measurements and relevance-review cards.

Run: python scripts/evaluate_viewing.py --output docs/evaluation/s5-results.json
These proxies do not establish real-user relevance or causality. No network is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from export_static import build_model  # noqa: E402
from recommender import DATASETS, load_dataset  # noqa: E402
from viewing import VIEWING_CONFIG, canonical_key  # noqa: E402

SEED = 2026
K = 10


def make_profiles(engine, limit=60):
    """Fix one explicit like, one simulated viewed seed and one hidden target."""
    rng = np.random.default_rng(SEED)
    profiles = []
    if engine.ratings is not None:
        for row in engine.ratings:
            positives = np.flatnonzero(row >= 4)
            if len(positives) >= 3:
                liked, watched, target = rng.choice(positives, 3, replace=False).tolist()
                profiles.append((liked, watched, target))
    else:
        # The bundled graph is used both in training and in this transductive proxy.
        # This is neighbour recovery, NOT held-out human viewing evidence.
        for watched in rng.permutation(engine.n):
            neighbours = [engine.by_id[mid] for mid in engine.movies[watched].get("tmdb_recs", [])
                          if mid in engine.by_id and mid != engine.movies[watched]["id"]]
            neighbours = sorted(set(neighbours))
            if len(neighbours) >= 2:
                liked, target = rng.choice(neighbours, 2, replace=False).tolist()
                profiles.append((liked, int(watched), target))
    return profiles[:limit]


def evaluate(engine, profiles):
    output = {}
    for variant in ["popularity", "explicit_hybrid", "hybrid_with_viewing"]:
        hits, ndcg, diversity, coverage, latency = [], [], [], set(), []
        for liked, watched, target in profiles:
            keys = [canonical_key(m) for i, m in enumerate(engine.movies) if i not in {liked, watched}]
            options = {"eligible_keys": keys, "k": K}
            if variant != "popularity":
                options["liked"] = [engine.movies[liked]["id"]]
            if variant == "hybrid_with_viewing":
                options.update(use_viewing=True, viewing={"version": 1, "signals": [{
                    "key": canonical_key(engine.movies[watched]), "duration": 600,
                    "watched_seconds": 180, "plays": 1, "updated_at": 0}], "playback": []})
            started = time.perf_counter()
            out = engine.recommend(**options)
            latency.append((time.perf_counter() - started) * 1000)
            ids = [m["id"] for m in out["items"]]
            target_id = engine.movies[target]["id"]
            hit = target_id in ids
            hits.append(int(hit))
            ndcg.append(1 / math.log2(ids.index(target_id) + 2) if hit else 0)
            indices = [engine.by_id[mid] for mid in ids]
            coverage.update(indices)
            pairs = [1 - engine.content_sim[a, b] for i, a in enumerate(indices) for b in indices[i + 1:]]
            diversity.append(float(np.mean(pairs)) if pairs else 0)
        output[variant] = {"hit_rate_at_10": round(statistics.mean(hits), 4),
                           "ndcg_at_10": round(statistics.mean(ndcg), 4),
                           "coverage": round(len(coverage) / engine.n, 4),
                           "intra_list_diversity": round(statistics.mean(diversity), 4),
                           "median_ms": round(statistics.median(latency), 3),
                           "p95_ms": round(float(np.percentile(latency, 95)), 3)}
    return output


def node_measurement(model):
    if not shutil.which("node"):
        return {"available": False}
    script = """
const {performance} = require('node:perf_hooks');
const E = require(process.argv[1]);
const before = process.memoryUsage(), started = performance.now();
const engine = new E(require(process.argv[2]));
const startup = performance.now() - started;
const payload = {version:1, signals:[{key:`${engine.movies[0].source}:${engine.movies[0].id}`,
  duration:600, watched_seconds:180, plays:1, updated_at:0}], playback:[]};
const timings=[];
for(let i=0;i<25;i++) {
 const start=performance.now();
 engine.recommend([engine.movies[1].id],[],null,100,{viewing:payload,use_viewing:true});
 timings.push(performance.now()-start);
}
timings.sort((a,b)=>a-b);
console.log(JSON.stringify({available:true,runtime:process.version,startup_ms:+startup.toFixed(3),
 heap_delta_mib:+((process.memoryUsage().heapUsed-before.heapUsed)/1024/1024).toFixed(3),
 array_buffer_delta_mib:+((process.memoryUsage().arrayBuffers-before.arrayBuffers)/1024/1024).toFixed(3),
 median_request_ms:+timings[12].toFixed(3),p95_request_ms:+timings[23].toFixed(3)}));
"""
    # Explicit temporary root keeps this runnable in the workspace sandbox too.
    with tempfile.TemporaryDirectory(prefix="s5-eval-", dir=ROOT / "frontend/data") as task_dir:
        path = Path(task_dir) / "model.json"
        path.write_text(json.dumps(model), encoding="utf-8")
        proc = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "frontend/engine.js"), str(path)],
                              capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)


def review_cards(engine):
    titles = {movie["title"]: movie for movie in engine.movies}
    first = titles.get("Inception", engine.movies[0])
    watched = titles.get("Interstellar", engine.movies[1])
    options = {"liked": [first["id"]], "use_viewing": True, "viewing": {"version": 1, "signals": [{
        "key": canonical_key(watched), "duration": 600, "watched_seconds": 180, "plays": 1}], "playback": []}}
    # Match the application's k=100 request and then display the first five.
    items = engine.recommend(**options, k=100)["items"][:5]
    review_path = ROOT / "docs/evaluation/s5-human-review.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() and first.get("source") == "tmdb" else None
    return {"liked": first["title"], "watched": watched["title"],
            "recommendations": [{"title": m["title"], "reason": m["reason"]} for m in items],
            "human_review": review or "not reviewed; experimental ranking remains opt-in"}


def run():
    results = {"protocol_version": 1, "seed": SEED, "k": K, "viewing_policy": VIEWING_CONFIG,
               "default_enabled": False, "python": sys.version.split()[0], "numpy": np.__version__, "datasets": {}}
    (ROOT / "frontend/data").mkdir(parents=True, exist_ok=True)
    for name in ["curated", "tmdb"]:
        started = time.perf_counter()
        engine = load_dataset(name)
        startup_ms = (time.perf_counter() - started) * 1000
        profiles = make_profiles(engine)
        if not profiles:
            raise ValueError(f"No usable profiles in {name}")
        model = build_model(engine)
        arrays = sum(value.nbytes for value in [engine.X, engine.C, engine.content_sim, engine.collab_sim, engine.quality])
        results["datasets"][name] = {
            "movies": engine.n, "collaborative_source": engine.collab_source, "profiles": len(profiles),
            "snapshot_sha256": hashlib.sha256(DATASETS[name].read_bytes()).hexdigest(),
            "profiles_sha256": hashlib.sha256(json.dumps(profiles).encode()).hexdigest(),
            "provenance": "seed-42 simulated ratings; synthetic viewing" if name == "curated" else
                          "bundled TMDB graph; transductive neighbour recovery; synthetic viewing",
            "metrics": evaluate(engine, profiles), "python_startup_ms": round(startup_ms, 3),
            "python_model_arrays_mib": round(arrays / 1024 ** 2, 3),
            "static_model_kib": round(len(json.dumps(model, ensure_ascii=False, separators=(",", ":")).encode()) / 1024, 3),
            "node": node_measurement(model), "review": review_cards(engine)}
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(serialized)
