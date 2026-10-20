"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const Resolver = require("../../frontend/preference-resolver.js");
const Preferences = require("../../frontend/preferences.js");
const config = { version: 1, feature_version: "test-v1", vocabulary_size: 3, genres: ["Sci-Fi", "Drama"] };
const snapshot = [{ id: 1, source: "tmdb" }];
const record = id => ({ version: 1, feature_version: "test-v1", feature_language: "en-US", key: `tmdb:${id}`,
  status: "applied", vector: [[0, .6], [1, .8]], movie: { id, source: "tmdb", title: `External ${id}`, genres: ["Sci-Fi"], tags: ["space"] },
  taste: { genres: ["Sci-Fi"], tags: ["space"] }, resolved_at: 1000 });
const memory = () => { const data = new Map(); return { getItem: key => data.get(key), setItem: (key, v) => data.set(key, v) }; };
const tick = () => new Promise(resolve => setImmediate(resolve));
async function settle(resolver) { for (let i = 0; i < 100 && resolver.inFlight.size; i++) await tick(); assert.equal(resolver.inFlight.size, 0); }
function make(options = {}) {
  const resolver = new Resolver(snapshot, { clock: () => 1000, ...options });
  resolver.configure(config, { backend: true }); return resolver;
}

test("explicit IDs save immediately and resolved choices survive a new session independently of catalogue summaries", async () => {
  const storage = memory(), prefs = new Preferences(storage);
  prefs.save("tmdb", { liked: [10, 11], disliked: [12], mood: "space" });
  const r = make({ storage, fetcher: async path => record(Number(path.split("/").pop())) });
  const saved = prefs.load("tmdb"); r.sync(saved.liked, saved.disliked);
  assert.equal(r.summary().pending, 3); await settle(r);
  assert.equal(r.summary().applied, 3); assert.equal(r.payload().positive_count, 2); assert.equal(r.payload().negative_count, 1);
  const reload = make({ storage, fetcher: () => { throw Error("Compatible features must be reused"); } });
  reload.sync(saved.liked, saved.disliked); await settle(reload);
  assert.deepEqual(reload.payload(), r.payload());
  assert.equal(reload.get(11).title, "External 11");
});

test("reversal during lookup applies only the current dislike and removal never resurrects a choice", async () => {
  let complete, changes = 0;
  const r = make({ onChange: () => changes++, fetcher: () => new Promise(resolve => complete = resolve) });
  r.sync([10], []); r.sync([], [10]); complete(record(10)); await settle(r);
  assert.equal(r.payload().positive_count, 0); assert.equal(r.payload().negative_count, 1);
  assert.deepEqual(r.payload().vector, [[0, -.3], [1, -.4]]); assert.deepEqual(r.payload().seeds, []);
  r.sync([11], []); r.sync([], []); const before = changes; complete(record(11)); await settle(r);
  assert.equal(r.payload(), null); assert.equal(changes, before);
});

test("all saved choices hydrate incrementally with at most two requests and no silent truncation", async () => {
  let active = 0, peak = 0, calls = 0;
  const r = make({ fetcher: async path => {
    active++; peak = Math.max(peak, active); calls++; await tick(); active--;
    return record(Number(path.split("/").pop()));
  } });
  const ids = Array.from({ length: 20 }, (_, i) => i + 10);
  r.sync(ids, []); r.sync(ids, []); await settle(r);
  assert.equal(peak, 2); assert.equal(calls, 20); assert.equal(r.payload().positive_count, 20);
  assert.equal(r.payload().seeds.length, 2); assert.equal(r.payload().vector.length, 2, "Request work is aggregated by vocabulary, not movie count");
});

test("metadata failures and unknown IDs remain saved, explicit retry recovers without fabricating features", async () => {
  let fail = true;
  const r = make({ fetcher: async () => { if (fail) throw Object.assign(Error("not found"), { status: 404 }); return record(10); } });
  r.sync([10], []); await settle(r);
  assert.equal(r.status("tmdb:10").status, "unavailable"); assert.equal(r.payload(), null);
  assert.deepEqual(r.liked, [10]); fail = false; r.retry(); await settle(r);
  assert.equal(r.status("tmdb:10").status, "applied");
});

