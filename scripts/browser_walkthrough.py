"""S5D rendered-browser walkthrough and responsiveness measurement (headless Microsoft Edge).

Usage:  python scripts/browser_walkthrough.py [--output docs/evaluation/s5d-browser.json]

Prerequisite: the backend is running (python run.py) on --backend. The script also serves
the static build on --static-port. It writes temporary harness files into frontend/
(_walk*.html/js) and always deletes them. The real app is driven through its own DOM:
seeded likes -> Top Picks with Discovered cards -> open a discovered film -> like it from
details -> Watch -> dislike another discovered film -> rapid toggles. An injected probe
records every fetch (including aborted ones) and main-thread long tasks. Desktop and
mobile screenshots of the details window are saved for visual review.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
EDGE_PATHS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "msedge", "microsoft-edge", "chromium", "google-chrome"]
RECEIVER_PORT = 8099

PROBE = r"""(function () {
  const realFetch = window.fetch.bind(window);
  const log = window.__walk = { fetches: [], longtasks: [], realFetch };
  window.fetch = function (url, options) {
    const rec = { url: String(url).replace(location.origin, ""), t0: performance.now(), status: null, aborted: false };
    log.fetches.push(rec);
    return realFetch(url, options).then((r) => { rec.status = r.status; rec.ms = performance.now() - rec.t0; return r; },
      (e) => { rec.aborted = e.name === "AbortError"; rec.error = e.name; rec.ms = performance.now() - rec.t0; throw e; });
  };
  try { new PerformanceObserver((list) => list.getEntries().forEach((e) => log.longtasks.push({ start: e.startTime, ms: e.duration })))
    .observe({ type: "longtask", buffered: true }); } catch { /* not supported */ }
  const q = new URLSearchParams(location.search);
  const likes = (q.get("likes") || "").split(",").filter(Boolean).map(Number);
  if (likes.length && !sessionStorage.getItem("walk-seeded")) {
    localStorage.setItem("cinemagic:preferences:v2", JSON.stringify({ version: 2, legacyImported: true,
      profiles: { tmdb: { liked: likes, disliked: [], mood: "" } } }));
    sessionStorage.setItem("walk-seeded", "1");
  }
})();"""

DRIVER = r"""(async function () {
  const q = new URLSearchParams(location.search), scenario = q.get("scenario"), shot = q.get("shot");
  const W = window.__walk, out = { scenario, steps: [], errors: [] };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function waitFor(fn, timeout = 30000) {
    const t0 = performance.now();
    for (;;) { const v = fn(); if (v) return v; if (performance.now() - t0 > timeout) throw new Error("timeout"); await sleep(25); }
  }
  const picks = () => [...document.querySelectorAll("#row-picks .scroller .tile")];
  const pickIds = () => picks().map((t) => Number(t.dataset.id));
  const recs = () => W.fetches.filter((f) => f.url.includes("/api/recommend"));
  const step = (name, data) => out.steps.push({ name, ...data });
  async function measureTaste(button, id, viaApi = true) {
    const before = recs().length, t0 = performance.now();
    button.click();
    if (!viaApi) {   // static mode ranks in the browser engine: no request to wait for
      await waitFor(() => !pickIds().includes(id));
      return { visible_ms: Math.round(performance.now() - t0) };
    }
    const req = await waitFor(() => recs().length > before && recs()[recs().length - 1].status !== null && recs()[recs().length - 1]);
    const fetched = performance.now() - t0;
    await waitFor(() => !pickIds().includes(id));
    return { fetch_ms: Math.round(fetched), visible_ms: Math.round(performance.now() - t0), server_ms: Math.round(req.ms) };
  }
  try {
    const backend = scenario !== "static";
    await waitFor(() => picks().length >= 6, 60000);
    if (backend) await waitFor(() => document.querySelector("#row-picks .badge-discovered"), 60000);
    const head = document.querySelector("#row-picks .row-head")?.innerText.replace(/\s+/g, " ").trim();
    step("boot", { ms: Math.round(performance.now()), picks: picks().length,
      discovered_badges: document.querySelectorAll("#row-picks .badge-discovered").length, subtitle: head });
    if (!backend) {
      const tile = picks()[0], id = Number(tile.dataset.id);
      tile.click();
      await waitFor(() => document.querySelector("#modalBody [data-act=love]"));
      step("static_like", { title: document.querySelector("#modalTitle").textContent, ...(await measureTaste(document.querySelector("#modalBody [data-act=love]"), id, false)) });
    } else {
      // 1. Open a discovered film's details.
      let tile = document.querySelector("#row-picks .badge-discovered").closest(".tile");
      let id = Number(tile.dataset.id);
      tile.click();
      await waitFor(() => document.querySelector("#modalBody .why") && !/Loading/.test(document.querySelector("#modalTitle")?.textContent || ""));
      const why = document.querySelector("#modalBody").innerText;
      step("discovered_details", { title: document.querySelector("#modalTitle").textContent,
        provenance: /Discovered outside the downloaded catalogue/.test(why), because: (why.match(/Because you \w+:? [^\n]*/) || [""])[0],
        reason_line: why.split("\n").find((l) => /widen|related-title|summary metadata/.test(l)) || "",
        watch_button: !!document.querySelector("#modalBody [data-watch]") });
      if (shot) { document.body.dataset.walkReady = "1"; return; }
      // 2. Like it from the details window: it leaves Top Picks.
      step("like_discovered", await measureTaste(document.querySelector("#modalBody [data-act=love]"), id));
      // 3. Watch it: the player gets a provider frame for this TMDB ID.
      document.querySelector("#modalBody [data-watch]").click();
      const frame = await waitFor(() => document.querySelector("#movieFrame iframe"), 15000);
      step("watch", { provider_host: new URL(frame.src).host, uses_tmdb_id: frame.src.includes(String(id)) });
      document.querySelector("[data-close]")?.click();
      await sleep(300);
      // 4. Dislike another discovered film from its details.
      tile = await waitFor(() => document.querySelector("#row-picks .badge-discovered")?.closest(".tile"));
      id = Number(tile.dataset.id);
      tile.click();
      await waitFor(() => document.querySelector("#modalBody [data-act=nope]") && !/Loading/.test(document.querySelector("#modalTitle")?.textContent || ""));
      const title = document.querySelector("#modalTitle").textContent;
      step("dislike_discovered", { title, ...(await measureTaste(document.querySelector("#modalBody [data-act=nope]"), id)) });
      document.querySelector("[data-close]")?.click();
      await sleep(300);
      // 5. Rapid toggles: older requests must be aborted and the final rows must reflect the last state.
      tile = picks()[0]; id = Number(tile.dataset.id);
      tile.click();
      const love = await waitFor(() => document.querySelector("#modalBody [data-act=love]"));
      const before = recs().length;
      love.click(); await sleep(40); love.click(); await sleep(40); love.click();
      await waitFor(() => !pickIds().includes(id), 30000);
      await sleep(1500);
      const burst = recs().slice(before);
      step("rapid_toggles", { requests: burst.length, aborted: burst.filter((f) => f.aborted).length,
        final_liked: document.querySelector("#modalBody [data-act=love]").getAttribute("aria-pressed") === "true",
        absent_from_picks: !pickIds().includes(id) });
    }
  } catch (e) { out.errors.push(String(e && e.stack || e)); }
  out.longtasks = { count: W.longtasks.length, total_ms: Math.round(W.longtasks.reduce((s, t) => s + t.ms, 0)),
    max_ms: Math.round(Math.max(0, ...W.longtasks.map((t) => t.ms))) };
  out.recommend_requests = recs().map((f) => ({ status: f.status, aborted: f.aborted, ms: Math.round(f.ms || 0) }));
  out.console_errors = window.__walkErrors || [];
  await W.realFetch(`http://127.0.0.1:__PORT__/${scenario}`, { method: "POST", mode: "no-cors", body: JSON.stringify(out) });
})();
window.addEventListener("error", (e) => (window.__walkErrors ||= []).push(String(e.message)));"""


def edge():
    for path in EDGE_PATHS:
        found = shutil.which(path) or (path if Path(path).exists() else None)
        if found:
            return found
    sys.exit("Microsoft Edge or Chromium is required for the browser walkthrough.")


class Receiver(BaseHTTPRequestHandler):
    results: dict = {}

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        Receiver.results[self.path.strip("/")] = json.loads(body)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


def write_harness():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head>\n  <script src="_walk_probe.js"></script>', 1)
    html = html.replace("</body>", '  <script src="_walk_driver.js"></script>\n</body>', 1)
    (FRONTEND / "_walk.html").write_text(html, encoding="utf-8")
    (FRONTEND / "_walk_probe.js").write_text(PROBE, encoding="utf-8")
    (FRONTEND / "_walk_driver.js").write_text(DRIVER.replace("__PORT__", str(RECEIVER_PORT)), encoding="utf-8")
    # Headless windows cannot be narrower than about 500 px, so phone layouts render in a 390 px iframe.
    (FRONTEND / "_walk_frame.html").write_text(FRAME, encoding="utf-8")


FRAME = """<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#000}iframe{border:0;display:block}</style>
<iframe id="f" width="390" height="844"></iframe><script>f.src = "_walk.html" + location.search;</script>"""


def remove_harness():
    for name in ("_walk.html", "_walk_probe.js", "_walk_driver.js", "_walk_frame.html"):
        (FRONTEND / name).unlink(missing_ok=True)


def run_flow(browser, url, scenario, timeout=120):
    with tempfile.TemporaryDirectory() as profile:
        proc = subprocess.Popen([browser, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
                                 "--window-size=1440,900", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + timeout
            while scenario not in Receiver.results and time.time() < deadline:
                time.sleep(0.5)
        finally:
            proc.kill()
            proc.wait()
            time.sleep(1)
    return Receiver.results.get(scenario, {"scenario": scenario, "errors": ["no result before timeout"]})


def screenshot(browser, url, path, size):
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
                        "--hide-scrollbars", f"--window-size={size}", "--virtual-time-budget=45000",
                        f"--screenshot={path}", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8000/")
    parser.add_argument("--static-port", type=int, default=8091)
    parser.add_argument("--likes", default="862,14160,354912", help="seeded TMDB likes (default Toy Story, Up, Coco)")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evaluation" / "s5d-browser.json")
    parser.add_argument("--screens", type=Path, default=ROOT / "docs" / "evaluation" / "screens")
    args = parser.parse_args()
    browser = edge()
    receiver = HTTPServer(("127.0.0.1", RECEIVER_PORT), Receiver)
    threading.Thread(target=receiver.serve_forever, daemon=True).start()

    class Quiet(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(FRONTEND), **kw)

        def log_message(self, *_):
            pass
    static = ThreadingHTTPServer(("127.0.0.1", args.static_port), Quiet)
    threading.Thread(target=static.serve_forever, daemon=True).start()
    write_harness()
    try:
        backend = run_flow(browser, f"{args.backend}_walk.html?scenario=backend&likes={args.likes}", "backend")
        static_run = run_flow(browser, f"http://127.0.0.1:{args.static_port}/_walk.html?scenario=static&likes={args.likes}", "static")
        args.screens.mkdir(parents=True, exist_ok=True)
        shots = {}
        for name, page, size in (("desktop", "_walk.html", "1440,900"), ("mobile", "_walk_frame.html", "600,844")):
            path = args.screens / f"s5d-discovered-details-{name}.png"
            screenshot(browser, f"{args.backend}{page}?scenario=shot-{name}&shot=1&likes={args.likes}", path, size)
            if name == "mobile" and path.exists():
                try:
                    from PIL import Image
                    with Image.open(path) as image:
                        image.crop((0, 0, 390, 844)).save(path)
                except ImportError:
                    pass   # the uncropped image still shows the 390 px frame on the left
            shots[name] = str(path.relative_to(ROOT)).replace(os.sep, "/") if path.exists() else None
    finally:
        remove_harness()
        static.shutdown()
        receiver.shutdown()
    result = {"recorded": time.strftime("%Y-%m-%d"), "browser": Path(browser).name, "likes": args.likes,
              "backend": backend, "static": static_run, "screenshots": shots}
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
