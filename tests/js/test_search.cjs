"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const Catalogue = require("../../frontend/catalogue.js");

class Element {
  constructor() {
    this.innerHTML = ""; this.value = ""; this.listeners = new Map();
    const classes = new Set();
    this.classList = { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c),
      toggle: (c, on) => on ? classes.add(c) : classes.delete(c) };
  }
  addEventListener(type, handler) { this.listeners.set(type, handler); }
  querySelectorAll() { return []; }
  fire(type, event = {}) { return this.listeners.get(type)?.(event); }
  focus() {}
  blur() {}
}
const film = (id, title, extra = {}) => ({ id, tmdb_id: id, source: "tmdb", title, year: 2024,
  tags: [], genres: [], rating: 7, poster: "/poster.jpg", backdrop: "/backdrop.jpg", ...extra });
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness({ live = true, fetcher } = {}) {
  const nodes = new Map(["#searchForm", "#searchInput", "#searchClear", "#searchToggle", "#rowList", "#preview"].map(s => [s, new Element()]));
  const timers = new Map(), requests = [], positions = [], body = new Element();
  let serial = 0;
  const clock = { setTimeout: (callback, delay) => { timers.set(++serial, { callback, delay }); return serial; },
    clearTimeout: id => timers.delete(id) };
  const context = {
    document: { body, querySelector: s => nodes.get(s), querySelectorAll: () => [] },
    window: {}, location: { hostname: "localhost" }, matchMedia: () => ({ matches: false }),
    ...clock, scrollTo: position => positions.push(position), console,
    AbortController, // browsers provide it; the app aborts superseded recommendation requests
    CinemagicProviders: require("../../frontend/providers.js"),
    CinemagicViewingStore: require("../../frontend/viewing.js"),
    CinemagicPreferenceStore: require("../../frontend/preferences.js"),
    CinemagicMoviePlayer: require("../../frontend/player.js"),
  };
  const source = fs.readFileSync(require.resolve("../../frontend/app.js"), "utf8");
  vm.runInNewContext(source.replace("  boot();", `
    hidePreview = () => {};
    globalThis.app = { state, bindSearch, buildRows, renderRows, rowHTML,
      setCatalogue(value) { catalogue = value; } };
  `), context);
  const app = context.app;
  app.state.movies = [film(1, "Spider Movie"), film(2, "Unrelated")];
  app.state.byId = new Map(app.state.movies.map(m => [m.id, m]));
  const catalogue = new Catalogue(app.state.movies, { timers: clock, onChange: () => app.renderRows(), fetcher: async (url, options) => {
    requests.push(url);
    return fetcher ? fetcher(url, options) : { ok: true, json: async () => ({ items: [film(10, "Remote Spider")], total_pages: 1 }) };
  } });
  catalogue.live = live;
  app.setCatalogue(catalogue); app.bindSearch();
  return { ...app, catalogue, nodes, requests, positions, timers, body,
    type(value) { nodes.get("#searchInput").value = value; nodes.get("#searchInput").fire("input"); },
    async search() {
      assert.equal(timers.size, 1, "Typing should leave only one pending search");
      const [id, timer] = [...timers][0]; assert.equal(timer.delay, 300);
      timers.delete(id); await timer.callback(); await tick();
    } };
}

test("typing pauses fetch the latest query without Enter and display a dedicated landscape grid", async () => {
  const f = harness();
  f.type("spi"); f.type("spider");
  assert.equal(f.requests.length, 0);
  assert.equal(f.body.classList.contains("searching"), true);
  assert.equal(f.nodes.get("#searchClear").hidden, false);
  assert.match(f.nodes.get("#rowList").innerHTML, /Searching movies/);
  await f.search();
  assert.equal(f.requests.length, 1);
  assert.equal(new URL(f.requests[0], "http://local").searchParams.get("q"), "spider");
  assert.deepEqual(Array.from(f.buildRows(), row => row.key), ["search"]);
  const html = f.nodes.get("#rowList").innerHTML;
  assert.match(html, /class="search-grid"/); assert.match(html, /src="\/backdrop.jpg"/);
  assert.match(html, /Remote Spider/); assert.doesNotMatch(html, /data-scroll|Trending Now/);
  assert.equal(f.positions.length, 1, "Only entering search resets scroll, not every keystroke");
});

