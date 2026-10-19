"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const Catalogue = require("../../frontend/catalogue.js");
const snapshot = [{ id: 1, tmdb_id: 1, source: "tmdb", title: "Known", tags: [], genres: [] }];
const film = (id, title = "Remote") => ({ id, tmdb_id: id, source: "tmdb", title, tags: [], genres: [], metadata_language: "en-US", full_details: false });
const response = (data, status = 200) => ({ ok: status === 200, status, json: async () => data });
const timers = { setTimeout: () => 1, clearTimeout() {} };
const memory = () => { const data = new Map(); return { getItem: (key) => data.get(key), setItem: (key, value) => data.set(key, value) }; };

test("static mode and curated ID space never invoke remote search", async () => {
  let calls = 0;
  const browser = new Catalogue(snapshot, { timers, fetcher: async () => { calls++; throw Error("unexpected request"); } });
  await browser.configure(false); browser.setQuery("test"); await browser.run(browser.seq, false);
  assert.equal(calls, 0); assert.equal(browser.state.loading, false);
  const curated = new Catalogue([{ ...snapshot[0], source: "curated", tmdb_id: null }], { timers, fetcher: async () => { calls++; } });
  await curated.configure(true);
  assert.equal(calls, 0); assert.equal(curated.live, false);
});

test("missing capabilities stay snapshot-only without pretending the model supports new API paths", async () => {
  const browser = new Catalogue(snapshot, { timers, fetcher: async () => response({}, 404) });
  await browser.configure(true);
  assert.equal(browser.live, false);
  browser.setQuery("test"); assert.equal(browser.state.loading, false);
});

test("search pagination deduplicates titles and leaves the trained snapshot unchanged", async () => {
  const browser = new Catalogue(snapshot, { timers, fetcher: async (path) => {
    const page = new URL(path, "http://local").searchParams.get("page");
    return response({ items: page === "1" ? [film(2), film(3)] : [film(3), film(4)], total_pages: 2 });
  } });
  browser.live = true;
  browser.setQuery("movie"); await browser.run(browser.seq, false); await browser.more();
  assert.deepEqual(browser.state.items.map((m) => m.id), [2, 3, 4]);
  assert.equal(browser.state.items[0].in_model, false);
  assert.equal(browser.snapshot.size, 1); assert.equal(snapshot.length, 1);
});

test("late responses cannot overwrite a newer query even if fetch ignores abort", async () => {
  let finishFirst;
  const browser = new Catalogue(snapshot, { timers, fetcher: async (path) => {
    const query = new URL(path, "http://local").searchParams.get("q");
    if (query === "old") return new Promise((resolve) => { finishFirst = () => resolve(response({ items: [film(2, "Old")], total_pages: 1 })); });
    return response({ items: [film(3, "New")], total_pages: 1 });
  } });
  browser.live = true;
  browser.setQuery("old"); const old = browser.run(browser.seq, false);
  browser.setQuery("new"); await browser.run(browser.seq, false);
  finishFirst(); await old;
  assert.equal(browser.state.query, "new"); assert.equal(browser.state.items[0].title, "New");
  assert.equal(browser.get(2), undefined);
});

test("saved remote details survive refresh with fresh model membership and no credentials", async () => {
  const storage = memory();
  const browser = new Catalogue(snapshot, { timers, storage, fetcher: async () => response({ ...film(2), full_details: true, cast: ["Actor"] }) });
  browser.backend = true;
  const details = await browser.details(2); assert.equal(details.in_model, false);
  const restored = new Catalogue(snapshot, { storage, timers });
  assert.equal(restored.get(2).title, "Remote");
  assert.deepEqual(restored.get(2).cast, ["Actor"]);
  assert.equal(restored.savedMovies().length, 1);
  assert.equal((await restored.details(2)).full_details, true);
  const indexedLater = new Catalogue([...snapshot, film(2)], { storage, timers });
  assert.equal(indexedLater.get(2).in_model, true);
});

test("search errors retain previous pages and give a retry state", async () => {
  let fail = false;
  const browser = new Catalogue(snapshot, { timers, fetcher: async () => fail ? response({}, 429) : response({ items: [film(2)], total_pages: 2 }) });
  browser.live = true; browser.setQuery("test"); await browser.run(browser.seq, false);
  fail = true; await browser.more();
  assert.equal(browser.state.items.length, 1); assert.equal(browser.state.page, 1);
  assert.match(browser.state.error, /busy/); assert.equal(browser.state.loading, false);
});

test("metadata language changes replace old localized summaries and refetch details", async () => {
  const browser = new Catalogue(snapshot, { timers });
  browser.register({ ...film(2, "English"), full_details: true });
  browser.register({ ...film(2, "हिन्दी"), metadata_language: "hi-IN" });
  assert.equal(browser.get(2).title, "हिन्दी");
  assert.equal(browser.get(2).full_details, false);
});
