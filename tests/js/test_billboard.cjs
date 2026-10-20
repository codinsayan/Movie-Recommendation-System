"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const Engine = require("../../frontend/engine.js");
const model = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const a = { ...model.movies[0], backdrop: "/test-backdrop.jpg" };
const b = { ...model.movies[1], backdrop: null, poster: null };
const output = (items = []) => ({ items, mode: "popular", taste: { genres: [], tags: [], confidence: 0 }, watched_rows: [] });

class Element {
  constructor() {
    this.innerHTML = ""; this.children = []; this.style = {}; this.offsetWidth = 0;
    const classes = new Set();
    this.classList = { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c),
      toggle: (c, on) => on ? classes.add(c) : classes.delete(c) };
  }
  replaceChildren() { this.children = []; this.innerHTML = ""; }
  appendChild(child) { this.children.push(child); child.parent = this; }
  get firstElementChild() { return this.children[0]; }
  remove() { this.parent.children = this.parent.children.filter(c => c !== this); }
  removeAttribute(key) { delete this[key]; }
  decode() { return Promise.resolve(); }
}

function harness(respond = async () => output()) {
  const nodes = new Map([".billboard", "#bbBg", "#bbPoster", "#bbContent", "#bbDots", "#modal"].map(s => [s, new Element()]));
  const data = new Map(), timers = new Map(), requests = [];
  let serial = 0;
  const context = {
    document: { querySelector: s => nodes.get(s), querySelectorAll: () => [] },
    window: { localStorage: { getItem: k => data.get(k), setItem: (k, v) => data.set(k, v) } },
    location: { hostname: "localhost" }, matchMedia: () => ({ matches: false }),
    requestAnimationFrame: cb => cb(), Image: Element, console,
    setTimeout: (callback, delay) => { timers.set(++serial, { callback, delay }); return serial; },
    clearTimeout: id => timers.delete(id),
    CinemagicProviders: require("../../frontend/providers.js"),
    CinemagicViewingStore: require("../../frontend/viewing.js"),
    CinemagicPreferenceStore: require("../../frontend/preferences.js"),
    CinemagicMoviePlayer: require("../../frontend/player.js"),
    fetch: async (url, options) => {
      assert.equal(url, "/api/recommend");
      const request = JSON.parse(options.body);
      requests.push(request);
      const response = await respond(request);
      return { ok: true, json: async () => response };
    },
  };
  const source = fs.readFileSync(path.join(__dirname, "../../frontend/app.js"), "utf8");
  // Exercise actual app closures without booting a browser or adding production test globals.
  const entry = "  boot();";
  assert.equal(source.split(entry).length, 2);
  const expose = `
    const messages = [];
    renderRows = renderMoods = renderDrawer = renderOnboard = () => {};
    toast = message => messages.push(message);
    globalThis.app = { state, bb, viewing, refresh, setBillboardItems, showAllPicks, buildRows, rowHTML, messages,
      useEngine(value) { engine = value; } };
  `;
  vm.runInNewContext(source.replace(entry, expose), context, { filename: "app.js" });
  const app = context.app;
  app.state.movies = model.movies;
  app.state.byId = new Map(model.movies.map(m => [m.id, m]));
  app.viewing.setOptions({ use_viewing: true, recent_playback_only: true });
  return { ...app, nodes, timers, requests, context, runRefresh() {
    const entry = [...timers].find(([, timer]) => timer.delay <= 150);
    assert.ok(entry, "Recommendation refresh must be scheduled");
    timers.delete(entry[0]);
    return entry[1].callback();
  } };
}

test("empty recent picks show labelled broader banner suggestions while the strict row stays empty", async () => {
  const f = harness(async request => output(request.recent_playback_only ? [] : [a]));
  f.refresh({ immediate: true }); await f.runRefresh();
  assert.equal(f.requests.length, 2);
  assert.equal(f.requests[0].use_viewing, true);
  assert.equal(f.requests[1].use_viewing, true);
  assert.equal(f.state.scored.length, 0);
  assert.equal(f.viewing.options().recent_playback_only, true);
  assert.equal(f.bb.items[0].id, a.id);
  assert.equal(f.bb.broader, true);
  assert.match(f.nodes.get("#bbContent").innerHTML, /More to discover/);
  assert.match(f.nodes.get("#bbContent").innerHTML, /Showing broader suggestions/);
  const row = f.buildRows().find(row => row.key === "picks");
  assert.match(f.rowHTML(row, 0, true), /data-show-all-picks/);
});