test("static mode keeps missing metadata pending and can encode complete cached English details", async () => {
  const known = { id: 10, full_details: true, metadata_language: "en-US" };
  const r = new Resolver(snapshot, { lookup: id => id === 10 ? known : { ...known, metadata_language: "hi-IN" }, fetcher: () => { throw Error("No live static requests"); } });
  r.configure(config, { localResolve: movie => record(movie.id) }); r.sync([10, 11], []); await settle(r);
  assert.equal(r.summary().applied, 1); assert.equal(r.summary().pending, 1); assert.equal(r.payload().positive_count, 1);
});

test("version changes and malformed vectors rehydrate or remain unavailable instead of mixing feature spaces", async () => {
  let wrong = true;
  const r = make({ fetcher: async () => wrong ? { ...record(10), vector: [[99, 1]] } : record(10) });
  r.sync([10], []); await settle(r); assert.equal(r.payload(), null);
  wrong = false; r.retry(); await settle(r); assert.equal(r.payload().positive_count, 1);
  r.configure({ ...config, feature_version: "test-v2" }, { backend: true }); await settle(r);
  assert.equal(r.payload(), null); assert.equal(r.status("tmdb:10").status, "unavailable");
});

test("feature-storage denial preserves session influence and preference IDs; old features remain usable on offline refresh", async () => {
  const r = make({ storage: { getItem: () => null, setItem: () => { throw Error("quota"); } }, fetcher: async () => record(10) });
  r.sync([10], []); await settle(r);
  assert.equal(r.storageFailed, true); assert.equal(r.payload().positive_count, 1);
  r.clock = () => 86401001; r.fetcher = async () => { throw Error("offline"); };
  r.retry(); await settle(r);
  assert.equal(r.status("tmdb:10").stale, true); assert.equal(r.payload().positive_count, 1);
});

test("curated IDs and conflicting imported choices cannot become positive external taste", async () => {
  let calls = 0;
  const r = make({ fetcher: async () => { calls++; return record(10); } });
  r.sync([10], [10]); await settle(r); assert.equal(r.payload().positive_count, 0); assert.equal(r.payload().negative_count, 1);
  const c = new Resolver([{ id: 1, source: "curated" }], { fetcher: () => calls++ });
  c.configure(config, { backend: true }); c.sync([10], []); await settle(c);
  assert.equal(c.payload(), null); assert.equal(calls, 1);
});

test("stale upstream metadata remains useful and a manual retry refreshes it even within the local TTL", async () => {
  let stale = true, calls = 0;
  const r = make({ fetcher: async () => { calls++; return { ...record(10), stale }; } });
  r.sync([10], []); await settle(r);
  assert.equal(r.summary().stale, 1); assert.equal(r.payload().positive_count, 1);
  stale = false; r.retry(); await settle(r);
  assert.equal(calls, 2); assert.equal(r.summary().stale, 0);
});

test("bounded derived-cache eviction retains all explicit choices and rehydrates uncached features after reload", async () => {
  const storage = memory(), prefs = new Preferences(storage), ids = Array.from({ length: 250 }, (_, i) => i + 10);
  const fetcher = async path => { const r = record(Number(path.split("/").pop())); r.movie.overview = "long metadata ".repeat(500); return r; };
  prefs.save("tmdb", { liked: ids });
  const r = make({ storage, fetcher }); r.sync(ids, []); await settle(r);
  // settle() has a small turn budget; instantly resolved batches drain in microtasks.
  assert.equal(r.payload().positive_count, 250);
  const serialized = storage.getItem("cinemagic:preference-features:v1"), cached = JSON.parse(serialized);
  assert.ok(cached.items.length < 200); assert.ok(serialized.length * 2 <= 2 * 1024 * 1024);
  const saved = new Preferences(storage).load("tmdb"); assert.equal(saved.liked.length, 250);
  const reloaded = make({ storage, fetcher }); reloaded.sync(saved.liked, saved.disliked);
  assert.ok(reloaded.summary().pending > 0); await settle(reloaded);
  assert.equal(reloaded.payload().positive_count, 250);
});
