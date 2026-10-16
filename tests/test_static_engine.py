"""The browser engine (frontend/engine.js) must give the same answers as Python."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from export_static import export  # noqa: E402
from recommender import load_default  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

CASES = [
    {"liked": [1, 2], "disliked": [], "mood": None, "k": 12},
    {"liked": [16, 21], "disliked": [45], "mood": None, "k": 12},
    {"liked": [1, 2, 4, 7], "disliked": [46], "mood": None, "k": 100},
    {"liked": [], "disliked": [], "mood": "something scary", "k": 8},
    {"liked": [], "disliked": [], "mood": "cozy and heartwarming", "k": 8},
    {"liked": [9], "disliked": [45, 46, 48], "mood": "space, make me cry", "k": 10},
    {"liked": [], "disliked": [], "mood": None, "k": 12},
]
SIMILAR = [1, 16, 45, 60]

NODE_SCRIPT = """
const Engine = require(process.argv[1]);
const e = new Engine(require(process.argv[2]));
const {cases, similar} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
console.log(JSON.stringify({
  recs: cases.map(c => e.recommend(c.liked, c.disliked, c.mood, c.k)),
  sims: similar.map(id => e.similar(id, 6)),
}));
"""


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    model = export(tmp_path_factory.mktemp("static") / "model.json")
    proc = subprocess.run(
        [NODE, "-e", NODE_SCRIPT, str(ROOT / "frontend" / "engine.js"), str(model)],
        input=json.dumps({"cases": CASES, "similar": SIMILAR}),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def engine():
    return load_default()


@pytest.mark.parametrize("i", range(len(CASES)))
def test_recommend_parity(engine, results, i):
    c = CASES[i]
    py = engine.recommend(c["liked"], c["disliked"], c["mood"], c["k"])
    js = results["recs"][i]
    assert js["mode"] == py["mode"]
    assert js["taste"] == py["taste"]
    if py["mode"] == "popular":
        # equal ratings tie, and numpy's argsort is not stable: compare scores only
        assert [m["score"] for m in js["items"]] == [m["score"] for m in py["items"]]
        return
    assert [m["id"] for m in js["items"]] == [m["id"] for m in py["items"]]
    for a, b in zip(js["items"], py["items"]):
        assert (a["match"], a["reason"], a["shared"], a["because"]) == (b["match"], b["reason"], b["shared"], b["because"])
        assert a["score"] == pytest.approx(b["score"], abs=1e-4)


@pytest.mark.parametrize("i", range(len(SIMILAR)))
def test_similar_parity(engine, results, i):
    py = engine.similar(SIMILAR[i], 6)
    js = results["sims"][i]
    assert [m["id"] for m in js] == [m["id"] for m in py]
    assert [m["shared"] for m in js] == [m["shared"] for m in py]
