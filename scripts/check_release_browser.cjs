/* S6 real-browser DOM checks. Node >=22, Python dependencies and Chromium required.
 * Starts isolated local servers/profile; blocks third-party movie frames deliberately.
 * Synthetic messages exercise lifecycle; these results never establish video playback.
 * Usage: node scripts/check_release_browser.cjs --recorded 2026-10-20
 */
"use strict";
const fs = require("node:fs"), path = require("node:path"), os = require("node:os");
const http = require("node:http"), { spawn } = require("node:child_process");
const net = require("node:net");
const assert = require("node:assert/strict");
const ROOT = path.resolve(__dirname, ".."), FRONTEND = path.join(ROOT, "frontend");
const OUT = path.join(ROOT, "docs", "evaluation", "s6");
const recorded = process.argv[process.argv.indexOf("--recorded") + 1];
if (!process.argv.includes("--recorded") || !/^\d{4}-\d{2}-\d{2}$/.test(recorded)) throw Error("Supply --recorded YYYY-MM-DD");
const browser = process.env.CHROMIUM_PATH || [
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/chromium", "/usr/bin/google-chrome",
].find(p => fs.existsSync(p));
if (!browser) throw Error("Set CHROMIUM_PATH to an installed Chromium browser");
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(fn, label, timeout = 20000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { const result = await fn(); if (result) return result; await sleep(100); }
  throw Error("Timed out: " + label);
}
async function connect(url) {
  const ws = new WebSocket(url), pending = new Map(); let id = 0;
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  ws.onmessage = event => {
    const message = JSON.parse(event.data), item = pending.get(message.id);
    if (!item) return;
    pending.delete(message.id); clearTimeout(item.timer);
    if (message.error) item.reject(Error(JSON.stringify(message.error))); else item.resolve(message.result);
  };
  return { close: () => ws.close(), send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const serial = ++id, timer = setTimeout(() => { pending.delete(serial); reject(Error(method + " timed out")); }, 15000);
      pending.set(serial, { resolve, reject, timer }); ws.send(JSON.stringify({ id: serial, method, params }));
    });
  } };
}
let server, chrome, staticServer, client;
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "cinemagic-s6-"));
async function backend(providers) {
  if (server && server.exitCode === null) { const previous = server; await new Promise(resolve => { previous.once("exit", resolve); previous.kill(); }); }
  server = spawn(process.env.PYTHON || "python", ["-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8126"], {
    cwd: ROOT, windowsHide: true, stdio: "ignore", env: { ...process.env, TMDB_READ_ACCESS_TOKEN: "", TMDB_API_KEY: "",
      CINEMAGIC_DATASET: "tmdb", CINEMAGIC_PROVIDERS: providers, CINEMAGIC_RANKING: "dynamic" },
  });
  await until(async () => {
    if (server.exitCode !== null) throw Error("Test backend exited during startup");
    try { return (await fetch("http://127.0.0.1:8126/api/health")).ok; } catch { return false; }
  }, "backend startup");
}
async function evaluate(expression) {
  const response = await client.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (response.exceptionDetails) throw Error(response.exceptionDetails.text + ": " + response.exceptionDetails.exception?.description);
  return response.result.value;
}
const wait = (expression, label) => until(() => evaluate(expression), label);
const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
async function key(selector, key, extras = {}) {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus();document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:${JSON.stringify(key)},bubbles:true,cancelable:true,...${JSON.stringify(extras)}}))`);
}
async function closeModal() { await click("#modalBody [data-close]"); await wait("!document.querySelector('#modal').classList.contains('open')", "modal closed"); }
async function screenshot(name) {
  const shot = await client.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, name + ".png"), Buffer.from(shot.data, "base64"));
}
async function searchMovie() {
  await click("#searchToggle");
  await evaluate("const input=document.querySelector('#searchInput');input.value='Inception';input.dispatchEvent(new Event('input',{bubbles:true}))");
  await wait("document.querySelector('#rowList .tile[data-id=\"27205\"]')", "debounced Inception search");
  await click('#rowList .tile[data-id="27205"]');
  await wait("document.querySelector('#modalTitle')?.textContent==='Inception'", "movie details");
}
async function openPlayer() {
  await click('#modalBody [data-watch="27205"]');
  await wait("document.querySelector('#movieFrame iframe')", "movie iframe");
  await wait("document.activeElement?.classList.contains('m-close')", "modal initial focus");
}
async function message(data, origin = "https://cinesrc.st") {
  await evaluate(`window.dispatchEvent(new MessageEvent('message',{origin:${JSON.stringify(origin)},source:document.querySelector('#movieFrame iframe').contentWindow,data:${JSON.stringify(data)}}))`);
}
async function flow(base, width, label) {
  await client.send("Emulation.setDeviceMetricsOverride", { width, height: width < 600 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 600 });
  await client.send("Page.navigate", { url: base });
  await wait("document.querySelector('.bb-title') && document.querySelector('#row-picks .tile')", "boot picks");
  await searchMovie();
  await click('#modalBody [data-act="love"][data-id="27205"]');
  await openPlayer();
  assert.equal(await evaluate("CinemagicProviders.list().length"), 3);
  assert.equal(await evaluate("document.querySelector('#movieFrame iframe').hasAttribute('sandbox')"), false);
  assert.match(await evaluate("document.querySelector('#movieFrame iframe').allow"), /fullscreen/);
  await click('#modalBody [data-watchlist="27205"]');
  await evaluate("window.__s6OldFrame=document.querySelector('#movieFrame iframe')");
  await message({ type: "cinesrc:timeupdate", currentTime: 90, duration: 900 });
  await message({ type: "cinesrc:timeupdate", currentTime: 700, duration: 900 }, "https://wrong.example");
  await message({ type: "cinesrc:error" });
  assert.match(await evaluate("document.querySelector('#movieStatus').textContent"), /Choose another source/);
  assert.equal(await evaluate("document.querySelector('#movieFrame iframe')===window.__s6OldFrame"), true);
  await click(".source-trigger");
  await key(".source-trigger", "End"); await key(".source-trigger", "Enter");
  assert.equal(await evaluate("document.querySelector('#movieSource').value"), "vidsrc");
  assert.equal(await evaluate("document.querySelectorAll('#movieFrame iframe').length"), 1);
  assert.match(await evaluate("document.querySelector('#movieFrame iframe').src"), /startAt=90/);
  assert.match(await evaluate("document.querySelector('#movieFrame iframe').src"), /autoplay=1/);
  const status = await evaluate("document.querySelector('#movieStatus').textContent");
  await evaluate("window.dispatchEvent(new MessageEvent('message',{origin:'https://cinesrc.st',source:window.__s6OldFrame.contentWindow,data:{type:'cinesrc:error'}}))");
  assert.equal(await evaluate("document.querySelector('#movieStatus').textContent"), status);
  // Escape closes just the menu first; Tab is trapped at the dialog boundary.
  await click(".source-trigger"); await key(".source-trigger", "Escape");
  assert.equal(await evaluate("document.querySelector('#modal').classList.contains('open')"), true);
  assert.equal(await evaluate("document.querySelector('.source-menu').hidden"), true);
  await key("#movieForget", "Tab");
  assert.equal(await evaluate("document.activeElement.classList.contains('m-close')"), true);
  assert.equal(await evaluate("document.querySelector('.movie-player').scrollWidth <= document.querySelector('.movie-player').clientWidth+1"), true);
  assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth+1"), true);
  await screenshot(label + "-player");
  await closeModal();
  assert.equal(await evaluate("document.querySelectorAll('#movieFrame iframe').length"), 0);
  await client.send("Page.reload", { ignoreCache: true });
  await wait("document.querySelector('.bb-title') && document.querySelector('#row-picks .tile')", "refresh picks");
  await searchMovie(); await openPlayer();
  assert.equal(await evaluate("document.querySelector('#movieSource').value"), "vidsrc");
  assert.match(await evaluate("document.querySelector('#movieFrame iframe').src"), /startAt=90/);
  assert.equal(await evaluate("document.querySelector('#modalBody [data-watchlist]').getAttribute('aria-pressed')"), "true");
  const prefs = await evaluate("JSON.parse(localStorage.getItem('cinemagic:preferences:v2')).profiles.tmdb.liked");
  assert.ok(prefs.includes(27205));
  await click("#movieRestart");
  assert.equal(await evaluate("new URL(document.querySelector('#movieFrame iframe').src).searchParams.has('startAt')"), false);
  await message({ type: "PLAYER_EVENT", data: { player_status: "playing", player_progress: 90, player_duration: 900, player_info: { mediaType: "movie", tmdb: 27205 } } }, "https://vidsrc.sh");
  // Replacing a movie with its trailer must dispose the old frame as well.
  await click('#modalBody [data-close]');
  await click('#rowList .tile[data-id="27205"]');
  await wait("document.querySelector('#modalBody [data-trailer]')", "trailer action");
  await click('#modalBody [data-trailer]');
  assert.equal(await evaluate("document.querySelectorAll('#modalBody iframe').length"), 1);
  assert.equal(await evaluate("document.querySelector('#movieFrame')===null"), true);
  assert.match(await evaluate("document.querySelector('#modalBody iframe').src"), /^https:\/\/www.youtube-nocookie.com\//);
  await closeModal(); await click("#searchClear");
  await click("#tasteBtn");
  await wait("document.querySelector('#useViewing')", "viewing options");
  await click("#useViewing"); await click("#recentPlaybackOnly");
  await wait("document.querySelector('.bb-title')?.textContent.length > 0 && document.querySelector('[data-show-all-picks]')", "explicit recent-playback empty state");
  await screenshot(label + "-filters");
  await click("#useViewing"); await click("#recentPlaybackOnly");
  await client.send("Page.navigate", { url: "about:blank" });
  await wait("location.href==='about:blank' && document.readyState==='complete'", "detached test document");
  return { label, viewport: [width, width < 600 ? 844 : 900], passed: ["boot", "debounced snapshot search", "details", "watch", "registry permissions", "manual keyboard source switch", "no switch on error", "wrong-origin and stale-frame rejection", "resume URL transfer", "autoplay request and pause guidance", "menu Escape", "modal focus trap", "no horizontal overflow", "close disposal", "refresh retains resume/watchlist/likes/source", "start over", "trailer replaces movie", "recent-playback empty state"], video_playback: "not tested; third-party frames blocked", screenshots: [label + "-player.png", label + "-filters.png"] };
}

(async () => {
  const results = { recorded, browser: path.basename(browser), scope: "Local release candidate; real DOM with blocked external frames and synthetic progress/errors", scenarios: [] };
  try {
    fs.mkdirSync(OUT, { recursive: true });
    for (const port of [8126, 8127]) {
      await new Promise((resolve, reject) => {
        const probe = net.createServer(); probe.once("error", reject);
        probe.listen(port, "127.0.0.1", () => probe.close(resolve));
      });
    }
    await backend("cinesrc,vidlink,vidsrc");
    staticServer = http.createServer((request, response) => {
      const name = path.resolve(FRONTEND, "." + decodeURIComponent(request.url.split("?")[0] === "/" ? "/index.html" : request.url.split("?")[0]));
      if (!name.startsWith(FRONTEND + path.sep) || !fs.existsSync(name) || !fs.statSync(name).isFile()) { response.writeHead(404); return response.end(); }
      const mime = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".jpg": "image/jpeg", ".png": "image/png" };
      response.setHeader("Content-Type", mime[path.extname(name)] || "application/octet-stream"); fs.createReadStream(name).pipe(response);
    }).listen(8127, "127.0.0.1");
    chrome = spawn(browser, ["--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { windowsHide: true, stdio: "ignore" });
    const portFile = path.join(profile, "DevToolsActivePort");
    await until(() => fs.existsSync(portFile), "browser DevTools");
    const port = fs.readFileSync(portFile, "utf8").split("\n")[0];
    const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    client = await connect(tabs.find(tab => tab.type === "page").webSocketDebuggerUrl);
    await client.send("Page.enable"); await client.send("Runtime.enable"); await client.send("Network.enable");
    await client.send("Network.setBlockedURLs", { urls: ["*://cinesrc.st/*", "*://vidlink.pro/*", "*://vidsrc.sh/*", "*://www.youtube-nocookie.com/*"] });
    await client.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
    for (const [base, width, name] of [["http://127.0.0.1:8126/", 1440, "backend-desktop"], ["http://127.0.0.1:8126/", 390, "backend-mobile"], ["http://127.0.0.1:8127/", 1440, "static-desktop"], ["http://127.0.0.1:8127/", 390, "static-mobile"]]) {
      // Independent flow; retain state inside its refresh exercise only.
      await client.send("Storage.clearDataForOrigin", { origin: new URL(base).origin, storageTypes: "local_storage" });
      results.scenarios.push(await flow(base, width, name));
    }
    await backend("");
    await client.send("Page.navigate", { url: "http://127.0.0.1:8126/" });
    await wait("document.querySelector('#row-picks .tile')", "disabled-provider boot");
    await searchMovie();
    assert.equal(await evaluate("CinemagicProviders.list().length"), 0);
    assert.match(await evaluate("document.querySelector('.playback-unavailable').textContent"), /sources are currently unavailable/);
    assert.equal(await evaluate("document.querySelector('#modalBody [data-watch]')===null"), true);
    assert.equal(await evaluate("JSON.parse(localStorage.getItem('cinemagic:preferences:v2')).profiles.tmdb.liked.includes(27205)"), true);
    await screenshot("backend-disabled-sources");
    results.scenarios.push({ label: "disabled-provider restart", passed: ["no enabled providers", "explicit unavailable state", "recommendations remain", "browser likes preserved"], screenshots: ["backend-disabled-sources.png"] });
    await client.send("Page.navigate", { url: "about:blank" });
    await backend("cinesrc");
    await client.send("Page.navigate", { url: "http://127.0.0.1:8126/" });
    await wait("document.querySelector('#row-picks .tile')", "single-provider boot");
    await searchMovie(); await openPlayer();
    assert.equal(await evaluate("document.querySelector('#movieSource').value"), "cinesrc");
    assert.equal(await evaluate("document.querySelector('#movieSource').children.length"), 1);
    assert.match(await evaluate("document.querySelector('#movieFrame iframe').src"), /[?&]t=90/);
    await click("#movieForget");
    assert.equal(await evaluate("JSON.parse(localStorage.getItem('cinemagic:viewing:v1')).progress['tmdb:27205']===undefined"), true);
    assert.equal(await evaluate("document.querySelector('#modalBody [data-watchlist]').getAttribute('aria-pressed')"), "true");
    await closeModal();
    results.scenarios.push({ label: "disabled saved source", passed: ["fallback to first enabled source at next open", "resume retained", "one source option", "remove history preserves watchlist", "close disposal"] });
  } catch (error) { results.error = error.stack; process.exitCode = 1; }
  finally {
    // Ask Chromium to close its child processes before removing its own profile.
    if (client) { try { await client.send("Browser.close"); } catch { /* already exited */ } client.close(); }
    if (chrome?.exitCode === null) {
      await Promise.race([new Promise(resolve => chrome.once("exit", resolve)), sleep(3000)]);
      if (chrome.exitCode === null) chrome.kill();
    }
    if (server) server.kill(); staticServer?.close();
    // This is an isolated profile created above, never a personal browser profile.
    try {
      const resolved = path.resolve(profile);
      assert.equal(path.dirname(resolved), path.resolve(os.tmpdir()));
      assert.ok(path.basename(resolved).startsWith("cinemagic-s6-"));
      fs.rmSync(resolved, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
    } catch { results.profile_cleanup = "Browser may still hold temporary profile files"; }
    fs.writeFileSync(path.join(OUT, "browser.json"), JSON.stringify(results, null, 2) + "\n");
    console.log(JSON.stringify(results, null, 2));
  }
})();