test("clear restores the home rows, preserves taste, and rejects an outstanding search", async () => {
  let finish;
  const f = harness({ fetcher: async () => new Promise(resolve => { finish = resolve; }) });
  f.state.liked.add(1); f.state.disliked.add(2); f.state.mood = "space";
  f.type("spider");
  const pending = f.search(); await tick();
  f.nodes.get("#searchClear").fire("click");
  assert.equal(f.state.query, ""); assert.equal(f.body.classList.contains("searching"), false);
  assert.equal(f.nodes.get("#searchInput").value, ""); assert.equal(f.nodes.get("#searchClear").hidden, true);
  assert.ok(f.buildRows().some(row => row.key === "picks"));
  assert.equal(f.state.liked.has(1), true); assert.equal(f.state.disliked.has(2), true); assert.equal(f.state.mood, "space");
  finish({ ok: true, json: async () => ({ items: [film(10, "Obsolete")], total_pages: 1 }) });
  await pending;
  assert.equal(f.catalogue.state.items.length, 0);
  assert.doesNotMatch(f.nodes.get("#rowList").innerHTML, /Obsolete|search-grid/);
});

test("paginated results remain in the grid with retry controls on a later-page failure", async () => {
  let fail = false;
  const f = harness({ fetcher: async url => {
    const page = Number(new URL(url, "http://local").searchParams.get("page"));
    if (fail) return { ok: false, status: 429 };
    return { ok: true, json: async () => ({ items: [film(page + 10, `Result ${page}`)], total_pages: 3 }) };
  } });
  f.type("result"); await f.search();
  assert.match(f.nodes.get("#rowList").innerHTML, /data-search-more/);
  await f.catalogue.more();
  assert.equal(f.buildRows()[0].items.length, 2);
  fail = true; await f.catalogue.more();
  assert.match(f.nodes.get("#rowList").innerHTML, /Result 1/);
  assert.match(f.nodes.get("#rowList").innerHTML, /Result 2/);
  assert.match(f.nodes.get("#rowList").innerHTML, /data-search-retry/);
});

test("static search shows every local match and escapes titles/queries without network calls", () => {
  const f = harness({ live: false });
  f.state.movies = Array.from({ length: 40 }, (_, i) => film(i + 1, '<Spider & friends>', { backdrop: null }));
  f.type("<Spider");
  assert.equal(f.buildRows()[0].items.length, 40);
  const html = f.nodes.get("#rowList").innerHTML;
  assert.match(html, /&lt;Spider &amp; friends&gt;/); assert.match(html, /poster-artwork/);
  assert.match(html, /Downloaded catalogue only/); assert.doesNotMatch(html, /<Spider/);
  assert.equal(f.requests.length, 0); assert.equal(f.timers.size, 0);
  f.type("no match"); assert.match(f.nodes.get("#rowList").innerHTML, /No titles match/);
});

test("composition waits for a complete title and Escape cancels a pending search", async () => {
  const f = harness(), input = f.nodes.get("#searchInput");
  input.fire("compositionstart"); f.type("incomplete");
  assert.equal(f.timers.size, 0); assert.equal(f.state.query, "");
  input.value = "complete"; input.fire("compositionend");
  await f.search(); assert.equal(f.requests.length, 1);
  f.type("another"); input.fire("keydown", { key: "Escape" });
  assert.equal(f.timers.size, 0); assert.equal(f.state.query, "");
  assert.equal(f.nodes.get("#searchForm").classList.contains("open"), false);
});
