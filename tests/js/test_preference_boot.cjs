"use strict";
const { test } = require("node:test"), assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const Engine = require("../../frontend/engine.js"), Preferences = require("../../frontend/preferences.js"), Resolver = require("../../frontend/preference-resolver.js");
const model = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const record = JSON.parse(fs.readFileSync(0, "utf8"));
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness(storage) {
  const engine = new Engine(model), timers = new Map(), requests = [], metadata = [];
  let serial = 0;
  const context = { console, window: { localStorage: storage }, location: { hostname: "localhost" },
    document: { querySelector: () => ({ innerHTML: "" }), querySelectorAll: () => [] },
    matchMedia: () => ({ matches: false }), AbortController,
    setTimeout: (callback, delay) => { timers.set(++serial, { callback, delay }); return serial; },
    clearTimeout: id => timers.delete(id),
    CinemagicProviders: require("../../frontend/providers.js"),
    CinemagicViewingStore: require("../../frontend/viewing.js"), CinemagicPreferenceStore: Preferences,
    CinemagicPreferenceResolver: Resolver, CinemagicCatalogueBrowser: require("../../frontend/catalogue.js"),
    CinemagicMoviePlayer: require("../../frontend/player.js"),
    fetch: async (path, options) => {
      if (path === "/api/meta") return new Promise((resolve, reject) => {
        metadata.push({ resolve: () => resolve({ ok: true, json: async () => model.meta }), reject });
        options?.signal?.addEventListener("abort", () => reject(Error("Timed out")), { once: true });
      });
      if (path === "/api/movies") return { ok: true, json: async () => model.movies };
      if (path === "/api/capabilities") return { ok: true, json: async () => ({ catalogue: { live_search: false } }) };
      if (path === "/api/recommend") {
        const body = JSON.parse(options.body); requests.push(body);
        return { ok: true, json: async () => engine.handle(path, body) };
      }
      throw Error("Unexpected bootstrap request " + path);
    } };
  const source = fs.readFileSync(require.resolve("../../frontend/app.js"), "utf8");
  // Keep the real boot/storage/resolver/request wiring; isolate presentation and DOM listeners.
  vm.runInNewContext(source.replace("  boot();", `
    bindAll = renderMoods = renderOnboard = renderDrawer = renderRows = setBillboardItems = () => {};
    skeletonRows = () => "";
    globalThis.app = { state, boot, configurePreferenceResolver };
  `), context);
  return { app: context.app, timers, requests, metadata, async runRecommendations() {
    const scheduled = [...timers].find(([, timer]) => timer.delay <= 150);
    assert.ok(scheduled, "Boot must schedule recommendations after resolving the feature contract");
    timers.delete(scheduled[0]); await scheduled[1].callback();
  } };
}

function savedStorage() {
  const values = new Map(), storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
  new Preferences(storage).save("tmdb", { liked: [record.movie.id] });
  const resolver = new Resolver(model.movies, { storage });
  resolver.records.set(record.key, { ...record, resolved_at: Date.now() }); resolver.persist();
  return storage;
}

test("first recommendation after a real app boot/reload includes restored external features, even when metadata is delayed", async () => {
  const storage = savedStorage(); let firstPicks;
  for (let reload = 0; reload < 2; reload++) {
    const f = harness(storage), boot = f.app.boot(); await tick();
    assert.equal(f.app.state.liked.has(record.movie.id), true);
    assert.equal(f.requests.length, 0);
    assert.equal([...f.timers.values()].some(timer => timer.delay <= 150), false, "No unpersonalized request may race feature restoration");
    f.metadata[0].resolve(); await boot; await f.runRecommendations();
    assert.equal(f.requests.length, 1); assert.equal(f.requests[0].external_preferences.positive_count, 1);
    assert.ok(f.app.state.becauseRows.some(row => row.source.id === record.movie.id));
    const picks = Array.from(f.app.state.scored, movie => movie.id);
    if (!firstPicks) firstPicks = picks; else assert.deepEqual(picks, firstPicks);
  }
});

test("feature-contract timeout preserves saved choices and falls back without blocking the app", async () => {
  const storage = savedStorage(), f = harness(storage), boot = f.app.boot(); await tick();
  const deadline = [...f.timers.values()].find(timer => timer.delay === 5000);
  assert.ok(deadline); deadline.callback(); await boot; await f.runRecommendations();
  assert.equal(f.app.state.liked.has(record.movie.id), true);
  assert.equal(new Preferences(storage).load("tmdb").liked[0], record.movie.id);
  assert.ok(f.app.state.scored.length); assert.equal(f.requests[0].external_preferences, undefined);
});
