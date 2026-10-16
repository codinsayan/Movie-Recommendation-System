"""Export the trained recommender to JSON for the static (GitHub Pages) build.

Usage:  python scripts/export_static.py [output_path]

The browser engine (frontend/engine.js) loads this file and reproduces
/api/recommend, /api/movies/{id}/similar and /api/meta without a server.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import recommender as rec  # noqa: E402

DEFAULT_OUT = ROOT / "frontend" / "data" / "model.json"


def sparse_rows(matrix) -> list[list[list[float]]]:
    return [[[int(j), float(row[j])] for j in row.nonzero()[0]] for row in matrix]


def build_model(engine: rec.Recommender) -> dict:
    # Similarity matrices are n x n, so ship the sparse item vectors instead and
    # let the browser compute X·Xᵀ and C·Cᵀ on load (milliseconds for ~500 films).
    return {
        "version": 2,
        "movies": engine.movies,
        "vocab": {t: int(i) for t, i in engine.vectorizer.vocabulary_.items()},
        "idf": engine.vectorizer.idf_.tolist(),
        "X": sparse_rows(engine.X),
        "C": sparse_rows(engine.C),
        "quality": engine.quality.tolist(),
        "meta": engine.meta(),
        "config": {
            "weights": rec.WEIGHTS,
            "moodWeights": rec.MOOD_WEIGHTS,
            "dislikePenalty": rec.DISLIKE_PENALTY,
            "moodBoost": rec.MOOD_BOOST,
            "mmrLambda": rec.MMR_LAMBDA,
            "moodSynonyms": rec.MOOD_SYNONYMS,
        },
    }


def export(out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_model(rec.load_default()), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


if __name__ == "__main__":
    path = export(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT)
    print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