test("Show all picks disables only the recent filter and restores ordinary banner picks", async () => {
  const f = harness(async request => output(request.recent_playback_only ? [] : [a]));
  f.showAllPicks(); await f.runRefresh();
  assert.equal(f.viewing.options().recent_playback_only, false);
  assert.equal(f.viewing.options().use_viewing, true);
  assert.equal(f.requests.length, 1);
  assert.equal(f.state.scored[0].id, a.id);
  assert.equal(f.bb.broader, false);
  assert.doesNotMatch(f.nodes.get("#bbContent").innerHTML, /More to discover/);
});

test("eligible recent picks need no fallback and remove stale banner backgrounds", async () => {
  const f = harness(async () => output([b]));
  f.setBillboardItems([a]);
  assert.equal(f.nodes.get("#bbBg").children.length, 1);
  f.refresh({ immediate: true }); await f.runRefresh();
  assert.equal(f.requests.length, 1);
  assert.equal(f.bb.items[0].id, b.id);
  assert.equal(f.bb.broader, false);
  assert.equal(f.nodes.get("#bbBg").children.length, 0);
});

test("no picks at all clears stale movies, rotation and dots and shows recovery actions", async () => {
  const f = harness();
  f.setBillboardItems([a, b]);
  const oldTimer = f.bb.timer;
  assert.ok(f.timers.has(oldTimer));
  f.refresh({ immediate: true }); await f.runRefresh();
  assert.equal(f.bb.items.length, 0);
  assert.equal(f.timers.has(oldTimer), false);
  assert.equal(f.nodes.get("#bbBg").children.length, 0);
  assert.equal(f.nodes.get("#bbDots").innerHTML, "");
  assert.equal(f.nodes.get("#bbPoster").hidden, true);
  assert.match(f.nodes.get("#bbContent").innerHTML, /No matching picks yet/);
  assert.match(f.nodes.get("#bbContent").innerHTML, /Show all picks/);
  assert.match(f.nodes.get("#bbContent").innerHTML, /Browse movies/);
});

test("a failed broader request still renders the recovery state", async () => {
  const f = harness(async request => {
    if (!request.recent_playback_only) throw Error("offline");
    return output();
  });
  f.refresh({ immediate: true }); await f.runRefresh();
  assert.match(f.nodes.get("#bbContent").innerHTML, /Show all picks/);
  assert.equal(f.messages.length, 0);
});

test("a late broader response cannot overwrite picks after the filter is turned off", async () => {
  let finishOld;
  const f = harness(async request => {
    if (request.recent_playback_only) return output();
    if (!finishOld) return new Promise(resolve => { finishOld = resolve; });
    return output([b]);
  });
  f.refresh({ immediate: true });
  const pending = f.runRefresh();
  await new Promise(resolve => setImmediate(resolve));
  f.showAllPicks();
  finishOld(output([a]));
  await pending;
  assert.equal(f.bb.items.length, 0, "Scheduling the newer request already invalidates the old response");
  await f.runRefresh();
  assert.equal(f.bb.items[0].id, b.id);
  assert.equal(f.bb.broader, false);
});

test("the actual static engine also recovers a banner with both options enabled and no evidence", async () => {
  const f = harness(async () => { throw Error("Static mode must not fetch"); });
  f.useEngine(new Engine(model));
  f.refresh({ immediate: true }); await f.runRefresh();
  assert.equal(f.requests.length, 0);
  assert.equal(f.state.scored.length, 0);
  assert.equal(f.bb.items.length, 5);
  assert.equal(f.bb.broader, true);
  f.showAllPicks(); await f.runRefresh();
  assert.ok(f.state.scored.length > 0);
  assert.equal(f.bb.broader, false);
});
